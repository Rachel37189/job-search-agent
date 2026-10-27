import pytest

from shared.store import Store
from shared.tools import ToolError, run_tool


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path)


def test_preference_override_replaces_not_merges(store):
    run_tool(store, "save_preference", {"experience_levels": ["junior"], "excluded_roles": ["qa"]})
    out = run_tool(store, "save_preference", {"experience_levels": ["junior", "mid"]})
    prefs = store.load("preferences")
    assert prefs["experience_levels"] == ["junior", "mid"]
    assert prefs["excluded_roles"] == ["qa"]
    assert "['junior'] -> ['junior', 'mid']" in out


def test_application_update_does_not_duplicate(store):
    run_tool(store, "save_application", {"company": "Wix", "role": "Junior Backend Developer", "status": "applied"})
    run_tool(store, "save_application", {"company": "wix", "status": "interview"})
    apps = store.load("applications")
    assert len(apps) == 1 and apps[0]["status"] == "interview"


def test_new_role_same_company_creates_second_application(store):
    run_tool(store, "save_application", {"company": "Wix", "role": "Backend", "status": "applied"})
    run_tool(store, "save_application", {"company": "Wix", "role": "Data", "status": "applied"})
    assert len(store.load("applications")) == 2


def test_search_filters_by_saved_preferences(store):
    run_tool(store, "save_preference", {"experience_levels": ["junior"], "excluded_roles": ["qa"]})
    out = run_tool(store, "search_jobs", {"query": "dev"})
    assert "Junior Python Developer" in out and "Entry Level" in out
    assert "Senior" not in out and "QA" not in out and "React" not in out  # React title has no level -> mid
    run_tool(store, "save_preference", {"experience_levels": ["junior", "mid"]})
    assert "React Frontend Developer" in run_tool(store, "search_jobs", {"query": "dev"})


def test_search_output_is_compact(store):
    out = run_tool(store, "search_jobs", {"query": "dev", "limit": 2})
    assert len(out.splitlines()) <= 3 and len(out) < 400


def test_followups(store):
    run_tool(store, "follow_up", {"action": "add", "company": "Wix", "in_days": 7})
    assert "Wix" in run_tool(store, "follow_up", {"action": "list"})
    run_tool(store, "follow_up", {"action": "done", "company": "Wix"})
    assert run_tool(store, "follow_up", {"action": "list"}) == "no open reminders"


@pytest.mark.parametrize("name,args", [
    ("nope", {}),
    ("save_application", {"company": "X"}),                       # missing status
    ("save_application", {"company": "X", "status": "hired"}),    # not in enum
    ("save_application", {"company": "X", "status": "interview"}),  # update with nothing to update
    ("save_preference", {}),
    ("follow_up", {"action": "add", "company": "X"}),             # missing in_days
    ("search_jobs", {"query": "x", "bogus": 1}),
])
def test_bad_input_raises_tool_error(store, name, args):
    with pytest.raises(ToolError):
        run_tool(store, name, args)


def test_external_failure_becomes_tool_error(store, monkeypatch):
    def boom(q):
        raise OSError("network down")
    monkeypatch.setattr("shared.tools.fetch_jobs", boom)
    with pytest.raises(ToolError, match="jobs API unavailable"):
        run_tool(store, "search_jobs", {"query": "python"})
