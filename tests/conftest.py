import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT), str(ROOT / "API")]
os.environ["JOBS_FIXTURE"] = str(ROOT / "tests" / "fixtures" / "jobs.json")
