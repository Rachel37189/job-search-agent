"""Prompt-cache breakpoints.

Breakpoint 1: on the system block -> caches tools + system (render order tools -> system -> messages).
Breakpoint 2: on the last block of the last message -> caches the whole conversation so far, so the
next model call (next tool round or next turn) reads it from cache.
Markers are added to a copy; the stored history is never modified.
"""
import copy

from harness import log


def system_blocks(system_prompt: str) -> list[dict]:
    return [{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}]


def mark_messages(messages: list[dict]) -> list[dict]:
    msgs = copy.deepcopy(messages)
    last = msgs[-1]["content"][-1]
    last["cache_control"] = {"type": "ephemeral"}
    log(__file__, f"breakpoints: system + message {len(msgs)} ({last['type']})")
    return msgs
