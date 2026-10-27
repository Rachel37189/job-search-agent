"""Token usage and cost per model call and per turn."""
from harness import log
from shared.scenario import cost_usd


class TurnMeter:
    def __init__(self):
        self.usage = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0}
        self.calls = 0
        self.last_context = 0  # prompt size of the latest call, used by compaction.py

    def add(self, usage, label: str = "call") -> None:
        u = {
            "input": usage.input_tokens,
            "cache_read": usage.cache_read_input_tokens or 0,
            "cache_write": usage.cache_creation_input_tokens or 0,
            "output": usage.output_tokens,
        }
        for k, v in u.items():
            self.usage[k] += v
        self.calls += 1
        self.last_context = u["input"] + u["cache_read"] + u["cache_write"]
        log(__file__, f"{label}: in={u['input']} cache_read={u['cache_read']} cache_write={u['cache_write']} "
                      f"out={u['output']} cost=${cost_usd(u):.4f}")

    def summary(self) -> dict:
        return {**self.usage, "model_calls": self.calls, "cost_usd": round(cost_usd(self.usage), 6)}
