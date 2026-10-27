"""Job-search agent on the Claude Agent SDK: Claude Code runs the harness, this file only configures it."""
import json
import time
from pathlib import Path

from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ClaudeSDKClient, ResultMessage, TextBlock,
                              ToolUseBlock)

from shared.prompts import SYSTEM_PROMPT
from shared.store import Store
from tools import SERVER, allowed_names, build_server, write_claude_md


class Agent:
    """One instance per session; state (domain JSON, CLAUDE.md, session id) is loaded from disk."""

    def __init__(self, state_dir: Path, model: str, effort: str):
        self.state_dir = state_dir
        self.workspace = state_dir / "workspace"  # cwd of Claude Code; holds CLAUDE.md
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.store = Store(state_dir / "domain")
        self.session_file = state_dir / "session.json"
        resume = json.loads(self.session_file.read_text())["session_id"] if self.session_file.exists() else None
        write_claude_md(self.store, self.workspace)  # replaces: memory
        self.options = ClaudeAgentOptions(
            model=model,
            effort=effort,
            system_prompt=SYSTEM_PROMPT,  # replaces: context
            tools=[],  # no built-in Claude Code tools at all
            mcp_servers={SERVER: build_server(self.store, self.workspace)},  # replaces: tools
            allowed_tools=allowed_names(),  # replaces: tools
            strict_mcp_config=True,
            permission_mode="dontAsk",  # anything not in allowed_tools is denied, never prompted
            setting_sources=["project"],  # replaces: memory
            cwd=str(self.workspace),  # replaces: memory
            resume=resume,  # replaces: history
            max_turns=12,  # replaces: loop
        )
        self.client = ClaudeSDKClient(self.options)
        print(f"[SDK/agent.py] new agent instance, resume={resume}, model={model}, effort={effort}")

    async def __aenter__(self):
        await self.client.connect()
        return self

    async def __aexit__(self, *exc):
        await self.client.disconnect()

    async def ask(self, text: str) -> dict:
        t0 = time.perf_counter()
        await self.client.query(text)  # replaces: loop
        parts, used, result = [], [], None
        async for msg in self.client.receive_response():  # replaces: loop
            if isinstance(msg, AssistantMessage):
                for b in msg.content:
                    if isinstance(b, TextBlock):
                        parts.append(b.text)
                    elif isinstance(b, ToolUseBlock):
                        used.append(b.name.removeprefix(f"mcp__{SERVER}__"))
                        print(f"[SDK/agent.py] tool call {b.name} {json.dumps(b.input, ensure_ascii=False)[:90]}")
            elif isinstance(msg, ResultMessage):
                result = msg
        self.session_file.write_text(json.dumps({"session_id": result.session_id}))  # replaces: history
        u = result.usage or {}  # replaces: tokens
        return {
            "reply": "\n".join(parts).strip(),
            "tools": used,
            "input": u.get("input_tokens", 0),  # replaces: tokens
            "cache_read": u.get("cache_read_input_tokens", 0),  # replaces: tokens
            "cache_write": u.get("cache_creation_input_tokens", 0),  # replaces: tokens
            "output": u.get("output_tokens", 0),  # replaces: tokens
            "model_calls": result.num_turns,
            "cost_usd_reported": result.total_cost_usd,  # replaces: tokens
            "model_usage": result.model_usage,  # replaces: tokens
            "seconds": round(time.perf_counter() - t0, 2),
            "compacted": False,  # replaces: compaction (automatic inside Claude Code)
        }
