"""Persistent domain state (preferences, applications, follow-ups) as JSON files in one state dir.

Both harnesses use this exact store, so the pass/fail checks read the same files in both versions.
"""
import json
import os
from pathlib import Path

FILES = ("preferences", "applications", "followups")


class Store:
    def __init__(self, state_dir: str | os.PathLike):
        self.dir = Path(state_dir)
        self.dir.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        return self.dir / f"{name}.json"

    def load(self, name: str):
        p = self._path(name)
        if not p.exists():
            return {} if name == "preferences" else []
        return json.loads(p.read_text(encoding="utf-8"))

    def save(self, name: str, data) -> None:
        tmp = self._path(name).with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        tmp.replace(self._path(name))

    def memory_text(self) -> str:
        """Compact memory snapshot: preferences + one line per application. Used by both harnesses."""
        prefs = self.load("preferences")
        apps = self.load("applications")
        lines = ["## Saved preferences"]
        lines += [f"- {k}: {', '.join(v) if isinstance(v, list) else v}" for k, v in sorted(prefs.items())] or ["- (none yet)"]
        lines.append("## Applications (company | role | status)")
        lines += [f"- {a['company']} | {a['role']} | {a['status']}" for a in apps] or ["- (none yet)"]
        return "\n".join(lines)
