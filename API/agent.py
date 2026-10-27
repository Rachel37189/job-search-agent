"""Job-search agent on the raw Messages API: wires the harness parts together."""
import time
from pathlib import Path

from harness import log
from harness.compaction import compact, should_compact
from harness.context import build_user_content
from harness.history import History
from harness.loop import run_turn
from harness.memory import Memory
from harness.tokens import TurnMeter
from harness.tools import definitions
from shared.prompts import SYSTEM_PROMPT
from shared.store import Store

COMPACT_THRESHOLD_TOKENS = 12000


class Agent:
    """One instance per session. Everything it knows on start comes from state_dir on disk."""

    def __init__(self, client, state_dir: Path, model: str, effort: str):
        self.client = client
        self.store = Store(state_dir / "domain")
        self.memory = Memory(self.store)
        self.history = History(state_dir / "history.jsonl")
        self.tools = definitions()
        self.cfg = {"model": model, "effort": effort, "system": SYSTEM_PROMPT,
                    "compact_threshold": COMPACT_THRESHOLD_TOKENS}
        log(__file__, f"new agent instance, state={state_dir.name}/, model={model}, effort={effort}")

    def ask(self, text: str) -> dict:
        t0 = time.perf_counter()
        meter = TurnMeter()
        meter.last_context = self.history.last_context_tokens()
        compacted = should_compact(meter.last_context, COMPACT_THRESHOLD_TOKENS)
        if compacted:
            compact(self.client, self.cfg, self.tools, self.history, meter)
        content = build_user_content(text, self.memory, self.history)
        reply, used = run_turn(self.client, self.cfg, self.tools, self.store, self.history, content, meter)
        return {"reply": reply, "tools": used, "compacted": compacted,
                "seconds": round(time.perf_counter() - t0, 2), **meter.summary()}
