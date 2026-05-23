# SubMind — Stop paying for intelligence twice.

SubMind is a production-ready MCP (Model Context Protocol) server that gives your AI coding agent direct, browser-automated access to ChatGPT, Gemini, and a persistent PostgreSQL memory layer — all through 19 tools with no API keys needed for the LLM platforms.

Your AI agent already runs on an expensive model. Why pay again for ChatGPT/Gemini APIs? SubMind opens real Chrome, types into real text boxes, clicks real send buttons — and extracts the response via JavaScript injection with a 3-layer completeness guard.

## Features

| Category | Tools | Description |
|----------|-------|-------------|
| **ChatGPT** | 8 tools | Query, session, image generation, image I/O, session management |
| **Gemini** | 7 tools | Query, session, document generation, session management, resume |
| **Memory** | 4 tools | Save, search, retrieve, list recent — SQLite/PostgreSQL-backed |

## Quick Start

### 1. Install dependencies
```bash
pip install -r requirements.txt
npm install -g agent-browser
```

### 2. Set up Chrome profiles (one-time)
```bash
python setup_accounts.py
```
Opens ChatGPT → you log in → press Enter. Opens Gemini → you log in → press Enter. Sessions persist forever via Chrome profile cookies.

### 3. Verify paths
Copy `.env.example` to `.env` and review the defaults. All paths default to `%USERPROFILE%` subdirectories — customize only if your Chrome or agent-browser is installed in a non-standard location.

### 4. Connect to Your AI Client

SubMind works with any MCP-compatible AI client.
Add the following to your client's MCP config:

```json
{
  "mcpServers": {
    "submind": {
      "command": "python",
      "args": ["-u", "path/to/submind/joodei_browser_mcp.py", "--transport", "stdio"],
      "env": {"PYTHONUNBUFFERED": "1"}
    }
  }
}
```

| Client | Config File Location |
|--------|---------------------|
| Claude Desktop | `%APPDATA%\Claude\claude_desktop_config.json` |
| Claude Code | `claude mcp add submind python path/to/joodei_browser_mcp.py` |
| OpenCode | `opencode.json` in project root |
| Cursor | `.cursor/mcp.json` in project root |
| Windsurf | `~/.codeium/windsurf/mcp_config.json` |
| Any MCP client | HTTP mode: `python joodei_browser_mcp.py` → `http://localhost:8765` |

See [docs/setup.md](docs/setup.md) for detailed per-client instructions.

## Platform Support

| Platform | Status | Capabilities |
|----------|--------|-------------|
| ChatGPT | Stable | Query, session (5 loops), DALL-E images, session management |
| Gemini | Stable | Query, session (10 rounds), PDF/MD/XLSX docs, session management |

## Token Efficiency

| Approach | Tokens per task | Context window impact |
|----------|----------------|----------------------|
| **SubMind (browser)** | ~100 (tool call) + response text | Zero — agent delegates, doesn't read |
| Direct API call | Full conversation in context | High — every exchange fills window |
| Embedded web views | 2-5K per page parse | Moderate — scraped DOM bloat |

SubMind saves ~90% of context tokens by keeping your agent as orchestrator, not participant.

## Architecture

```
┌──────────────────────────────────────────────┐
│                 Your AI Agent                 │
│  (Claude / OpenCode / Cursor / Windsurf /     │
│           Any MCP Client)                      │
└──────────────────┬───────────────────────────┘
                   │ MCP protocol (stdio/HTTP)
┌──────────────────▼───────────────────────────┐
│           joodei_browser_mcp.py               │
│          FastMCP server — 19 tools            │
├────────┬──────────────┬──────────────────────┤
│ ChatGPT│   Gemini     │   Memory Brain        │
│delegate│  delegate    │   (SQLite/PostgreSQL) │
├────────┴──────────────┴──────────────────────┤
│           agent-browser (Node)                │
│      Chrome CDP — real browser control        │
├──────────────────────────────────────────────┤
│         Google Chrome (2 profiles)            │
│  chatgpt-profile | gemini-profile             │
└──────────────────────────────────────────────┘
```

### Key Design Decisions

- **Real Chrome only** — no headless, no bundled Chromium. Anti-detection via `--disable-blink-features=AutomationControlled` + dedicated profiles.
- **3-layer response guard** — busy-state detection → stability check → closing marker verification. Prevents mid-generation partial extraction.
- **Self-healing selectors** — regex-based `_find_ref()` with multi-keyword matching. Survives DOM class/attribute changes.
- **Session persistence** — URL-based conversation detection survives server restart. No conversation state lost.
- **Profile isolation** — separate Chrome profiles per platform ensure independent sessions and cookie stores.

## Files

| File | Role |
|------|------|
| `joodei_browser_mcp.py` | MCP server exposing 19 tools via FastMCP |
| `chatgpt_delegate.py` | ChatGPT browser automation (863 lines) |
| `gemini.py` | Gemini browser automation (553 lines) |
| `memory_brain.py` | SQLite/PostgreSQL memory with zero-setup fallback |
| `setup_accounts.py` | One-time Chrome profile login wizard |
| `.env.example` | Environment configuration template |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for how to add new platform adapters, self-healing selector guidelines, and the 3-layer response guard specification.

## License

MIT — for personal use only with your own accounts. See [LICENSE](LICENSE).

## Disclaimer

This tool automates YOUR OWN browser with YOUR OWN accounts. It is not a proxy, not a shared service, and not for resale. You are responsible for complying with each platform's Terms of Service. The authors assume no liability for account restrictions, bans, or data loss.
