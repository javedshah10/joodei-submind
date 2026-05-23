"""
gemini.py — Delegate tasks to Google Gemini via real Chrome browser.

Usage:
    from gemini import delegate_to_gemini
    answer = delegate_to_gemini("What is the latest news on AI?")
"""

import subprocess
import time
import sys
import re
import os as _os
import base64
import shutil as _shutil
from datetime import datetime as _datetime

_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))

# Example: r"C:\Users\YourName\AppData\Roaming\npm\agent-browser.cmd"
AGENT_BROWSER = _os.environ.get("AGENT_BROWSER", _os.path.join(_os.path.expanduser("~"), "AppData", "Roaming", "npm", "agent-browser.cmd"))
# Example: r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_EXE = _os.environ.get("CHROME_EXE", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
# Example: r"C:\Users\YourName\submind-gemini-profile"
PROFILE = _os.environ.get("GEMINI_PROFILE", _os.path.join(_os.path.expanduser("~"), "submind-gemini-profile"))
SESSION = "gemini"
STEALTH_ARGS = (
    "--disable-blink-features=AutomationControlled,"
    "--no-first-run,"
    "--no-default-browser-check"
)
POLL_INTERVAL = 10
MAX_WAIT = 300

_session_active = False  # Session persistence for multi-query in same chat

# ── Markers ──
START_MARKER = "Start:>"
STOP_MARKER = "<:End"
MARKER_PATTERN = re.compile(re.escape(START_MARKER) + r"(.+?)" + re.escape(STOP_MARKER), re.DOTALL)

# ── Browser Commands ──
def _run(args: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding='utf-8', errors='replace')
        out = (result.stdout or '').strip()
        if not out: out = (result.stderr or '').strip()
        if 'ERR_INTERNET_DISCONNECTED' in out or 'ERR_NETWORK' in out: return 'CONNECTION_LOST'
        return out
    except subprocess.TimeoutExpired: return ""
    except Exception: return "CONNECTION_LOST"

_last_profile = None

# Example: r"C:\Users\YourName\submind\gemini\docs"
DOWNLOAD_PATH = _os.environ.get("GEMINI_DOWNLOAD_PATH", _os.path.join(_os.path.expanduser("~"), "submind", "gemini", "docs"))
EXTENSION_PATH = _os.environ.get("GEMINI_EXTENSION_PATH", _os.path.join(_SCRIPT_DIR, "gemini", "extension"))


def _launch_open() -> str:
    global _last_profile
    if _last_profile is None:
        _last_profile = PROFILE
    if _last_profile != PROFILE:
        _run([AGENT_BROWSER, 'close', '--all'], timeout=10)
        time.sleep(2)
    _last_profile = PROFILE
    _os.makedirs(DOWNLOAD_PATH, exist_ok=True)
    result = _run([AGENT_BROWSER, '--executable-path', CHROME_EXE, '--args', STEALTH_ARGS, '--headed', '--profile', PROFILE, '--session-name', SESSION, '--download-path', DOWNLOAD_PATH, '--extension', EXTENSION_PATH, 'open', 'https://gemini.google.com/app'], timeout=60)
    return result

def _session(args: list[str], timeout: int = 30) -> str:
    return _run([AGENT_BROWSER, '--session-name', SESSION] + args, timeout=timeout)

def _snapshot() -> str: return _session(['snapshot', '-i'])
def _click(ref: str) -> str: return _session(['click', ref])
def _eval_js(js: str) -> str: return _session(['eval', js])

def _find_ref(snapshot: str, role: str, *keywords: str) -> str | None:
    for line in snapshot.split('\n'):
        lower = line.lower()
        if role.lower() in lower and all(kw.lower() in lower for kw in keywords):
            match = re.search(r'ref=(\S+)\]', line)
            if match: return f'@{match.group(1)}'
    return None

def _find_input_ref(snap: str) -> str | None:
    return _find_ref(snap, 'textbox', 'gemini') or _find_ref(snap, 'textbox', 'prompt') or _find_ref(snap, 'textbox', 'enter')

def _inject_text(text: str) -> None:
    """Type via agent-browser type — only reliable approach for Gemini React.
    Newlines trigger Enter key; collapse to single line to avoid premature send."""
    text = text.replace('\n', ' ').replace('\r', ' ')
    for attempt in range(3):
        snap = _snapshot()
        ref = _find_input_ref(snap)
        if ref:
            _session(['type', ref, text], timeout=120)
            time.sleep(3)
            return
        time.sleep(2)

