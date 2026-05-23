"""
memory_brain.py — PostgreSQL / SQLite memory for LLM agent.
Stores findings, facts, and knowledge for persistent recall across sessions.

If DATABASE_URL is set, uses PostgreSQL. Otherwise falls back to SQLite
automatically — no setup needed.
"""

import os as _os
import json
from datetime import datetime

_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
_DATABASE_URL = _os.environ.get("DATABASE_URL", "")

# ── SQLite fallback (zero setup) ─────────────────────────────────────────
_SQLITE_PATH = _os.environ.get("SQLITE_PATH", _os.path.join(_os.path.expanduser("~"), "submind_memory.db"))
_db = None  # 'postgres' or 'sqlite'
_pg_available = False

def _init_db():
    """Detect available database. PostgreSQL preferred, SQLite fallback."""
    global _db, _pg_available
    if _DATABASE_URL:
        try:
            import psycopg2, psycopg2.extras
            from urllib.parse import urlparse
            p = urlparse(_DATABASE_URL)
            conn = psycopg2.connect(
                host=p.hostname or "localhost",
                port=p.port or 5432,
                dbname=p.path.lstrip("/") or "llm_memory",
                user=p.username or "postgres",
                password=p.password or "postgres",
            )
            cur = conn.cursor()
            cur.execute("""CREATE TABLE IF NOT EXISTS memory (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                category TEXT DEFAULT 'general',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""")
            conn.commit(); cur.close(); conn.close()
            _db = 'postgres'
            _pg_available = True
            return True
        except Exception:
            pass
    try:
        import sqlite3
        conn = sqlite3.connect(_SQLITE_PATH)
        conn.execute("""CREATE TABLE IF NOT EXISTS memory (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.commit(); conn.close()
        _db = 'sqlite'
        return True
    except Exception:
        return False


def _get_pg_conn():
    from urllib.parse import urlparse
    import psycopg2, psycopg2.extras
    p = urlparse(_DATABASE_URL)
    return psycopg2.connect(
        host=p.hostname or "localhost",
        port=p.port or 5432,
        dbname=p.path.lstrip("/") or "llm_memory",
        user=p.username or "postgres",
        password=p.password or "postgres",
    )

def _get_sqlite_conn():
    import sqlite3
    conn = sqlite3.connect(_SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


_DB_READY = _init_db()


def save_memory(key: str, value: str, category: str = "general") -> str:
    """Save a fact or finding. Updates if key exists."""
    if not _DB_READY:
        return "Memory unavailable — install PostgreSQL or ensure write access to SQLite path."
    try:
        if _db == 'postgres':
            conn = _get_pg_conn(); cur = conn.cursor()
            cur.execute(
                "INSERT INTO memory (key, value, category, created_at) VALUES (%s,%s,%s,%s) ON CONFLICT (key) DO UPDATE SET value=EXCLUDED.value, category=EXCLUDED.category, created_at=CURRENT_TIMESTAMP",
                (key.strip(), value.strip(), category.strip(), datetime.now()),
            )
            conn.commit(); cur.close(); conn.close()
        else:
            conn = _get_sqlite_conn()
            conn.execute(
                "INSERT OR REPLACE INTO memory (key, value, category, created_at) VALUES (?,?,?,?)",
                (key.strip(), value.strip(), category.strip(), datetime.now()),
            )
            conn.commit(); conn.close()
        return f"Saved: {key}"
    except Exception as e:
        return f"Error saving memory: {e}"


def get_memory(key: str) -> str:
    """Retrieve a specific memory by exact key."""
    if not _DB_READY:
        return "Memory unavailable — install PostgreSQL or ensure write access to SQLite path."
    try:
        if _db == 'postgres':
            conn = _get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT key, value, category, created_at FROM memory WHERE key=%s", (key.strip(),))
            row = cur.fetchone(); cur.close(); conn.close()
            if row:
                return f"[{row['category']}] {row['key']}: {row['value']} ({row['created_at'].strftime('%Y-%m-%d')})"
        else:
            conn = _get_sqlite_conn()
            row = conn.execute("SELECT key, value, category, created_at FROM memory WHERE key=?", (key.strip(),)).fetchone()
            conn.close()
            if row:
                return f"[{row['category']}] {row['key']}: {row['value']} ({row['created_at'][:10]})"
        return f"No memory found for: {key}"
    except Exception as e:
        return f"Error retrieving memory: {e}"


def search_memory(query: str, category: str = None, limit: int = 10) -> str:
    """Search memories by keyword."""
    if not _DB_READY:
        return "Memory unavailable — install PostgreSQL or ensure write access to SQLite path."
    try:
        if _db == 'postgres':
            conn = _get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            if category:
                cur.execute(
                    "SELECT key, value, category, created_at FROM memory WHERE (key ILIKE %s OR value ILIKE %s) AND category=%s ORDER BY created_at DESC LIMIT %s",
                    (f"%{query}%", f"%{query}%", category, limit),
                )
            else:
                cur.execute(
                    "SELECT key, value, category, created_at FROM memory WHERE key ILIKE %s OR value ILIKE %s ORDER BY created_at DESC LIMIT %s",
                    (f"%{query}%", f"%{query}%", limit),
                )
            rows = cur.fetchall(); cur.close(); conn.close()
        else:
            conn = _get_sqlite_conn()
            if category:
                rows = conn.execute(
                    "SELECT key, value, category, created_at FROM memory WHERE (key LIKE ? OR value LIKE ?) AND category=? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", category, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT key, value, category, created_at FROM memory WHERE key LIKE ? OR value LIKE ? ORDER BY created_at DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                ).fetchall()
            conn.close()
        if not rows:
            return f"No memories found for: {query}"
        return "\n".join(f"[{r['category']}] {r['key']}: {r['value'][:200]}" for r in rows)
    except Exception as e:
        return f"Error searching memory: {e}"


def list_recent(limit: int = 5) -> str:
    """List most recent memories."""
    if not _DB_READY:
        return "Memory unavailable — install PostgreSQL or ensure write access to SQLite path."
    try:
        if _db == 'postgres':
            conn = _get_pg_conn()
            cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            cur.execute("SELECT key, value, category, created_at FROM memory ORDER BY created_at DESC LIMIT %s", (limit,))
            rows = cur.fetchall(); cur.close(); conn.close()
        else:
            conn = _get_sqlite_conn()
            rows = conn.execute("SELECT key, value, category, created_at FROM memory ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
            conn.close()
            rows = [dict(r) for r in rows]
        if not rows:
            return "Memory is empty."
        return "\n".join(f"[{r['category']}] {r['key']} ({r['created_at']})" for r in rows)
    except Exception as e:
        return f"Error listing memory: {e}"


def delete_memory(key: str) -> str:
    """Delete a memory by key."""
    if not _DB_READY:
        return "Memory unavailable — install PostgreSQL or ensure write access to SQLite path."
    try:
        if _db == 'postgres':
            conn = _get_pg_conn(); cur = conn.cursor()
            cur.execute("DELETE FROM memory WHERE key=%s", (key.strip(),))
            deleted = cur.rowcount
            conn.commit(); cur.close(); conn.close()
        else:
            conn = _get_sqlite_conn()
            cur = conn.execute("DELETE FROM memory WHERE key=?", (key.strip(),))
            deleted = cur.rowcount
            conn.commit(); conn.close()
        return f"Deleted {deleted} memory(s)" if deleted else f"No memory found for: {key}"
    except Exception as e:
        return f"Error deleting memory: {e}"
