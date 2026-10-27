"""The shared domain tools exposed to Claude Code as an in-process MCP server."""
from pathlib import Path

from claude_agent_sdk import create_sdk_mcp_server, tool

from shared.store import Store
from shared.tools import TOOL_SPECS, ToolError, run_tool

SERVER = "jobs"
MUTATING = {"save_preference", "save_application"}


def write_claude_md(store: Store, workspace: Path) -> None:
    """Memory for the SDK: CLAUDE.md, regenerated from the shared store, loaded by Claude Code at session start."""
    text = ("# Memory (generated from saved state - do not edit)\n\n" + store.memory_text()
            + "\n\nFor details call list_applications / follow_up(action=list).\n")
    (workspace / "CLAUDE.md").write_text(text, encoding="utf-8")  # replaces: memory


def build_server(store: Store, workspace: Path):
    def make(spec):
        @tool(spec["name"], spec["description"], spec["input_schema"])  # replaces: tools
        async def handler(args):
            try:
                text = run_tool(store, spec["name"], args)  # replaces: tools
            except ToolError as e:
                return {"content": [{"type": "text", "text": str(e)}], "is_error": True}  # replaces: tools
            if spec["name"] in MUTATING:
                write_claude_md(store, workspace)  # replaces: memory
            return {"content": [{"type": "text", "text": text}]}  # replaces: tools
        return handler

    tools = [make(s) for s in TOOL_SPECS]
    return create_sdk_mcp_server(name=SERVER, version="1.0.0", tools=tools)  # replaces: tools


def allowed_names() -> list[str]:
    return [f"mcp__{SERVER}__{s['name']}" for s in TOOL_SPECS]  # replaces: tools
