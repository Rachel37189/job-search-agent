"""Tool schemas for the API request, and dispatch of tool_use blocks to the shared implementations."""
from harness import log
from shared.store import Store
from shared.tools import TOOL_SPECS, ToolError, run_tool


def definitions() -> list[dict]:
    """JSON-schema tool definitions, in a fixed order so the cached prefix never changes."""
    return [dict(spec) for spec in TOOL_SPECS]


def dispatch(store: Store, tool_uses: list) -> list[dict]:
    """Run every tool_use block of one assistant message; all results go back in a single user message."""
    results = []
    for block in tool_uses:
        try:
            text = run_tool(store, block.name, dict(block.input))
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": text})
            log(__file__, f"{block.name}({_short(block.input)}) -> {len(text)} chars")
        except ToolError as e:
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(e), "is_error": True})
            log(__file__, f"{block.name}({_short(block.input)}) -> is_error: {e}")
        except Exception as e:  # a bug in a tool must not kill the conversation
            msg = f"internal tool error: {type(e).__name__}: {e}"
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": msg, "is_error": True})
            log(__file__, f"{block.name} -> is_error: {msg}")
    return results


def _short(args) -> str:
    s = ", ".join(f"{k}={v!r}" for k, v in dict(args).items())
    return s if len(s) < 90 else s[:87] + "..."
