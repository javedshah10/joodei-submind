"""
joodei_browser_mcp.py — MCP server exposing ChatGPT + Gemini automation as tools.
"""

import sys
import os as _os
_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)

import anyio
from fastmcp import FastMCP, Context

from chatgpt_delegate import (
    delegate_to_chatgpt,
    delegate_to_chatgpt_session,
    delegate_to_chatgpt_image,
    cleanup_image_session,
    get_image_base64,
    get_chatgpt_session_title,
    rename_chatgpt_session_title,
    delete_chatgpt_session,
)

from memory_brain import (
    save_memory,
    search_memory,
    get_memory,
    list_recent,
)

from gemini import (
    delegate_to_gemini,
    delegate_to_gemini_session,
    cleanup_gemini_session,
    delegate_to_gemini_document,
    get_session_title,
    rename_session_title,
    resume_session_by_title,
)

mcp = FastMCP("Joodei Browser Agent")


# ── ChatGPT Tools ──────────────────────────────────────────────────────────

@mcp.tool(description="""Single-shot ChatGPT delegation. Use for quick coding questions,
syntax help, or technical facts.""")
async def chatgpt_query(query: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(delegate_to_chatgpt, query)
        return result
    except anyio.get_cancelled_exc_class():
        return "ChatGPT query cancelled by client."


@mcp.tool(description="""Multi-turn iterative ChatGPT session for complex technical tasks:
advanced code writing, debugging, fixing errors, step-by-step problem
solving. Maintains same chat window across loops. Max 5 loops.

LOOP DISCIPLINE:
- Break task into logical steps — each shaped by prior output.
- After each step: wait 3 mins before extraction. Poll every 19s. Max 5 mins.
- Never advance to next loop until current loop resolved.

EXTRACTION:
  Stage 1: Start:> ... <:End markers (lastIndexOf)
  Stage 2: Full raw response if markers missing
  Never return empty when content exists.

RETRY: Empty after max wait → retry same step ONCE. Log skip if still empty.

STOP: GOAL_ACHIEVED | no progress (2 identical) | blocker | 3 consecutive skips""")
async def chatgpt_session(task: str, max_loops: int = 5, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(
            delegate_to_chatgpt_session, task, max_loops
        )
        return result
    except anyio.get_cancelled_exc_class():
        return "ChatGPT session cancelled by client."


@mcp.tool(description="""Generate an image via ChatGPT DALL-E. Send a single prompt,
waits for generation, saves to chatgpt_images/ folder. Returns absolute file path.
Call chatgpt_image_read(path) to view. Call chatgpt_image_cleanup when done.""")
async def chatgpt_image(prompt: str, iterations: int = 1, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(
            delegate_to_chatgpt_image, prompt, iterations
        )
        return result
    except anyio.get_cancelled_exc_class():
        return "Image generation cancelled by client."


@mcp.tool(description="""Delete the current image generation chat from ChatGPT sidebar
to keep history clean. Call when image is satisfactory.""")
async def chatgpt_image_cleanup(ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(cleanup_image_session)
        return result
    except anyio.get_cancelled_exc_class():
        return "Cleanup cancelled."


@mcp.tool(description="""Read a saved image file and return as base64 data URL.
Use after chatgpt_image to inspect the result.""")
async def chatgpt_image_read(filepath: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(get_image_base64, filepath)
        return result
    except anyio.get_cancelled_exc_class():
        return "Read cancelled."


@mcp.tool(description="""Get the current ChatGPT session title from sidebar.
Use for: identifying active session, resuming conversations.""")
async def chatgpt_get_title(ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(get_chatgpt_session_title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Get title cancelled."


@mcp.tool(description="""Rename the current ChatGPT session in sidebar.
Use for: labeling image generation sessions for future reference.""")
async def chatgpt_rename_title(new_title: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(rename_chatgpt_session_title, new_title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Rename cancelled."


@mcp.tool(description="""Delete a ChatGPT session by title. No args = current.
Use to clean up old image generation chats after saving images.""")
async def chatgpt_delete(title: str = None, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(delete_chatgpt_session, title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Delete cancelled."


# ── Memory Brain Tools ────────────────────────────────────────────────────

@mcp.tool(description="""Save a fact, finding, or decision to persistent local memory
as key-value pair with optional category. Use for: saving important findings,
decisions, code snippets. Never store sensitive credentials.""")
async def memory_save(key: str, value: str, category: str = "general", ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(save_memory, key, value, category)
        return result
    except anyio.get_cancelled_exc_class():
        return "Save cancelled."


@mcp.tool(description="""Search local memory by keyword. Returns matching memories
ordered by recency. Use for: finding previously saved context or decisions.""")
async def memory_search(query: str, category: str = None, limit: int = 10, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(search_memory, query, category, limit)
        return result
    except anyio.get_cancelled_exc_class():
        return "Search cancelled."


@mcp.tool(description="""Retrieve a specific memory by exact key.
Use for: looking up a known saved fact or value.""")
async def memory_get(key: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(get_memory, key)
        return result
    except anyio.get_cancelled_exc_class():
        return "Get cancelled."


@mcp.tool(description="""List most recent memories. Default 5.
Use for: checking what was recently saved or getting memory overview.""")
async def memory_recent(limit: int = 5, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(list_recent, limit)
        return result
    except anyio.get_cancelled_exc_class():
        return "List cancelled."


# ── Gemini Tools ──────────────────────────────────────────────────────────

@mcp.tool(description="""Single-shot with live Google Search. Use for real-time data,
current news, weather, prices, factual lookups. Returns one focused answer.
Do NOT use for coding or multi-step reasoning.""")
async def gemini_query(query: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(delegate_to_gemini, query)
        return result
    except anyio.get_cancelled_exc_class():
        return "Gemini query cancelled by client."


@mcp.tool(description="""Multi-turn research session with live Google Search at every step.
Use for deep research, market analysis, iterative fact-finding, or any
goal requiring follow-up refinement. Maintains context across rounds.
Max 10 rounds. Do NOT use for coding.

ROUND DISCIPLINE:
- Break goal into chained sub-questions — each shaped by prior answer.
- Send ONE sub-question per round. Never batch multiple questions.
- After each round: wait 3 mins before extraction. Poll every 19s. Max 5 mins.
- Never advance to next round until current round resolved.

EXTRACTION:
  Stage 1: Start:> ... <:End markers via lastIndexOf()
  Stage 2: Full raw response if markers missing
  Never return empty when content exists.

RETRY: Empty after max wait → retry same question ONCE. Log skip if still empty.

TRACKING: Round X/10: [question] → [answer or SKIPPED]
Final: synthesized conclusion across all rounds.

STOP: Goal resolved | 10 rounds | 3 consecutive skipped rounds

ROUTING: Single fact → gemini_query. Multi-step → gemini_session""")
async def gemini_session(task: str, max_loops: int = 10, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(
            delegate_to_gemini_session, task, max_loops
        )
        return result
    except anyio.get_cancelled_exc_class():
        return "Gemini session cancelled by client."


@mcp.tool(description="""Delete a Gemini session by title. No args = current.
Pass title to delete specific one.""")
async def gemini_cleanup(title: str = None, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(cleanup_gemini_session, title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Cleanup cancelled."


@mcp.tool(description="""Ask Gemini to create and download a document.
Formats: PDF, MD, XLSX only. Always include provide a download link in the request.
PDF saves to gemini/docs/ via Chrome extension auto-download.
PDF themes (specify in prompt, default Theme 1 if not mentioned):

Theme 1: Clean white, blue accents, formal — for reports, PRDs, handovers
Theme 4: Dark obsidian, emerald highlights — for executive summaries

Always request: professional formatting, proper headings, alignment.""")
async def gemini_document(prompt: str, doc_type: str = "pdf", ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(
            delegate_to_gemini_document, prompt, doc_type
        )
        return result
    except anyio.get_cancelled_exc_class():
        return "Document generation cancelled."


@mcp.tool(description="""Get the current Gemini session title from sidebar.
Use for: identifying active session, resuming conversations.""")
async def gemini_get_title(ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(get_session_title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Get title cancelled."


@mcp.tool(description="""Rename the current Gemini session in sidebar.
Use for: labeling sessions for future reference.""")
async def gemini_rename_title(new_title: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(rename_session_title, new_title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Rename cancelled."


@mcp.tool(description="""Resume an existing Gemini session by clicking its title in sidebar.
Use before gemini_session to continue a previous conversation.
Call gemini_get_title first to see available sessions.""")
async def gemini_resume(title: str, ctx: Context = None) -> str:
    try:
        result = await anyio.to_thread.run_sync(resume_session_by_title, title)
        return result
    except anyio.get_cancelled_exc_class():
        return "Resume cancelled."


if __name__ == "__main__":
    transport = "stdio" if "--transport" in sys.argv and "stdio" in sys.argv else "http"

    while True:
        try:
            if transport == "stdio":
                mcp.run(transport="stdio")
            else:
                mcp.run(transport="http", port=8765)
        except Exception:
            pass
