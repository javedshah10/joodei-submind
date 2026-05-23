# Security Policy

## Personal Use Only

SubMind is designed for **personal use with your own accounts**. It is not a proxy service, not a shared API gateway, and not intended for multi-user deployment. Each instance should serve exactly one person with their own credentials.

## AgentProfile Isolation

Each platform uses a dedicated Chrome profile directory:

| Platform | Profile Directory | Purpose |
|----------|------------------|---------|
| ChatGPT | `agent-browser-profile` | Isolated ChatGPT session |
| Gemini | `gemini-profile` | Isolated Gemini session |
| Default | `Default` | Not used by SubMind |

Profiles ensure:
- Independent cookie stores (no cross-platform session leaks)
- No contamination of your personal Chrome profile
- Safe deletion without affecting your main browser

## No Credential Storage

SubMind **never stores**:
- ChatGPT/OpenAI passwords or session tokens
- Google/Gemini passwords or OAuth tokens
- Any authentication cookies in files or databases

Credentials live ONLY in Chrome's encrypted profile storage — the same place Chrome normally stores them. SubMind just launches Chrome with the right profile.

## API Keys

The `.env` file may contain:
- `GROQ_API_KEY` — for the optional LLM agent router (`browser_agent.py`)
- `GOOGLE_API_KEY` — optional, for Gemini API fallback

These are never committed, never logged, and never sent to any server. Add `.env` to your `.gitignore`.

## What SubMind Does NOT Do

- Does NOT send your credentials to remote servers
- Does NOT proxy or relay browser sessions
- Does NOT store conversation history on disk (PostgreSQL memory is opt-in, key-value only)
- Does NOT expose HTTP endpoints without explicit configuration (`--transport http`)

## Responsible Disclosure

If you discover a security vulnerability:

1. **Do NOT open a public issue.**
2. Email a detailed report with reproduction steps.
3. Allow 30 days for resolution before public disclosure.

## Chrome Flags

SubMind launches Chrome with these flags for anti-detection and isolation:

```
--disable-blink-features=AutomationControlled
--no-first-run
--no-default-browser-check
```

These minimize bot detection while keeping Chrome fully functional. No flags disable security features (certificate validation, sandbox, site isolation).

## Database

The PostgreSQL memory layer (`memory_brain.py`) stores ONLY:
- Key-value pairs you explicitly save via `memory_save`
- Category and timestamp metadata

No passwords, tokens, or sensitive data should be saved to memory. The `memory_save` tool description explicitly warns against credential storage.
