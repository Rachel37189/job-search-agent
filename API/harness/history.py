"""Conversation history: an append-only JSONL file on disk.

Records: {"type": "message", "role", "content"} and {"type": "compaction", "summary"}.
Nothing is ever rewritten; the messages sent to the model are rebuilt from the last compaction onward.
"""
import json
from pathlib import Path

from harness import log


class History:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.records = []
        if self.path.exists():
            self.records = [json.loads(l) for l in self.path.read_text(encoding="utf-8").splitlines() if l.strip()]
            log(__file__, f"loaded {len(self.records)} records from {self.path.name}")

    def _append(self, rec: dict) -> None:
        self.records.append(rec)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def append(self, role: str, content: list, **meta) -> None:
        """content: list of block dicts. Assistant turns are stored whole (thinking + tool_use + text).
        meta (e.g. context_tokens) is stored next to the message but never sent to the model."""
        blocks = [b if isinstance(b, dict) else b.model_dump(exclude_none=True) for b in content]
        self._append({"type": "message", "role": role, "content": blocks, **meta})

    def last_context_tokens(self) -> int:
        """Prompt size of the latest model call since the last compaction (0 right after one)."""
        for r in reversed(self.records):
            if r["type"] == "compaction":
                return 0
            if "context_tokens" in r:
                return r["context_tokens"]
        return 0

    def append_compaction(self, summary: str) -> None:
        self._append({"type": "compaction", "summary": summary})
        log(__file__, f"appended compaction record ({len(summary)} chars)")

    def messages(self) -> list[dict]:
        """Messages since the last compaction; the summary becomes the first user message.
        Consecutive same-role messages are merged (summary + next user turn)."""
        start, summary = 0, None
        for i, r in enumerate(self.records):
            if r["type"] == "compaction":
                start, summary = i + 1, r["summary"]
        msgs = []
        if summary is not None:
            msgs.append({"role": "user", "content": [
                {"type": "text", "text": f"<conversation_summary>\n{summary}\n</conversation_summary>"}]})
        for r in self.records[start:]:
            if r["type"] != "message":
                continue
            if msgs and msgs[-1]["role"] == r["role"]:
                msgs[-1] = {"role": r["role"], "content": msgs[-1]["content"] + r["content"]}
            else:
                msgs.append({"role": r["role"], "content": list(r["content"])})
        return msgs

    def texts_since_compaction(self) -> list[str]:
        return [b.get("text", "") for m in self.messages() for b in m["content"] if b.get("type") == "text"]
