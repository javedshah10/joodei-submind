"""
chatgpt_delegate.py — Delegate hard tasks to ChatGPT via real Chrome browser.

Uses agent-browser CLI to automate ChatGPT in the user's REAL Chrome with
their existing profile, bypassing bot detection through:
  - Real Chrome executable (not bundled Chromium)
  - Chrome anti-automation flags (disables navigator.webdriver)
  - Persistent user profile with existing login cookies
  - Headed mode for natural browser fingerprint

Usage:
    from chatgpt_delegate import delegate_to_chatgpt
    answer = delegate_to_chatgpt("What is the latest news on AI agents?")
"""

import subprocess
import time
import sys
import os as _os
import re
import base64

_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))

# ── Configuration ──────────────────────────────────────────────────────────
# Example: r"C:\Users\YourName\AppData\Roaming\npm\agent-browser.cmd"
AGENT_BROWSER = _os.environ.get("AGENT_BROWSER", _os.path.join(_os.path.expanduser("~"), "AppData", "Roaming", "npm", "agent-browser.cmd"))
# Example: r"C:\Program Files\Google\Chrome\Application\chrome.exe"
CHROME_EXE = _os.environ.get("CHROME_EXE", r"C:\Program Files\Google\Chrome\Application\chrome.exe")
# Example: r"C:\Users\YourName\submind-chatgpt-profile"
PROFILE = _os.environ.get("CHATGPT_PROFILE", _os.path.join(_os.path.expanduser("~"), "submind-chatgpt-profile"))
SESSION = "chatgpt"
STEALTH_ARGS = (
    "--disable-blink-features=AutomationControlled,"
    "--no-first-run,"
    "--no-default-browser-check"
)
POLL_INTERVAL = 10
MAX_WAIT = 300

# Session-state tracking — prevents resetting chat between calls
_session_active = False
_image_session_active = False


# ── Numbered Marker System ────────────────────────────────────────────────

def get_markers(loop: int) -> tuple[str, str]:
    """Return (start_marker, stop_marker) for the given loop number.

    Loop 1: START:$  $:STOP
    Loop 2: START1:$ $:STOP1
    Loop 3: START2:$ $:STOP2  etc.
    """
    if loop == 1:
        return "START:$", "$:STOP"
    n = loop - 1
    return f"START{n}:$", f"$:STOP{n}"


def extract_response(raw_text: str, loop: int) -> str:
    """Extract text between loop-specific markers; fallback to raw text."""
    if not raw_text:
        return ""
    start, stop = get_markers(loop)
    pattern = re.compile(re.escape(start) + r"(.+?)" + re.escape(stop), re.DOTALL)
    match = pattern.search(raw_text)
    if match:
        return match.group(1).strip()
    # Markers not found — return raw (ChatGPT may have ignored marker instruction)
    print(f"  [Markers '{start}'/'{stop}' not found, using raw response]", file=sys.stderr)
    return raw_text.strip()


# ── Browser Commands ──────────────────────────────────────────────────────

