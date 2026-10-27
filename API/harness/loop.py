"""The agent loop: call the model while stop_reason == "tool_use"; all tool_results go back in one message."""
from harness import log
from harness.caching import mark_messages, system_blocks
from harness.history import History
from harness.tokens import TurnMeter
from harness.tools import dispatch
from shared.store import Store

MAX_ROUNDS = 12


def run_turn(client, cfg: dict, tools: list[dict], store: Store, history: History,
             user_content: list[dict], meter: TurnMeter) -> tuple[str, list[str]]:
    history.append("user", user_content)
    used = []
    for rnd in range(1, MAX_ROUNDS + 1):
        resp = client.messages.create(
            model=cfg["model"], max_tokens=16000, output_config={"effort": cfg["effort"]},
            system=system_blocks(cfg["system"]), tools=tools, messages=mark_messages(history.messages()),
        )
        meter.add(resp.usage, f"round {rnd}")
        # whole content: thinking blocks must be replayed unchanged
        history.append("assistant", resp.content, context_tokens=meter.last_context)
        log(__file__, f"round {rnd}: stop_reason={resp.stop_reason}")

        if resp.stop_reason == "tool_use":
            calls = [b for b in resp.content if b.type == "tool_use"]
            used += [b.name for b in calls]
            history.append("user", dispatch(store, calls))
            continue
        if resp.stop_reason == "pause_turn":
            continue
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if resp.stop_reason in ("max_tokens", "refusal"):
            text = text or f"[stopped: {resp.stop_reason}]"
        return text, used
    log(__file__, f"gave up after {MAX_ROUNDS} rounds")
    return "[stopped: too many tool rounds]", used
