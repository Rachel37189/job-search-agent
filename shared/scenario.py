"""Scenario runner pieces shared by both main.py files: loading, pass/fail checks, LOC counting, results file."""
import json
import re
import shutil
import sys
from pathlib import Path

from shared.store import Store

ROOT = Path(__file__).resolve().parent.parent

# Opus 5.5 list prices, USD per 1M tokens (cache write = 5-minute TTL, 1.25x input).
PRICES = {"input": 4.00, "cache_write": 5.00, "cache_read": 0.20, "output": 20.00}


def utf8_stdout() -> None:
    """Windows consoles default to a legacy code page that cannot print Hebrew."""
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def load_scenario(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def reset_dir(path: Path) -> None:
    """Every run starts from a clean state."""
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True)


def cost_usd(usage: dict) -> float:
    return sum(usage.get(k, 0) * PRICES[k] for k in PRICES) / 1_000_000


def _lookup(store: Store, path: str):
    name, _, field = path.partition(".")
    data = store.load(name)
    return data.get(field) if field else data


def run_checks(scenario: dict, store: Store, turns: list[dict]) -> list[dict]:
    """Evaluate the scenario's checks against the saved state (mostly) and the turn log."""
    out = []
    for c in scenario["checks"]:
        kind = c["type"]
        if kind == "state_set_equals":
            got = _lookup(store, c["path"]) or []
            ok = sorted(got) == sorted(c["value"])
        elif kind == "state_contains":
            got = _lookup(store, c["path"]) or []
            ok = c["value"] in got
        elif kind == "application":
            got = [a for a in store.load("applications") if a["company"].lower() == c["company"].lower()]
            ok = len(got) == c.get("count", 1) and all(a["status"] == c["status"] for a in got)
        elif kind == "open_followup":
            got = [f for f in store.load("followups") if f["company"].lower() == c["company"].lower() and not f["done"]]
            ok = len(got) >= 1
        elif kind == "tool_used_in_sessions":
            got = sorted({t["session"] for t in turns if c["tool"] in t["tools"]})
            ok = got == sorted(c["sessions"])
        elif kind == "reply_mentions":
            reply = next(t["reply"] for t in turns if t["turn"] == c["turn"])
            got = {name: any(re.search(a, reply, re.I) for a in alts) for name, alts in c["any_of"].items()}
            ok = all(got.values())
        else:
            raise ValueError(f"unknown check type {kind}")
        out.append({"id": c["id"], "description": c["description"], "passed": bool(ok), "observed": got})
    return out


def count_loc(path: Path) -> int:
    """Non-blank lines that are not pure comments or docstring-only lines."""
    n, in_doc = 0, False
    for line in path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if in_doc:
            in_doc = not (s.endswith('"""') or s.endswith("'''"))
            continue
        if s.startswith(('"""', "'''")):
            in_doc = not (len(s) > 3 and (s.endswith('"""') or s.endswith("'''")))
            continue
        if s and not s.startswith("#"):
            n += 1
    return n


def count_replaces(paths: list[Path]) -> dict[str, int]:
    """SDK side: lines tagged `# replaces: <part>` per harness part."""
    counts: dict[str, int] = {}
    for p in paths:
        for line in p.read_text(encoding="utf-8").splitlines():
            m = re.search(r"#\s*replaces:\s*([\w, ]+)", line)
            if m:
                for part in (x.strip() for x in m.group(1).split(",")):
                    counts[part] = counts.get(part, 0) + 1
    return counts


def summarize(turns: list[dict]) -> dict:
    keys = ["input", "cache_read", "cache_write", "output", "model_calls", "cost_usd", "seconds"]
    tot = {k: round(sum(t[k] for t in turns), 6) for k in keys}
    all_in = tot["input"] + tot["cache_read"] + tot["cache_write"]
    tot["cache_hit_pct"] = round(100 * tot["cache_read"] / all_in, 1) if all_in else 0.0
    return tot


def write_results(out: str, payload: dict) -> None:
    p = Path(out)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[shared/scenario.py] wrote {p}")
