"""Context-window management: when the prompt passes a threshold, summarize the whole conversation.

Simple compaction: one summary replaces everything; no earlier turns or thinking blocks are replayed
(required for Opus 5.5's preserved-thinking check). Only runs between turns, never mid tool round.
The summary request keeps the same system + tools so it reuses the prompt cache.
"""
from harness import log
from harness.caching import mark_messages, system_blocks
from harness.history import History
from harness.tokens import TurnMeter

SUMMARY_PROMPT = (
    "The conversation is getting long. Write a compact summary that will replace everything above. "
    "Keep: the user's stated goals and preferences (latest values only), every company/role/status mentioned, "
    "reminders, which job searches ran and what was found, and any open question. "
    "Drop greetings and repeated tool output. Do not call any tools; respond with only the summary text."
)


def should_compact(last_context_tokens: int, threshold: int) -> bool:
    return last_context_tokens > threshold


def compact(client, cfg: dict, tools: list[dict], history: History, meter: TurnMeter) -> None:
    log(__file__, f"context {meter.last_context} > {cfg['compact_threshold']} tokens -> summarizing conversation")
    msgs = history.messages() + [{"role": "user", "content": [{"type": "text", "text": SUMMARY_PROMPT}]}]
    resp = client.messages.create(
        model=cfg["model"], max_tokens=4000, output_config={"effort": cfg["effort"]},
        system=system_blocks(cfg["system"]), tools=tools, messages=mark_messages(msgs),
    )
    meter.add(resp.usage, "compaction")
    summary = "".join(b.text for b in resp.content if b.type == "text").strip()
    history.append_compaction(summary)