def _click_send() -> None:
    """Click Gemini send button — must be enabled and NOT Edit/Update."""
    _eval_js(
        "(function(){"
        "const btns=document.querySelectorAll('button');"
        "for(const b of btns){"
        "const label=b.getAttribute('aria-label')||'';"
        "const text=b.textContent||'';"
        "if(b.disabled)continue;"
        "if(text.includes('Edit')||text.includes('Update')||text.includes('Cancel'))continue;"
        "if(label.includes('Send')||text.includes('Send')){"
        "b.click();return'sent:'+text;"
        "}"
        "}"
        "return'no-send-btn';"
        "})()"
    )

def _poll_for_response(min_count: int = 2) -> str:
    """Poll for Gemini response — min_count=2 for query (prompt has marker), 1 for session."""
    for attempt in range(1, (MAX_WAIT // POLL_INTERVAL) + 1):
        time.sleep(POLL_INTERVAL); snap = _snapshot()
        if 'CONNECTION_LOST' in snap: return snap
        current_text = _eval_js(
            "(function(){"
            "const body=document.body.innerText;"
            "const count=(body.match(/Start:>/g)||[]).length;"
            f"if(count<{min_count})return'';"
            "const start=body.lastIndexOf('Start:>');"
            "const end=body.lastIndexOf('<:End');"
            "if(start<0||end<start)return'';"
            "const text=body.substring(start+8,end).trim();"
            "if(text.length<5)return'';"
            "return text;"
            "})()"
        )
        if current_text:
            print(f"  [Polled {attempt} time(s), response received]", file=sys.stderr)
            return f"[Polled {attempt}x] {current_text}"
        # Fallback: Gemini didn't use markers
        fallback = _eval_js(
            "(function(){"
            "const body=document.body.innerText;"
            "const said=body.lastIndexOf('Gemini said');"
            "if(said<0)return'';"
            "let t=body.substring(said+12);"
            "const tools=t.indexOf('Tools');"
            "if(tools>0)t=t.substring(0,tools);"
            "return t.trim();"
            "})()"
        ).strip().strip('"')
        if fallback and len(fallback) > 5:
            print(f"  [Polled {attempt} time(s), Gemini said fallback]", file=sys.stderr)
            return f"[Polled {attempt}x] {fallback}"
    print(f"  [Timed out after {MAX_WAIT//POLL_INTERVAL} polls]", file=sys.stderr)
    return ""

def extract_response(raw_text: str) -> str:
    # Try marker extraction first
    match = MARKER_PATTERN.search(raw_text)
    if match: return match.group(1).strip()
    # Fallback: text after "Gemini said"
    parts = raw_text.split("Gemini said")
    if len(parts) > 1: return parts[1].strip()[:500]
    return raw_text.strip()[:500]


def _is_truncated(text: str) -> bool:
    """Check if response appears cut off — no closing marker, ends mid-word."""
    if not text: return False
    text = text.strip()
    # No closing period at end
    last = text[-1] if text else ''
    if last and last not in '.!?":End':
        return True
    return False

# ── Chat Setup ──

def _setup_chat(temp: bool = True, fresh: bool = True) -> str | None:
    """Open Gemini, check login, start chat."""
    global _session_active
    if fresh:
        _launch_open(); time.sleep(6)
    for _ in range(3):
        snap = _snapshot()
        if _find_input_ref(snap): break
        if 'sign in' in snap.lower() and not _find_input_ref(snap):
            time.sleep(3); continue
        break
    snap = _snapshot()
    if not _find_input_ref(snap) and ('sign in to' in snap.lower() or 'get started' in snap.lower()):
        return "Gemini not logged in — please login manually first"
    # Check if already in conversation (survives server restart)
    url = _eval_js('window.location.href').strip().strip('"')
    in_convo = '/app/' in url and len(url.split('/app/')[1]) > 5 if url else False
    if fresh and not in_convo:
        new_chat_ref = _find_ref(snap, 'link', 'new chat')
        if new_chat_ref: _click(new_chat_ref); time.sleep(2); snap = _snapshot()
    if temp and fresh and not in_convo:
        temp_ref = _find_ref(snap, 'button', 'temporary')
        if temp_ref: _click(temp_ref); time.sleep(1); snap = _snapshot()
    if fresh and not in_convo:
        mode_ref = _find_ref(snap, 'button', 'open mode picker')
        if mode_ref:
            _click(mode_ref); time.sleep(1)
            snap2 = _snapshot()
            thinking_opt = _find_ref(snap2, 'menuitem', 'thinking')
            if thinking_opt:
                _click(thinking_opt); time.sleep(1)
    _session_active = True
    return None

# ── Delegate Functions ──

def delegate_to_gemini(query: str) -> str:
    err = _setup_chat(temp=True, fresh=True)  # Always fresh, single question
    if err: return err
    snap = _snapshot()
    if not _find_input_ref(snap):
        _session(['open', 'https://gemini.google.com/app']); time.sleep(4)
        err = _setup_chat(temp=True)
        if err: return err
    input_ref = _find_input_ref(_snapshot())
    for _ in range(2):
        if input_ref: break
        time.sleep(3); input_ref = _find_input_ref(_snapshot())
    if not input_ref: return "Gemini input box not found"
    # Single-line prompt — rich-textarea doesn't support multiline injection
    wrapped = (
        f"<query>{query}</query> "
        "<rules>Pick ONE length: 10,50,100,250,350,500,500+ words. "
        "10=fact,50=simple,100=moderate,250=nuanced,350=detailed,500=complex,500+=comprehensive. "
        f"Start answer with {START_MARKER}. End answer with {STOP_MARKER}. "
        "No other text outside these tags.</rules>"
    )
    _inject_text(wrapped); _click_send()
    result = _poll_for_response()
    if not result: return "Gemini timed out"
    if 'CONNECTION_LOST' in result: return "Internet connection lost"
    return extract_response(result)

def delegate_to_gemini_session(task: str, max_loops: int = 1) -> str:
    """Agent-driven single-shot per call. Multiple calls = same chat."""
    global _session_active
    url = _eval_js('window.location.href').strip().strip('"')
    in_convo = url and '/app/' in url and len(url.split('/app/')[1]) > 5
    _session_active = _session_active or in_convo
    
    err = _setup_chat(temp=False, fresh=not _session_active)
    if err: return err
    _session_active = True

    results = []
    for loop in range(1, max_loops + 1):
        print(f"  [Gemini session loop {loop}/{max_loops}]", file=sys.stderr)
        snap = _snapshot(); input_ref = _find_input_ref(snap)
        for _ in range(2):
            if input_ref: break
            time.sleep(2); snap = _snapshot(); input_ref = _find_input_ref(snap)
        if not input_ref: return "Gemini input box not found"

        msg = f"<task>{task}</task> <rules>Pick ONE length: 10,50,100,250,350,500,500+ words. Wrap answer in Start:> and <:End markers. No filler.</rules>"
        _inject_text(msg); _click_send()
        response = _wait_for_response(round=loop)
        
        if not response or 'SKIPPED' in response or 'timed out' in response.lower():
            break
        results.append(response)
        if 'GOAL_ACHIEVED' in response:
            break
        break  # Single response per call
    
    return results[-1] if results else response or "[No response]"


def _wait_for_response(round: int = 1) -> str:
    """3-layer poll guard: busy-state → stability → closing marker."""
    POLL_INTERVAL = 19
    MAX_WAIT = 300
    last_text = ""
    stable_count = 0

    for _ in range(MAX_WAIT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)

        # LAYER 1 — Busy state detection (skip if still generating)
        is_busy = _eval_js(
            "(function(){"
            "const stop=document.querySelector("
            "'[aria-label*=\"Stop\"],button[aria-label*=\"Stop\"],"
            "[data-test-id=\"stop-button\"]');"
            "return stop&&!stop.disabled?'busy':'idle';"
            "})()"
        ).strip().strip('"')
        if 'busy' in is_busy:
            print("  [Gemini still generating — waiting]", file=sys.stderr)
            stable_count = 0
            continue

        # Extract text (markers first, then fallback)
        raw = _eval_js(
            "(function(){"
            "const body=document.body.innerText;"
            f"const count=(body.match(/Start:>/g)||[]).length;"
            f"if(count<{round+1})return'';"  # round-aware marker count
            "const start=body.lastIndexOf('Start:>');"
            "const end=body.lastIndexOf('<:End');"
            "if(start<0||end<start)return'';"
            "return body.substring(start+8,end).trim();"
            "})()"
        ).strip().strip('"')
        if not raw or len(raw) < 5:
            # Fallback to "Gemini said"
            raw = _eval_js(
                "(function(){"
                "const body=document.body.innerText;"
                "const said=body.lastIndexOf('Gemini said');"
                "if(said<0)return'';"
                "let t=body.substring(said+12);"
                "const tools=t.indexOf('Tools');"
                "if(tools>0)t=t.substring(0,tools);"
                "return t.trim();"
                "})()"
            ).strip().strip('"')
        if not raw or len(raw) < 3:
            continue

        # LAYER 3 — Closing marker gate
        if 'Start:>' in raw and '<:End' not in raw:
            print("  [Marker opened but not closed — still typing]", file=sys.stderr)
            stable_count = 0
            continue

        # LAYER 2 — Stability check (same text twice before returning)
        if raw == last_text and len(raw) > 10:
            stable_count += 1
            if stable_count >= 2:
                print(f"  [Response stable — returning]", file=sys.stderr)
                return raw
        else:
            stable_count = 0
            last_text = raw

    return "[Gemini timed out — session still active, call again]"


def cleanup_gemini_session(target_title: str = None) -> str:
    """Delete a Gemini session by title. Hover required for 3-dot menu."""
    target_title = target_title or ''
    for attempt in range(2):
        # Hover over the conversation link to reveal 3-dot button
        result = _eval_js(
            "(function(){"
            "const links=document.querySelectorAll('a');"
            "for(let i=0;i<links.length;i++){"
            "const t=links[i].textContent.trim();"
            "const h=links[i].href||'';"
            f"if(t.length>3&&h.includes('/app/')&&("
            f"  '{target_title}'===''||t==='{target_title}')){{"
            # Get the custom element containing this link
            "const item=links[i].closest('gem-nav-list-item');"
            "if(!item)return'no item';"
            # Hover triggers the trailing button
            "const evt=new MouseEvent('mouseover',{bubbles:true});"
            "item.dispatchEvent(evt);"
            # Click the trailing button (3-dot)
            "const btns=item.querySelectorAll('button');"
            "if(btns.length){btns[0].click();return'clicked:'+t;}"
            "return'no 3-dot btn';"
            "}"
            "}"
            "return'no match';"
            "})()"
        ).strip().strip('"')
        time.sleep(1)
        # Click Delete in dropdown
        _eval_js(
            "(function(){"
            "const items=document.querySelectorAll('[role=\"menuitem\"]');"
            "items.forEach(i=>{if(i.textContent.includes('Delete'))i.click()});"
            "return'delete clicked';"
            "})()"
        )
        time.sleep(0.5)
        # Confirm deletion
        _eval_js(
            "(function(){"
            "const btns=document.querySelectorAll('button');"
            "btns.forEach(b=>{if(b.textContent.trim()==='Delete')b.click()});"
            "return'confirmed';"
            "})()"
        )
        time.sleep(1)
        # Verify deleted
        check = _eval_js(
            "(function(){"
            "const links=document.querySelectorAll('a');"
            "for(let i=0;i<links.length;i++){"
            f"if(links[i].textContent.trim()==='{target_title}')return'still exists';"
            "}"
            "return'deleted';"
            "})()"
        ).strip().strip('"')
        if 'deleted' in check:
            return f"Deleted: {target_title or 'current session'}"
        time.sleep(1)
    return f"Failed to delete {target_title or 'current session'}"


def get_session_title() -> str:
    """Get the current Gemini session title from sidebar."""
    titles = _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('a');"
        "const titles=[];"
        "for(let i=0;i<links.length;i++){"
        "const t=links[i].textContent.trim();"
        "const h=links[i].href||'';"
        "if(t.length>3&&h.includes('/app/')&&t!=='Gemini')titles.push(t);"
        "}"
        "return titles[0]||'';"
        "})()"
    ).strip().strip('"')
    return titles or "No active session"


def rename_session_title(new_title: str) -> str:
    """Rename the current Gemini session in sidebar. Hover required."""
    # Hover over first conversation to reveal 3-dot, then click
    _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('a');"
        "for(const l of links){"
        "if(l.href&&l.href.includes('/app/')&&l.textContent.trim().length>3){"
        "const item=l.closest('gem-nav-list-item');"
        "if(item){"
        "item.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
        "const btns=item.querySelectorAll('button');"
        "if(btns.length){btns[0].click();return'clicked';}"
        "}"
        "break;"
        "}"
        "}"
        "return'no btn';"
        "})()"
    )
    time.sleep(1)
    # Click Rename in dropdown
    _eval_js(
        "(function(){"
        "const items=document.querySelectorAll('[role=\"menuitem\"]');"
        "items.forEach(i=>{if(i.textContent.includes('Rename'))i.click()});"
        "return'rename clicked';"
        "})()"
    )
    time.sleep(0.5)
    # Type new name
    _eval_js(
        "(function(){"
        "const input=document.querySelector('input[type=\"text\"],input:not([type])');"
        "if(!input)return'no input';"
        f"input.value='{new_title}';"
        "input.dispatchEvent(new Event('input',{bubbles:true}));"
        "return'typed';"
        "})()"
    )
    time.sleep(0.5)
    # Click Rename button to confirm
    _eval_js(
        "(function(){"
        "const btns=document.querySelectorAll('button');"
        "for(let i=0;i<btns.length;i++){"
        "if(btns[i].textContent.trim()==='Rename'){btns[i].click();return'confirmed';}"
        "}"
        "return'no rename btn';"
        "})()"
    )
    return f"Session renamed to: {new_title}"


