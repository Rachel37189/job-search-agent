"""Run the scenario on the raw-API version.

    python API/main.py --scenario scenario.json --out results/api.json

Needs ANTHROPIC_API_KEY in the environment (Claude Console key; never in code or git).
"""
import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

from agent import Agent  # noqa: E402
from shared.scenario import (ROOT, count_loc, load_scenario, reset_dir, run_checks, summarize,  # noqa: E402
                             utf8_stdout, write_results)
from shared.store import Store  # noqa: E402

STATE = HERE / "state"


def run(scenario: dict, make_client) -> dict:
    reset_dir(STATE)
    turns, n = [], 0
    for sess in scenario["sessions"]:
        print(f"\n===== session {sess['session']} (new agent instance) =====")
        agent = Agent(make_client(), STATE, scenario["model"], scenario["effort"])
        for text in sess["turns"]:
            n += 1
            print(f"\n--- turn {n} --- user: {text}")
            rec = agent.ask(text)
            print(f"assistant: {rec['reply']}")
            turns.append({"session": sess["session"], "turn": n, "user": text, **rec})
    checks = run_checks(scenario, Store(STATE / "domain"), turns)
    harness_dir = HERE / "harness"
    loc = {p.stem: count_loc(p) for p in sorted(harness_dir.glob("*.py")) if p.stem != "__init__"}
    loc["agent+main"] = count_loc(HERE / "agent.py") + count_loc(HERE / "main.py")
    return {"version": "api", "model": scenario["model"], "effort": scenario["effort"],
            "turns": turns, "totals": summarize(turns), "checks": checks,
            "checks_passed": f"{sum(c['passed'] for c in checks)}/{len(checks)}", "loc": loc}


def main() -> None:
    utf8_stdout()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", default=str(ROOT / "scenario.json"))
    ap.add_argument("--out", default=str(ROOT / "results" / "api.json"))
    args = ap.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set. Set it in this terminal only (never in code).")
    import anthropic
    result = run(load_scenario(args.scenario), anthropic.Anthropic)
    for c in result["checks"]:
        print(f"[{'PASS' if c['passed'] else 'FAIL'}] {c['id']}: {c['observed']}")
    write_results(args.out, result)


if __name__ == "__main__":
    main()