def _run(args: list[str], timeout: int = 30) -> str:
    """Run an agent-browser CLI command with list args, return stripped stdout."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding='utf-8',
            errors='replace',
        )
        out = (result.stdout or '').strip()
        if not out:
            out = (result.stderr or '').strip()
        if 'ERR_INTERNET_DISCONNECTED' in out or 'ERR_NETWORK' in out:
            return 'CONNECTION_LOST'
        if 'ERR_CONNECTION' in out or 'net::ERR' in out:
            return 'CONNECTION_LOST'
        return out
    except subprocess.TimeoutExpired:
        return ""
    except Exception:
        return "CONNECTION_LOST"


_last_profile = None


def _session(args: list[str], timeout: int = 30) -> str:
    """Run an agent-browser command on the running session."""
    return _run([AGENT_BROWSER, '--session-name', SESSION] + args, timeout=timeout)


def _snapshot() -> str:
    """Take an interactive accessibility snapshot of the page."""
    return _session(['snapshot', '-i'])


def _click(ref: str) -> str:
    """Click an element by its @ref from snapshot."""
    return _session(['click', ref])


def _eval_js(js: str) -> str:
    """Evaluate JavaScript in the browser and return the result."""
    return _session(['eval', js])


def _launch_open() -> str:
    """Launch the browser with stealth flags and navigate to ChatGPT."""
    global _last_profile
    # Only restart daemon when switching between ChatGPT and Gemini profiles
    if _last_profile is not None and _last_profile != PROFILE:
        _run([AGENT_BROWSER, 'close', '--all'], timeout=10)
        time.sleep(2)
    _last_profile = PROFILE

    def _navigate():
        return _run([
            AGENT_BROWSER,
            '--executable-path', CHROME_EXE,
            '--args', STEALTH_ARGS,
            '--headed',
            '--profile', PROFILE,
            '--session-name', SESSION,
            'open', 'https://chatgpt.com',
        ], timeout=60)

    result = _navigate()

    # Auto-fix HTTP 431 — clear cookies and retry
    time.sleep(2)
    snap = _snapshot()
    if 'not working' in snap.lower() or 'http error' in snap.lower():
        _session(['cookies', 'clear', '--url', 'https://chatgpt.com'], timeout=10)
        time.sleep(1)
        result = _navigate()
        time.sleep(3)

    return result


def _find_ref(snapshot: str, role: str, *keywords: str) -> str | None:
    """Find an element's @ref by its ARIA role and text keyword matches.

    Snapshot lines use format: '  - role "name" [ref=e123]'
    We extract 'e123' and return '@e123' for use with click/type commands.
    """
    for line in snapshot.split('\n'):
        lower = line.lower()
        if role.lower() in lower and all(kw.lower() in lower for kw in keywords):
            match = re.search(r'\[ref=(\S+)\]', line)
            if match:
                return f'@{match.group(1)}'
    return None


def _find_input_ref(snap: str) -> str | None:
    """Find the chat input textbox ref in a snapshot."""
    ref = _find_ref(snap, 'textbox', 'chat')
    if not ref:
        ref = _find_ref(snap, 'textbox', 'message')
    return ref


# ── Chat Setup ────────────────────────────────────────────────────────────

def _setup_chat() -> str | None:
    """Open ChatGPT, check login, start new temp chat, return error or None."""
    _launch_open()

    # Wait for page to fully load — poll snapshot until input box appears
    for _ in range(15):
        time.sleep(2)
        snap = _snapshot()
        if _find_input_ref(snap): break
    else:
        return "ChatGPT page did not load — try again"

    # Check login
    if 'log in' in snap.lower() or 'sign up' in snap.lower():
        # Retry — page may still be rendering
        for _ in range(3):
            time.sleep(3)
            snap = _snapshot()
            if _find_input_ref(snap) and 'log in' not in snap.lower() and 'sign up' not in snap.lower():
                break
        else:
            return "ChatGPT not logged in — please login manually first"

    # Start fresh chat
    new_chat_ref = _find_ref(snap, 'link', 'new chat')
    if new_chat_ref:
        _click(new_chat_ref)
        time.sleep(2)
        snap = _snapshot()

    # Enable temporary chat
    temp_ref = _find_ref(snap, 'button', 'temporary')
    if not temp_ref:
        temp_ref = _find_ref(snap, 'button', 'temp')
    if temp_ref:
        _click(temp_ref)
        time.sleep(1)
    else:
        for line in snap.split('\n'):
            if 'button' in line.lower() and 'temporary' in line.lower():
                match = re.search(r'\[ref=(\S+)\]', line)
                if match:
                    _click(f'@{match.group(1)}')
                    time.sleep(1)
                    break

    return None  # success


def _inject_text(text: str) -> None:
    """Type text into the contenteditable div via base64-encoded JavaScript.
    Verifies injection before returning — critical for production reliability."""
    encoded = base64.b64encode(text.encode('utf-8')).decode('ascii')
    for attempt in range(3):
        _eval_js(
            "(function(){"
            f"const raw=atob('{encoded}');"
            "const bytes=new Uint8Array(raw.length);"
            "for(let i=0;i<raw.length;i++)bytes[i]=raw.charCodeAt(i);"
            "const text=new TextDecoder('utf-8').decode(bytes);"
            "const div=document.querySelector('div[contenteditable=\"true\"]');"
            "if(!div)return'no-div';"
            "div.focus();"
            "div.innerHTML=text.replace(/\\n/g,'<br>');"
            "div.dispatchEvent(new Event('input',{bubbles:true}));"
            "return'typed:'+div.textContent.length;"
            "})()"
        )
        time.sleep(2)
        check = _eval_js(
            "const d=document.querySelector('div[contenteditable=\"true\"]');"
            "return d?d.textContent.length:0"
        ).strip().strip('"')
        try:
            if int(check) > 10:
                return  # Verified
        except ValueError: pass
        print(f"  [Injection retry {attempt+1}]", file=sys.stderr)
    print(f"  [WARNING: Injection unverified after 3 attempts]", file=sys.stderr)


def _click_send() -> None:
    """Click the ChatGPT send button via JavaScript."""
    _eval_js(
        "(function(){"
        "const btn=document.querySelector('[data-testid=\"send-button\"]');"
        "if(!btn)return'no-send-btn';"
        "btn.click();"
        "return'sent';"
        "})()"
    )


def _poll_for_response() -> str:
    """Poll for ChatGPT response; returns raw assistant text or empty string."""
    last_text = ""
    stable_count = 0

    for _ in range(MAX_WAIT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        snap = _snapshot()

        # Internet lost — wait and retry before giving up
        if 'CONNECTION_LOST' in snap:
            print("  [Connection lost, retrying...]", file=sys.stderr)
            for retry in range(10):
                time.sleep(5)
                snap = _snapshot()
                if 'CONNECTION_LOST' not in snap:
                    print("  [Connection restored!]", file=sys.stderr)
                    break
            else:
                return snap  # Still lost after 50s — give up
            continue

        # Check UI for active work indicators — only match BUTTONS, not response text
        is_busy = (
            _find_ref(snap, 'button', 'stop streaming') is not None or
            _find_ref(snap, 'button', 'stop generating') is not None
        )
        if is_busy:
            print("  [ChatGPT still working... waiting]", file=sys.stderr)
            stable_count = 0
            continue

        # "Continue generating" button
        cg = _find_ref(snap, 'button', 'continue')
        if cg:
            _click(cg)
            stable_count = 0
            continue

        # Check if assistant response exists and is stable
        current_text = _eval_js(
            "(function(){"
            # Try text-mode selector first
            "let msgs=document.querySelectorAll('[data-message-author-role=\"assistant\"]');"
            "if(msgs.length)return msgs[msgs.length-1].textContent.trim();"
            # Image mode fallback — check for estuary images
            "const imgs=document.querySelectorAll('img[src*=\"estuary\"]');"
            "if(imgs.length)return'[IMAGE_GENERATED]'+(imgs.length);"
            # Nothing yet
            "return\"\";"
            "})()"
        )

        if current_text and current_text == last_text and len(current_text) > 10:
            stable_count += 1
            if stable_count >= 2:
                return current_text
        elif current_text:
            last_text = current_text
            stable_count = 0

    return last_text


# ── Single-Query Delegate ─────────────────────────────────────────────────

def delegate_to_chatgpt(query: str) -> str:
    """
    Delegate a single question to ChatGPT. Opens a fresh temp chat,
    sends the query with concise-answer markers, and returns the answer.
    """
    err = _setup_chat()
    if err:
        return err

    # Ensure we're in text mode — reload page if image-mode UI is present
    snap = _snapshot()
    if 'Explore ideas' in snap:
        _session(['open', 'https://chatgpt.com/'])
        time.sleep(4)
        err = _setup_chat()
        if err:
            return err

    # Find input
    snap = _snapshot()
    input_ref = _find_input_ref(snap)
    retries = 0
    while not input_ref and retries < 2:
        time.sleep(3)
        snap = _snapshot()
        input_ref = _find_input_ref(snap)
        retries += 1
    if not input_ref:
        return "ChatGPT input box not found"

    # Build query with loop-1 markers
    start, stop = get_markers(1)
    wrapped = (
        f"Put your answer between: {start} and {stop}\n"
        f"Example: {start} your answer here {stop}\n\n"
        f"Question: {query}\n\n"
        "Rules:\n"
        "- Shortest complete answer (<=10 words facts, <=50 moderate, <=500 complex)\n"
        "- No filler, no openings, no repetition\n"
        "- Use web search if current info needed"
    )

    _inject_text(wrapped)
    _click_send()

    result = _poll_for_response()
    if not result:
        return "ChatGPT timed out after 3 minutes"
    if 'CONNECTION_LOST' in result:
        return "Internet connection lost"

    return extract_response(result, 1)


# ── Multi-Turn Session Delegate ───────────────────────────────────────────

def _should_continue(response: str, last_response: str, loop: int, max_loops: int) -> bool:
    """Decide whether to continue the session loop.

    Returns False to stop, True to send another follow-up.
    """
    if loop >= max_loops:
        return False
    if "GOAL_ACHIEVED" in response:
        return False
    if response.strip() == last_response.strip():
        print("  [No progress detected — stopping session]", file=sys.stderr)
        return False

    blockers = ["i cannot", "i don't know", "unable to", "i am unable", "not possible"]
    if any(b in response.lower() for b in blockers):
        print("  [ChatGPT indicated it cannot help — stopping session]", file=sys.stderr)
        return False

    continuers = ["next step", "now do", "part 1", "continued",
                  "please provide", "error", "fix", "issue",
                  "try this", "here's", "here is"]
    if any(c in response.lower() for c in continuers):
        return True

    return False


def delegate_to_chatgpt_session(task: str, max_loops: int = 7) -> str:
    """
    Maintain a single ChatGPT chat window across multiple exchanges until
    the goal is achieved, progress stalls, or max_loops reached.

    On first call: opens ChatGPT, starts fresh chat, enables temp mode.
    On subsequent calls: continues the SAME chat — preserves full history.
    """
    global _session_active

    if not _session_active:
        err = _setup_chat()
        if err:
            return err
        # Ensure text mode (not leftover image mode)
        snap = _snapshot()
        if 'Explore ideas' in snap:
            _session(['open', 'https://chatgpt.com/'])
            time.sleep(4)
            err = _setup_chat()
            if err:
                return err
        _session_active = True

    response = ""
    last_response = ""

    for loop in range(1, max_loops + 1):
        print(f"  [Session loop {loop}/{max_loops}]", file=sys.stderr)
        start, stop = get_markers(loop)

        # Find input in current chat window
        snap = _snapshot()
        input_ref = _find_input_ref(snap)
        retries = 0
        while not input_ref and retries < 2:
            time.sleep(2)
            snap = _snapshot()
            input_ref = _find_input_ref(snap)
            retries += 1
        if not input_ref:
            return "ChatGPT input box not found during session"

        # Build and send message
        if loop == 1:
            msg = (
                f"You are helping solve a task iteratively.\n"
                f"When fully complete, include GOAL_ACHIEVED at the very end.\n"
                f"Wrap response: {start} (response) {stop}\n"
                f"Keep under 500 words. Use web search if needed.\n\n"
                f"Task: {task}"
            )
        else:
            msg = (
                f"Continue improving. Wrap in: {start} (response) {stop}\n"
                f"Include GOAL_ACHIEVED when complete. Under 500 words.\n\n"
                f"Original task: {task}\n"
                f"Your last response: {last_response[:400]}\n\n"
                f"Improve, fix issues, or continue. Be specific."
            )

        _inject_text(msg)
        _click_send()

        raw = _poll_for_response()
        if not raw:
            return "ChatGPT timed out during session"
        if 'CONNECTION_LOST' in raw:
            return "Internet connection lost"

        response = extract_response(raw, loop)
        print(f"  [Loop {loop} response: {response[:120]}...]", file=sys.stderr)

        # GOAL_ACHIEVED — done
        if "GOAL_ACHIEVED" in response:
            clean = response.replace("GOAL_ACHIEVED", "").strip()
            print(f"  [GOAL_ACHIEVED at loop {loop}]", file=sys.stderr)
            return clean

        # Check guard — should we continue?
        if not _should_continue(response, last_response, loop, max_loops):
            print(f"  [Session complete at loop {loop}]", file=sys.stderr)
            return response

        last_response = response

    return response


# ── Image Generation Delegate ─────────────────────────────────────────────

import os as _os
import base64 as _base64


def _setup_chat_image() -> str | None:
    """Open ChatGPT, check login, start new regular chat, enter image mode."""
    global _image_session_active
    if _image_session_active:
        # Already in image session — skip navigation
        return None
    _launch_open()
    time.sleep(6)

    snap = _snapshot()
    if 'log in' in snap.lower() or 'sign up' in snap.lower():
        return "ChatGPT not logged in — please login manually first"

    # Check if already inside a conversation (e.g., after MCP restart)
    url = _eval_js('window.location.href').strip('"')
    if '/c/' in url:
        print("  [Already in a chat, reusing session]", file=sys.stderr)
        return None

    new_chat_ref = _find_ref(snap, 'link', 'new chat')
    if new_chat_ref:
        _click(new_chat_ref)
        time.sleep(3)
        snap = _snapshot()

    create_img_ref = None
    for _ in range(3):
        create_img_ref = _find_ref(snap, 'button', 'create an image')
        if not create_img_ref:
            create_img_ref = _find_ref(snap, 'button', 'create')
        if create_img_ref:
            break
        time.sleep(2)
        snap = _snapshot()

    if create_img_ref:
        _click(create_img_ref)
        time.sleep(2)

    return None


def _extract_and_save_images(folder: str, name: str) -> list[str]:
    """Extract generated images from DOM via canvas, save to folder."""
    _os.makedirs(folder, exist_ok=True)
    saved = []
    seen_srcs = set()

    for idx in range(4):
        b64 = _eval_js(
            f"(function(){{"
            # Find estuary images anywhere — image mode has no data-role attrs
            f"const allImgs=document.querySelectorAll('img[src*=\"estuary\"]');"
            f"if(!allImgs.length)return'';"
            f"const large=[];"
            f"const seen=new Set();"
            f"allImgs.forEach(i=>{{"
            f"if(i.width>200&&!seen.has(i.src)){{seen.add(i.src);large.push(i)}}"
            f"}});"
            f"if({idx}>=large.length)return'';"
            f"const img=large[{idx}];"
            f"try{{"
            f"const c=document.createElement('canvas');"
            f"c.width=img.naturalWidth;c.height=img.naturalHeight;"
            f"c.getContext('2d').drawImage(img,0,0);"
            f"return c.toDataURL('image/jpeg',0.85);"
            f"}}catch(e){{return'error:'+e.message}}"
            f"}})()"
        )
        # Strip JSON wrapping quotes from agent-browser eval output
        b64 = b64.strip().strip('"')
        if not b64 or not b64.startswith('data:image'):
            break
        # Decode base64
        try:
            header, data = b64.split(',', 1)
            img_bytes = _base64.b64decode(data)
            fname = f"{name}_{idx+1}.jpg" if idx > 0 else f"{name}.jpg"
            filepath = _os.path.join(folder, fname)
            with open(filepath, 'wb') as f:
                f.write(img_bytes)
            saved.append(filepath)
        except Exception as e:
            print(f"  [Save error: {e}]", file=sys.stderr)
    return saved


def delegate_to_chatgpt_image(prompt: str, iterations: int = 1) -> str:
    """
    Generate images via ChatGPT's DALL-E integration.
    On first call: opens new chat, clicks 'Create an image'.
    On subsequent calls: continues in SAME chat for iteration.
    Saves to chatgpt_images/ folder, returns comma-separated file paths.

    iterations: max extraction retries (not prompt count).
    For different prompts, call this function multiple times.
    """
    global _image_session_active

    if not _image_session_active:
        err = _setup_chat_image()
        if err:
            return err
        _image_session_active = True

    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', prompt[:30].strip())
    # Example: r"C:\Users\YourName\submind\chatgpt_images"
    folder = _os.environ.get("CHATGPT_IMAGES_PATH", _os.path.join(_os.path.expanduser("~"), "submind", "chatgpt_images"))

    print(f"  [Image generation: {prompt[:60]}...]", file=sys.stderr)

    # Find input and send ONE prompt
    snap = _snapshot()
    input_ref = _find_input_ref(snap)
    if not input_ref:
        return "ChatGPT input box not found"

    _inject_text(prompt)
    _click_send()

    raw = _poll_for_response()
    if not raw:
        return "ChatGPT timed out"
    if 'CONNECTION_LOST' in raw:
        return "Internet connection lost"

    # Wait for image to fully load, retry extraction
    img_name = f"{safe_name}_1"
    for retry in range(iterations * 10):
        time.sleep(3)
        # Wait for images to stabilize (count stops changing for 10s)
    prev_count = 0
    for retry in range(10):
        time.sleep(5)
        cur = int(_eval_js(
            "document.querySelectorAll('img[src*=\"estuary\"]').length"
        ).strip().strip('"') or '0')
        if cur == prev_count and cur > 0:
            break
        prev_count = cur
    
    saved = _extract_and_save_images(folder, img_name)
    if saved:
        print(f"  [Saved {len(saved)} image(s)]", file=sys.stderr)
        return ", ".join(saved)
    if retry % 5 == 4:
        print(f"  [Waiting for image render... {retry+1}/{iterations*10}]", file=sys.stderr)

    return "No images generated"


def cleanup_image_session() -> str:
    """Delete the current image chat from ChatGPT sidebar. Call when done."""
    global _image_session_active
    if not _image_session_active:
        return "No active image session"

    result = _eval_js(
        "(function(){"
        # Find any conversation link in sidebar (not system links)
        "const nav=document.querySelector('nav');"
        "if(!nav)return'no nav';"
        "const links=nav.querySelectorAll('a[href*=\"/c/\"]');"
        "if(!links.length)return'no conv links';"
        # Get the first conversation (most recent)
        "const link=links[0];"
        "const li=link.closest('li');"
        "if(!li)return'no li';"
        # Find the three-dot button within this li
        "const btn=li.querySelector('button');"
        "if(!btn)return'no button';"
        "btn.click();"
        "return'clicked menu on: '+link.textContent.substring(0,30);"
        "})()"
    )
    print(f"  [Cleanup menu: {result}]", file=sys.stderr)

    # Wait for dropdown, click Delete
    time.sleep(1)
    _eval_js(
        "(function(){"
        "const items=document.querySelectorAll('[role=\"menuitem\"]');"
        "items.forEach(i=>{if(i.textContent.includes('Delete'))i.click()});"
        "return'delete clicked';"
        "})()"
    )

    # Wait for confirmation, click confirm
    time.sleep(0.5)
    _eval_js(
        "(function(){"
        "const all=document.querySelectorAll('button');"
        "all.forEach(b=>{if(b.textContent.trim()==='Delete')b.click()});"
        "return'confirmed';"
        "})()"
    )

    _image_session_active = False
    print(f"  [Image session deleted]", file=sys.stderr)
    return "Session deleted"


def get_image_base64(filepath: str) -> str:
    """Read a saved image and return as base64 data URL. For MCP clients."""
    if not _os.path.exists(filepath):
        return f"File not found: {filepath}"
    try:
        with open(filepath, 'rb') as f:
            data = _base64.b64encode(f.read()).decode('ascii')
        ext = _os.path.splitext(filepath)[1].lower().lstrip('.')
        mime = 'image/png' if ext in ('', 'png') else f'image/{ext}'
        return f"data:{mime};base64,{data}"
    except Exception as e:
        return f"Error reading image: {e}"


def get_chatgpt_session_title() -> str:
    """Get active ChatGPT session title from sidebar."""
    titles = _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('nav a');"
        "for(let i=0;i<links.length;i++){"
        "const t=links[i].textContent.trim();"
        "const h=links[i].href||'';"
        "if(t.length>3&&h.includes('/c/'))return t;"
        "}"
        "return'';"
        "})()"
    ).strip().strip('"')
    return titles or "No active session"


def rename_chatgpt_session_title(new_title: str) -> str:
    """Rename ChatGPT session in sidebar. Hover+click 3-dot."""
    _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('nav a');"
        "for(const l of links){"
        "if(l.href&&l.href.includes('/c/')&&l.textContent.trim().length>3){"
        "const li=l.closest('li');"
        "if(li){"
        "li.dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
        "const btns=li.querySelectorAll('button');"
        "if(btns.length){btns[btns.length-1].click();return'clicked';}"
        "}"
        "break;"
        "}"
        "}"
        "return'no btn';"
        "})()"
    )
    time.sleep(1)
    _eval_js(
        "(function(){"
        "const items=document.querySelectorAll('[role=\"menuitem\"]');"
        "items.forEach(i=>{if(i.textContent.includes('Rename'))i.click()});"
        "})()"
    )
    time.sleep(0.5)
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
    _eval_js(
        "(function(){"
        "const btns=document.querySelectorAll('button');"
        "for(let i=0;i<btns.length;i++){"
        "if(btns[i].textContent.trim()==='Rename'){btns[i].click();return'confirmed';}"
        "}"
        "return'no rename btn';"
        "})()"
    )
    return f"Renamed to: {new_title}"


def resume_chatgpt_session(title: str) -> str:
    """Click a ChatGPT session in sidebar by title to resume."""
    result = _eval_js(
        "(function(){"
        "const links=document.querySelectorAll('nav a');"
        "for(let i=0;i<links.length;i++){"
        f"if(links[i].textContent.trim()==='{title}'){{"
        "links[i].click();return'resumed';"
        "}"
        "}"
        "return'not found';"
        "})()"
    ).strip().strip('"')
    return f"Resumed: {title}" if 'resumed' in result else f"Not found: {title}"


def delete_chatgpt_session(title: str = None) -> str:
    """Delete a ChatGPT session by title. Hover+click 3-dot."""
    for attempt in range(2):
        _eval_js(
            "(function(){"
            "const links=document.querySelectorAll('nav a');"
            "for(let i=0;i<links.length;i++){"
            "const t=links[i].textContent.trim();"
            f"if(t.length>3&&('{title}'===''||t==='{title}')){{"
            "links[i].dispatchEvent(new MouseEvent('mouseover',{bubbles:true}));"
            "return'hovered';"
            "}"
            "}"
            "return'no match';"
            "})()"
        )
        time.sleep(1)
        _eval_js(
            "(function(){"
            "const btns=document.querySelectorAll('button');"
            "for(let i=0;i<btns.length;i++){"
            f"const label=btns[i].getAttribute('aria-label')||'';"
            f"if(label.includes('{title}')||label.includes('conversation options')){{"
            "btns[i].click();return'clicked';"
            "}"
            "}"
            "return'no options btn';"
            "})()"
        )
        time.sleep(0.5)
        _eval_js(
            "(function(){"
            "const items=document.querySelectorAll('[role=\"menuitem\"]');"
            "items.forEach(i=>{if(i.textContent.includes('Delete'))i.click()});"
            "})()"
        )
        time.sleep(1)
        return f"Deleted: {title or 'current'}"
    return f"Failed to delete {title or 'current'}"


# ── CLI entry point ────────────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = sys.argv[1]
    else:
        query = input("Enter your query: ")

    answer = delegate_to_chatgpt(query)
    try:
        print(answer)
    except UnicodeEncodeError:
        print(answer.encode('ascii', errors='replace').decode('ascii'))