def resume_session_by_title(title: str) -> str:
    """Click a session in sidebar by title to resume it."""
    result = _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('a');"
        "for(let i=0;i<links.length;i++){"
        f"if(links[i].textContent.trim()==='{title}'){{"
        "links[i].click();return'resumed:'+links[i].textContent.trim();"
        "}"
        "}"
        "return'title not found: '+'" + title + "';"
        "})()"
    ).strip().strip('"')
    if 'resumed' in result:
        global _session_active
        _session_active = True
    return result


# ── Document Generation ────────────────────────────────────────────────────

def delegate_to_gemini_document(prompt: str, doc_type: str = "pdf") -> str:
    """
    Ask Gemini to create and download a document. Formats: PDF, MD, XLSX only.
    Returns the download link or local file path.
    """
    type_map = {"pdf": "PDF document", "md": "Markdown document", "xlsx": "Excel spreadsheet"}
    gtype = type_map.get(doc_type, "PDF document")
    err = _setup_chat(temp=False)
    if err: return err
    # Force fresh chat — prevent hallucination from old context
    ref = _find_ref(_snapshot(), 'link', 'new chat')
    if ref:
        _click(ref); time.sleep(3)

    wrapped = (
        f"Create a {gtype} download. Include download link. "
        f"Between {START_MARKER} and {STOP_MARKER}. "
        f"Fresh doc only. Request: {prompt}"
    )
    _inject_text(wrapped); _click_send()

    raw = _poll_for_response()
    if not raw: return "Gemini timed out"
    content = extract_response(raw)

    # Find PDF file element and click it to open viewer
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', prompt[:30].strip())
    timestamp = _datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_el = None
    snap = _snapshot()
    for line in snap.split('\n'):
        if 'generic' in line.lower() and ('pdf' in line.lower() or 'doc' in line.lower()):
            match = re.search(r'\[ref=(\S+)\]', line)
            if match:
                pdf_el = f'@{match.group(1)}'
                break

    if pdf_el:
        _click(pdf_el); time.sleep(4)
        snap2 = _snapshot()
        dl_ref = _find_ref(snap2, 'button', 'download')
        if dl_ref:
            _click(dl_ref)
            time.sleep(3)
            # Check download folder for new PDF
            pdfs = sorted(
                [_os.path.join(DOWNLOAD_PATH, f) for f in _os.listdir(DOWNLOAD_PATH) if f.lower().endswith('.pdf')],
                key=_os.path.getmtime, reverse=True
            )
            # Close PDF viewer
            close_ref = _find_ref(_snapshot(), 'button', 'close')
            if close_ref: _click(close_ref)
            if pdfs:
                return pdfs[0]
        return "PDF document generated — saved via browser download"

    return content[:500]
