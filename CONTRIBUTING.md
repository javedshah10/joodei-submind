# Contributing to SubMind

SubMind is built around a modular adapter pattern. Adding a new platform (Claude, Perplexity, DeepSeek, etc.) is a contained addition that doesn't touch existing adapters.

## Adding a New Platform Adapter

### 1. Create your adapter file

Name it `<platform>_delegate.py` (e.g., `claude_delegate.py`).

### 2. Implement the adapter interface

Your adapter must expose these functions:

```python
def delegate_to_<platform>(query: str) -> str:
    """Single-shot query. Open → inject → send → extract → return."""

def delegate_to_<platform>_session(task: str, max_loops: int = 5) -> str:
    """Multi-turn session. Maintain chat window across calls."""

def get_session_title() -> str:
    """Return current session title from platform sidebar."""

def rename_session_title(new_title: str) -> str:
    """Rename current session in platform sidebar."""

def cleanup_session(target_title: str = None) -> str:
    """Delete session by title. None = current."""
```

### 3. Internal utilities your adapter should implement

```python
def _launch_open() -> str:
    """Open platform in Chrome with stealth args + dedicated profile."""

def _snapshot() -> str:
    """Return agent-browser snapshot of page (prefer -i filter)."""

def _find_input_ref(snap: str) -> str | None:
    """Find textbox reference from snapshot. Use role + keyword matching."""

def _inject_text(text: str) -> None:
    """Type text into input box. Use JS injection for contenteditable,
    agent-browser type for React rich-textarea."""

def _click_send() -> None:
    """Click send/submit button. Filter out Edit/Update/Cancel buttons."""

def _wait_for_response(round: int = 1) -> str:
    """Poll for response with 3-layer completeness guard."""
```

## Self-Healing Selector Guidelines

Selectors MUST NOT hardcode CSS classes, IDs, or DOM paths. Instead:

1. **Use role-based matching** — `_find_ref(snap, role, *keywords)` where role is `textbox`, `button`, `link`, etc.
2. **Use multi-keyword confirmation** — match on 2+ independent keywords (e.g., `"gemini"`, `"prompt"` for input box).
3. **Regex for ref extraction** — `ref=(\S+)\]` extracts the agent-browser reference from snapshot lines.
4. **Fallback chains** — try primary selector, then alternate keywords, then broader match.

Example:
```python
def _find_input_ref(snap: str) -> str | None:
    return (
        _find_ref(snap, 'textbox', 'gemini') or
        _find_ref(snap, 'textbox', 'prompt') or
        _find_ref(snap, 'textbox', 'enter')
    )
```

## 3-Layer Response Guard (Required for All Adapters)

Every session adapter MUST implement this polling guard inside `_wait_for_response()`:

### Layer 1 — Busy State Detection
Check for "Stop generating" button or equivalent loading indicator. Skip extraction entirely if platform is still generating.
```python
is_busy = check_loading_indicator()
if is_busy:
    continue  # skip this poll
```

### Layer 2 — Stability Check
Extract text each poll. Only return when the same text appears twice consecutively (len > 10 chars).
```python
if current_text == last_text and len(current_text) > 10:
    stable_count += 1
    if stable_count >= 2:
        return current_text
else:
    stable_count = 0
    last_text = current_text
```

### Layer 3 — Closing Marker Gate
If using markers, verify both opening and closing markers are present. Reset stability counter if response appears incomplete.
```python
if "Start:>" in text and "<:End" not in text:
    stable_count = 0
    continue
```

## PR Checklist

- [ ] Adapter implements all required interface functions
- [ ] Self-healing selectors — no hardcoded CSS classes or IDs
- [ ] 3-layer response guard implemented in `_wait_for_response()`
- [ ] Separate Chrome profile for the new platform
- [ ] One-time login via `setup_accounts.py` (or documented manual step)
- [ ] MCP tool registration in `joodei_browser_mcp.py`
- [ ] Session management (get title, rename, delete) implemented
- [ ] All print output goes to `stderr` (MCP stdio compatibility)
- [ ] Tested with live Chrome interaction

## Code Style

- No comments unless explaining non-obvious intent
- One-line docstrings on all functions
- `print()` always to `sys.stderr` using `file=sys.stderr`
- 4-space indentation, 120-char line limit
- F-strings for string formatting
