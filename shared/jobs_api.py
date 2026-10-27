"""External tool backend: the free Remotive remote-jobs API (no key).

JOBS_FIXTURE=<path.json> replaces the network call with a local file (offline tests).
Responses are cached on disk for an hour so the API and SDK runs see the same listings.
"""
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://remotive.com/api/remote-jobs"
CACHE_DIR = Path(__file__).parent / "data" / "http_cache"
CACHE_TTL_S = 3600


def fetch_jobs(query: str, limit: int = 50) -> list[dict]:
    fixture = os.environ.get("JOBS_FIXTURE")
    if fixture:
        return json.loads(Path(fixture).read_text(encoding="utf-8"))["jobs"]

    url = f"{URL}?{urllib.parse.urlencode({'search': query, 'limit': limit})}"
    cache = CACHE_DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".json")
    if cache.exists() and time.time() - cache.stat().st_mtime < CACHE_TTL_S:
        return json.loads(cache.read_text(encoding="utf-8"))["jobs"]

    # Remotive answers 403 without a User-Agent.
    req = urllib.request.Request(url, headers={"User-Agent": "job-search-agent/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.load(resp)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"jobs": data.get("jobs", [])}, ensure_ascii=False), encoding="utf-8")
    return data.get("jobs", [])
