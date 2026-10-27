"""What goes into each turn.

- The system prompt and tools are frozen (cache prefix); nothing per-turn is ever put there.
- Memory goes into the user turn as a <memory> block, and only when it differs from the last
  snapshot the model already saw since the last compaction.
- Application details, job listings and reminders are not injected: the model fetches them with tools.
"""
from harness import log
from harness.history import History
from harness.memory import Memory


def build_user_content(user_text: str, memory: Memory, history: History) -> list[dict]:
    snap = memory.snapshot()
    block = f"<memory>\n{snap}\n</memory>"
    content = []
    if block not in history.texts_since_compaction():
        content.append({"type": "text", "text": block})
        log(__file__, "memory changed or not seen yet -> injected <memory> block")
    else:
        log(__file__, "memory unchanged since last injection -> not repeated")
    content.append({"type": "text", "text": user_text})
    return content
