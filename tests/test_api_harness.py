import json

import agent as api_agent
import main as api_main
from fake_client import RuleClient, ScriptedClient, message, text, tool_use
from harness.history import History
from shared.scenario import ROOT, load_scenario


def make_agent(tmp_path, client):
    return api_agent.Agent(client, tmp_path, "claude-opus-5-5", "medium")


def test_loop_runs_tools_and_returns_all_results_in_one_message(tmp_path):
    client = ScriptedClient([
        message([{"type": "thinking", "thinking": "", "signature": "sig"},
                 tool_use("save_preference", {"work_mode": "remote"}),
                 tool_use("save_application", {"company": "X", "status": "hired"})], "tool_use"),
        message([text("done")], "end_turn"),
    ])
    rec = make_agent(tmp_path, client).ask("hi")
    assert rec["reply"] == "done" and rec["model_calls"] == 2
    assert rec["tools"] == ["save_preference", "save_application"]
    second = client.requests[1]["messages"]
    results = second[-1]["content"]
    assert [b["type"] for b in results] == ["tool_result", "tool_result"]
    assert results[1]["is_error"] is True and "status must be" in results[1]["content"]
    # thinking block replayed unchanged
    assert second[-2]["content"][0] == {"type": "thinking", "thinking": "", "signature": "sig"}


def test_request_settings_and_cache_breakpoints(tmp_path):
    client = ScriptedClient([message([text("ok")], "end_turn")])
    make_agent(tmp_path, client).ask("hi")
    req = client.requests[0]
    assert req["model"] == "claude-opus-5-5" and req["output_config"] == {"effort": "medium"}
    assert req["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert req["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    # the stored history never carries cache markers
    assert "cache_control" not in (tmp_path / "history.jsonl").read_text(encoding="utf-8")


def test_history_is_append_only_and_reloads(tmp_path):
    client = ScriptedClient([message([text("a")], "end_turn"), message([text("b")], "end_turn")])
    ag = make_agent(tmp_path, client)
    ag.ask("one")
    before = (tmp_path / "history.jsonl").read_text(encoding="utf-8")
    ag.ask("two")
    after = (tmp_path / "history.jsonl").read_text(encoding="utf-8")
    assert after.startswith(before)
    reloaded = History(tmp_path / "history.jsonl").messages()
    assert [m["role"] for m in reloaded] == ["user", "assistant", "user", "assistant"]


def test_memory_injected_only_when_changed(tmp_path):
    client = ScriptedClient([
        message([text("a")], "end_turn"),
        message([text("b")], "end_turn"),
        message([tool_use("save_preference", {"work_mode": "remote"})], "tool_use"),
        message([text("c")], "end_turn"),
        message([text("d")], "end_turn"),
    ])
    ag = make_agent(tmp_path, client)
    for q in ["1", "2", "3", "4"]:
        ag.ask(q)
    def first_block(i):
        return client.requests[i]["messages"][-1]["content"][0]["text"]
    assert first_block(0).startswith("<memory>")      # first turn: injected
    assert first_block(1) == "2"                      # unchanged: not repeated
    assert first_block(4).startswith("<memory>")      # after save_preference: injected again
    assert "work_mode: remote" in first_block(4)


def test_compaction_over_threshold_replaces_history_with_summary(tmp_path, monkeypatch):
    monkeypatch.setattr(api_agent, "COMPACT_THRESHOLD_TOKENS", 1000)
    client = ScriptedClient([
        message([text("a")], "end_turn", inp=2000),
        message([text("SUMMARY")], "end_turn"),
        message([text("b")], "end_turn"),
    ])
    ag = make_agent(tmp_path, client)
    ag.ask("one")
    rec = ag.ask("two")
    assert rec["compacted"] and rec["model_calls"] == 2
    msgs = client.requests[2]["messages"]
    assert len(msgs) == 1 and "SUMMARY" in msgs[0]["content"][0]["text"]
    assert msgs[0]["content"][-1]["text"] == "two"
    assert "thinking" not in json.dumps(msgs)


def test_full_scenario_offline_passes_all_checks():
    result = api_main.run(load_scenario(ROOT / "scenario.json"), RuleClient)
    failed = [c for c in result["checks"] if not c["passed"]]
    assert not failed, failed
    assert len(result["turns"]) == 8 and result["totals"]["cost_usd"] > 0
    assert set(result["loc"]) >= {"loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"}
