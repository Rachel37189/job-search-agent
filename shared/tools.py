"""Domain tools shared by both harnesses: JSON schemas + implementations.

Every tool returns a short plain-text string (compact tool output = fewer tokens).
Bad input or a failed external call raises ToolError; each harness turns that into an is_error result.
"""
import datetime as dt
import re

from shared.jobs_api import fetch_jobs
from shared.store import Store

ROLES = ["backend", "fullstack", "frontend", "data", "ai", "qa", "devops", "mobile"]
LEVELS = ["junior", "mid", "senior"]
STATUSES = ["applied", "interview", "offer", "rejected", "withdrawn"]

ROLE_WORDS = {
    "qa": r"\bqa\b|quality assurance|\btest(er|ing)?\b|sdet",
    "devops": r"devops|\bsre\b|site reliability",
    "mobile": r"\bios\b|android|mobile",
}
SENIOR_WORDS = r"senior|\bsr\b|\blead\b|principal|staff|head of|director|manager|architect"
JUNIOR_WORDS = r"junior|\bjr\b|entry|graduate|intern"


class ToolError(Exception):
    """Raised for input the model can fix; sent back as is_error=True."""


TOOL_SPECS = [
    {
        "name": "search_jobs",
        "description": "Search live remote job listings (external Remotive API). Results are already "
                       "filtered by the saved experience_levels and excluded_roles preferences. "
                       "Returns one compact line per job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Keyword, e.g. 'python' or 'react'"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 10, "description": "Max results (default 5)"},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "save_application",
        "description": "Add a job application, or update an existing one (matched by company, and role "
                       "if given). Use it whenever the user reports applying or a status change.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "role": {"type": "string", "description": "Job title. Optional when updating."},
                "status": {"type": "string", "enum": STATUSES},
                "note": {"type": "string"},
            },
            "required": ["company", "status"],
            "additionalProperties": False,
        },
    },
    {
        "name": "list_applications",
        "description": "List saved applications, optionally filtered by status or company.",
        "input_schema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "enum": STATUSES},
                "company": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "save_preference",
        "description": "Save long-term search preferences (memory). Only the fields you pass are "
                       "replaced; a new value overrides the old one, it is not merged.",
        "input_schema": {
            "type": "object",
            "properties": {
                "roles": {"type": "array", "items": {"type": "string", "enum": ROLES}},
                "experience_levels": {"type": "array", "items": {"type": "string", "enum": LEVELS}},
                "work_mode": {"type": "string", "enum": ["remote", "hybrid", "onsite"]},
                "excluded_roles": {"type": "array", "items": {"type": "string", "enum": ROLES}},
                "notes": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "follow_up",
        "description": "Follow-up reminders. action=add needs company and in_days; "
                       "action=list shows open reminders; action=done closes the company's reminders.",
        "input_schema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["add", "list", "done"]},
                "company": {"type": "string"},
                "in_days": {"type": "integer", "minimum": 0, "maximum": 365},
                "note": {"type": "string"},
            },
            "required": ["action"],
            "additionalProperties": False,
        },
    },
]


def _level(title: str) -> str:
    t = title.lower()
    if re.search(SENIOR_WORDS, t):
        return "senior"
    return "junior" if re.search(JUNIOR_WORDS, t) else "mid"


def search_jobs(store: Store, query: str, limit: int = 5) -> str:
    if not query.strip():
        raise ToolError("query must not be empty")
    try:
        jobs = fetch_jobs(query)
    except Exception as e:  # network/HTTP/JSON problems go back to the model, not up the stack
        raise ToolError(f"jobs API unavailable: {type(e).__name__}: {e}") from e
    prefs = store.load("preferences")
    levels = set(prefs.get("experience_levels") or LEVELS)
    excluded = [ROLE_WORDS[r] for r in prefs.get("excluded_roles", []) if r in ROLE_WORDS]
    kept = [j for j in jobs
            if _level(j["title"]) in levels and not any(re.search(p, j["title"].lower()) for p in excluded)]
    lines = [f"{len(kept)} match / {len(jobs)} found for '{query}' (levels={','.join(sorted(levels))})"]
    for j in kept[:limit]:
        salary = f" | {j['salary']}" if j.get("salary") else ""
        lines.append(f"#{j['id']} | {j['title'][:60]} | {j['company_name']} | "
                     f"{(j.get('candidate_required_location') or '?')[:25]}{salary}")
    return "\n".join(lines)


