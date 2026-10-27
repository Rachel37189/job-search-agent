"""Run the scenario on the Agent SDK version.

    python SDK/main.py --scenario scenario.json --out results/sdk.json

Runs on your Claude Code login. ANTHROPIC_API_KEY must not be set, or billing moves to that key.
"""
import argparse
import asyncio
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from agent import Agent  # noqa: E402
from shared.scenario import (ROOT, count_replaces, load_scenario, reset_dir, run_checks, summarize,  # noqa: E402
                             utf8_stdout, write_results)
from shared.store import Store  # noqa: E402

STATE = HERE / "state"
PARTS = ["loop", "tools", "history", "memory", "context", "compaction", "caching", "tokens"]


KEYS = {"input": "inputTokens", "cache_read": "cacheReadInputTokens",
        "cache_write": "cacheCreationInputTokens", "output": "outputTokens", "cost_usd": "costUSD"}


def per_turn(rec: dict, prev: dict) -> dict:
    """ResultMessage.model_usage and total_cost_usd are cumulative over the (resumed) session.
    Turn values = difference from the previous turn, summed over every model Claude Code called."""
    cur = rec.pop("model_usage") or {}
    delta = {k: 0 for k in KEYS}
    aux = {}
    for model, mu in cur.items():
        before = prev.get(model, {})
        if any(mu.get(v, 0) < before.get(v, 0) for v in KEYS.values()):
            before = {}  # counter restarted
        d = {k: mu.get(v, 0) - before.get(v, 0) for k, v in KEYS.items()}
        for k in KEYS:
            delta[k] += d[k]
        if model != rec["model"] and any(d.values()):
            aux[model] = {k: round(v, 6) for k, v in d.items()}
    rec["main_loop_usage"] = {k: rec.pop(k) for k in ("input", "cache_read", "cache_write", "output")}
    rec.update({k: round(v, 6) for k, v in delta.items()})
    rec["aux_models"] = aux
    rec.pop("cost_usd_reported")
    return cur


async def run(scenario: dict) -> dict:
    reset_dir(STATE)
    turns, n, prev = [], 0, {}
    for sess in scenario["sessions"]:
        print(f"\n===== session {sess['session']} (new agent instance) =====")
        async with Agent(STATE, scenario["model"], scenario["effort"]) as agent:
            for text in sess["turns"]:
                n += 1
                print(f"\n--- turn {n} --- user: {text}")
                rec = await agent.ask(text)
                rec["model"] = scenario["model"]
                prev = per_turn(rec, prev)  # replaces: tokens
                print(f"assistant: {rec['reply']}")
                print(f"[SDK/main.py] in={rec['input']} cache_read={rec['cache_read']} "
                      f"cache_write={rec['cache_write']} out={rec['output']} calls={rec['model_calls']} "
                      f"cost=${rec['cost_usd']:.4f}")
                turns.append({"session": sess["session"], "turn": n, "user": text, **rec})
    checks = run_checks(scenario, Store(STATE / "domain"), turns)
    tagged = count_replaces([HERE / "agent.py", HERE / "tools.py", HERE / "main.py"])
    loc = {p: tagged.get(p, 0) for p in PARTS}
    return {"version": "sdk", "model": scenario["model"], "effort": scenario["effort"],
            "turns": turns, "totals": summarize(turns), "checks": checks,
            "checks_passed": f"{sum(c['passed'] for c in checks)}/{len(checks)}", "loc": loc}


def main() -> None:
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=str(ROOT / "scenario.json"))
    ap.add_argument("--out", default=str(ROOT / "results" / "sdk.json"))
    args = ap.parse_args()
    if os.environ.pop("ANTHROPIC_API_KEY", None):
        print("[SDK/main.py] ANTHROPIC_API_KEY was set; removed it for this run so the Claude Code login is used")
    result = asyncio.run(run(load_scenario(args.scenario)))
    for c in result["checks"]:
        print(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']}")
    write_results(args.out, result)


if __name__ == "__main__":
    main()
