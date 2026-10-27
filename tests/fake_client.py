"""A mock Anthropic client: no key, no network. Returns real anthropic.types.Message objects.

`ScriptedClient` replays a fixed list of responses. `RuleClient` plays a tiny rule-based "model" that
reacts to the latest user text, so the whole two-session scenario can run offline.
"""
import itertools
import json

from anthropic.types import Message

_ids = itertools.count(1)


def message(content: list[dict], stop_reason: str, inp=100, out=20, read=0, write=0) -> Message:
    return Message.model_validate({
        "id": f"msg_{next(_ids)}", "type": "message", "role": "assistant", "model": "claude-opus-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": inp, "output_tokens": out,
                  "cache_read_input_tokens": read, "cache_creation_input_tokens": write},
    })


def tool_use(name: str, args: dict) -> dict:
    return {"type": "tool_use", "id": f"toolu_{next(_ids)}", "name": name, "input": args}


def text(t: str) -> dict:
    return {"type": "text", "text": t}


class _Messages:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kw):
        self.owner.requests.append(json.loads(json.dumps(kw, default=str)))
        return self.owner.respond(kw)


class ScriptedClient:
    def __init__(self, responses: list[Message]):
        self.responses = list(responses)
        self.requests = []
        self.messages = _Messages(self)

    def respond(self, kw):
        return self.responses.pop(0)


def _last_user_text(msgs: list[dict]) -> tuple[str, bool]:
    """(text of the latest real user turn, whether the latest message is a tool_result)."""
    last = msgs[-1]["content"]
    is_result = any(b.get("type") == "tool_result" for b in last)
    for m in reversed(msgs):
        texts = [b["text"] for b in m["content"] if b.get("type") == "text" and not b["text"].startswith("<memory>")]
        if m["role"] == "user" and texts:
            return texts[-1], is_result
    return "", is_result


class RuleClient(ScriptedClient):
    """Keyword rules standing in for the model; one tool round per turn, then a short reply."""

    RULES = [
        ("תשמור את ההעדפות", [("save_preference", {"roles": ["backend", "fullstack", "frontend", "data", "ai"],
                                                  "experience_levels": ["junior"], "work_mode": "remote",
                                                  "excluded_roles": ["qa"]})]),
        ("משרות Python", [("search_jobs", {"query": "python"})]),
        ("הגשתי מועמדות", [("save_application", {"company": "Wix", "role": "Junior Backend Developer", "status": "applied"}),
                           ("save_application", {"company": "Monday", "role": "Junior Data Analyst", "status": "applied"})]),
        ("תזכיר לי", [("follow_up", {"action": "add", "company": "Wix", "in_days": 7})]),
        ("מה ההעדפות שלי", [("list_applications", {})]),
        ("זימון לראיון", [("save_application", {"company": "Wix", "status": "interview"})]),
        ("mid-level", [("save_preference", {"experience_levels": ["junior", "mid"]}), ("search_jobs", {"query": "react"})]),
        ("התזכורות", [("follow_up", {"action": "list"})]),
    ]

    def __init__(self):
        super().__init__([])

    def respond(self, kw):
        msgs = kw["messages"]
        if "Do not call any tools" in json.dumps(msgs[-1], ensure_ascii=False):
            return message([text("summary: prefs junior+remote, applied Wix and Monday")], "end_turn", inp=50, out=30)
        user, after_tools = _last_user_text(msgs)
        if after_tools:
            results = [b["content"] for b in msgs[-1]["content"]]
            return message([text("סיכום: " + " / ".join(results))], "end_turn", inp=900, read=600, out=40)
        for key, calls in self.RULES:
            if key in user:
                return message([tool_use(n, a) for n, a in calls], "tool_use", inp=800, read=500, write=300)
        return message([text("לא הבנתי")], "end_turn")
