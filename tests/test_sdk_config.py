"""SDK version without running Claude Code: tool handlers, CLAUDE.md memory, options, LOC tags."""
import asyncio
import importlib.util
import sys
from pathlib import Path

from shared.scenario import ROOT, count_replaces
from shared.store import Store

SDK = ROOT / "SDK"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"sdk_{name}", SDK / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SDK))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(SDK))
    return mod


def test_tool_handlers_errors_and_memory(tmp_path):
    tools = _load("tools")
    store = Store(tmp_path / "domain")
    ws = tmp_path / "ws"
    ws.mkdir()
    assert tools.build_server(store, ws)["type"] == "sdk"
    bad = asyncio.run(_call(tools, store, ws, "save_application", {"company": "X", "status": "hired"}))
    assert bad["is_error"] is True
    ok = asyncio.run(_call(tools, store, ws, "save_preference", {"experience_levels": ["junior"]}))
    assert "is_error" not in ok
    assert "experience_levels: junior" in (ws / "CLAUDE.md").read_text(encoding="utf-8")


async def _call(tools, store, ws, name, args):
    """Find the SdkMcpTool built for `name` and invoke its handler."""
    captured = []
    real = tools.create_sdk_mcp_server
    tools.create_sdk_mcp_server = lambda name, version, tools: captured.extend(tools) or {"type": "sdk"}
    try:
        tools.build_server(store, ws)
    finally:
        tools.create_sdk_mcp_server = real
    t = next(t for t in captured if t.name == name)
    return await t.handler(args)


def test_options_are_restricted(tmp_path):
    agent = _load("agent")
    a = agent.Agent(tmp_path, "claude-opus-5-5", "medium")
    o = a.options
    assert o.tools == [] and o.strict_mcp_config is True and o.setting_sources == ["project"]
    assert o.model == "claude-opus-5-5" and o.effort == "medium" and o.permission_mode == "dontAsk"
    assert all(n.startswith("mcp__jobs__") for n in o.allowed_tools) and len(o.allowed_tools) == 5
    assert o.system_prompt.startswith("You are a job-search assistant")
    assert (Path(o.cwd) / "CLAUDE.md").exists() and o.resume is None


def test_replaces_tags_counted():
    counts = count_replaces([SDK / "agent.py", SDK / "tools.py", SDK / "main.py"])
    for part in ["loop", "tools", "history", "memory", "context", "tokens"]:
        assert counts.get(part, 0) > 0, part
