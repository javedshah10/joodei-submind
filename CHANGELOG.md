# Changelog

## v1.0.0 — Initial Release (May 2026)

### What's Included

**19 MCP tools across 3 platforms:**

| # | Tool | Platform |
|---|------|----------|
| 1 | `chatgpt_query` | ChatGPT single-shot query |
| 2 | `chatgpt_session` | ChatGPT multi-turn session (max 5 loops) |
| 3 | `chatgpt_image` | DALL-E image generation with auto-save |
| 4 | `chatgpt_image_read` | Read saved images as base64 |
| 5 | `chatgpt_image_cleanup` | Delete image generation chat |
| 6 | `chatgpt_get_title` | Get current ChatGPT session title |
| 7 | `chatgpt_rename_title` | Rename ChatGPT session |
| 8 | `chatgpt_delete` | Delete ChatGPT session by title |
| 9 | `memory_save` | Save key-value to PostgreSQL |
| 10 | `memory_search` | Search memories by keyword |
| 11 | `memory_get` | Retrieve memory by exact key |
| 12 | `memory_recent` | List recent memories |
| 13 | `gemini_query` | Gemini single-shot with Google Search |
| 14 | `gemini_session` | Gemini multi-turn research (max 10 rounds) |
| 15 | `gemini_document` | Generate PDF/MD/XLSX document |
| 16 | `gemini_cleanup` | Delete Gemini session |
| 17 | `gemini_get_title` | Get Gemini session title |
| 18 | `gemini_rename_title` | Rename Gemini session |
| 19 | `gemini_resume` | Resume existing Gemini session |

### Key Features

- **Zero bot detection** — Real Chrome with stealth flags and dedicated profiles, not bundled Chromium or headless mode
- **One-time login** — `setup_accounts.py` wizard; sessions persist forever via Chrome profile cookies
- **3-layer response completeness guard** — Busy state detection + stability check + closing marker verification prevents mid-generation partial extraction
- **Self-healing selectors** — Regex-based element discovery with multi-keyword matching; no hardcoded CSS classes or IDs
- **Session persistence** — URL-based conversation detection survives server restart; never lose conversation state
- **Image generation pipeline** — DALL-E generation with JPEG 85% compression (4MB → ~800KB), stabilization loop, whole-page estuary search for extraction
- **Document generation** — Gemini PDF/MD/XLSX via Chrome extension auto-download
- **Crash recovery** — While-true restart loop in MCP server
- **Dual transport** — stdio (Claude Desktop/OpenCode) + HTTP:8765 (testing)
- **Text injection** — Base64 JS for ChatGPT (multiline + Unicode safe), `agent-browser type` for Gemini React rich-textarea

### Known Limitations

- **Gemini text injection** — Must use `agent-browser type` (real keystrokes); JS injection breaks React send button on rich-textarea custom element
- **ChatGPT image mode** — Whole-page estuary search needed; image mode has no `data-message-author-role` attribute
- **Windows only** — Paths use Windows conventions; Chrome profile paths are platform-specific

### File Summary

| File | Lines | Purpose |
|------|-------|---------|
| `joodei_browser_mcp.py` | 307 | FastMCP server with 19 tool wrappers |
| `chatgpt_delegate.py` | 863 | ChatGPT browser automation |
| `gemini.py` | 553 | Gemini browser automation with 3-layer guard |
| `memory_brain.py` | ~120 | PostgreSQL memory CRUD with upsert |
| `browser_agent.py` | ~80 | LLM agent router (optional) |
| `setup_accounts.py` | ~60 | One-time login wizard |