def _norm(s: str) -> str:
    return s.strip().lower()


def save_application(store: Store, company: str, status: str, role: str | None = None, note: str | None = None) -> str:
    if status not in STATUSES:
        raise ToolError(f"status must be one of {STATUSES}")
    apps = store.load("applications")
    same_co = [a for a in apps if _norm(a["company"]) == _norm(company)]
    match = [a for a in same_co if role and _norm(a["role"]) == _norm(role)]
    if not match and len(same_co) == 1 and (not role or status != "applied"):
        match = same_co  # update the only application at that company
    today = dt.date.today().isoformat()
    if match:
        app = match[0]
        app["status"], app["updated"] = status, today
        if note:
            app["note"] = note
        verb = "updated"
    else:
        if not role:
            raise ToolError(f"no application at {company} yet; pass role to create one")
        app = {"company": company.strip(), "role": role.strip(), "status": status, "updated": today}
        if note:
            app["note"] = note
        apps.append(app)
        verb = "added"
    store.save("applications", apps)
    return f"{verb}: {app['company']} | {app['role']} | {app['status']}"


def list_applications(store: Store, status: str | None = None, company: str | None = None) -> str:
    apps = [a for a in store.load("applications")
            if (not status or a["status"] == status) and (not company or _norm(a["company"]) == _norm(company))]
    if not apps:
        return "no applications match"
    return "\n".join(f"{a['company']} | {a['role']} | {a['status']} | {a['updated']}"
                     + (f" | {a['note']}" if a.get("note") else "") for a in apps)


def save_preference(store: Store, **fields) -> str:
    if not fields:
        raise ToolError("pass at least one preference field")
    prefs = store.load("preferences")
    old = {k: prefs.get(k) for k in fields}
    prefs.update(fields)
    store.save("preferences", prefs)
    changes = [f"{k}: {old[k]} -> {v}" if old[k] is not None else f"{k}: {v}" for k, v in fields.items()]
    return "saved " + "; ".join(changes)


def follow_up(store: Store, action: str, company: str | None = None, in_days: int | None = None,
              note: str | None = None) -> str:
    items = store.load("followups")
    today = dt.date.today()
    if action == "add":
        if not company or in_days is None:
            raise ToolError("action=add needs company and in_days")
        due = (today + dt.timedelta(days=in_days)).isoformat()
        items.append({"company": company.strip(), "due": due, "note": note or "", "done": False})
        store.save("followups", items)
        return f"reminder added: {company} on {due}"
    if action == "done":
        if not company:
            raise ToolError("action=done needs company")
        n = 0
        for it in items:
            if not it["done"] and _norm(it["company"]) == _norm(company):
                it["done"], n = True, n + 1
        store.save("followups", items)
        return f"closed {n} reminder(s) for {company}"
    if action == "list":
        open_items = sorted((it for it in items if not it["done"]), key=lambda it: it["due"])
        if not open_items:
            return "no open reminders"
        return "\n".join(f"{it['due']} | {it['company']}" + (f" | {it['note']}" if it["note"] else "")
                         + (" | OVERDUE" if it["due"] < today.isoformat() else "") for it in open_items)
    raise ToolError(f"unknown action {action!r}")


IMPLS = {
    "search_jobs": search_jobs,
    "save_application": save_application,
    "list_applications": list_applications,
    "save_preference": save_preference,
    "follow_up": follow_up,
}


def run_tool(store: Store, name: str, args: dict) -> str:
    """Validate and run one tool. Raises ToolError for anything the model should correct."""
    if name not in IMPLS:
        raise ToolError(f"unknown tool {name!r}")
    spec = next(s for s in TOOL_SPECS if s["name"] == name)["input_schema"]
    missing = [k for k in spec.get("required", []) if k not in args]
    unknown = [k for k in args if k not in spec["properties"]]
    if missing or unknown:
        raise ToolError(f"bad arguments: missing={missing} unknown={unknown}")
    for k, v in args.items():
        enum = spec["properties"][k].get("enum") or spec["properties"][k].get("items", {}).get("enum")
        vals = v if isinstance(v, list) else [v]
        if enum and any(x not in enum for x in vals):
            raise ToolError(f"{k} must be from {enum}")
    try:
        return IMPLS[name](store, **args)
    except TypeError as e:
        raise ToolError(f"bad arguments: {e}") from e
