"""Long-term memory: preferences + application history in the shared JSON store (state dir on disk).

Writing happens through the save_preference / save_application tools. Reading is a compact snapshot
(one line per item) that context.py injects only when it changed; details come from list_applications.
"""
from harness import log
from shared.store import Store


class Memory:
    def __init__(self, store: Store):
        self.store = store

    def snapshot(self) -> str:
        text = self.store.memory_text()
        log(__file__, f"snapshot read from {self.store.dir.name}/ ({len(text)} chars)")
        return text
