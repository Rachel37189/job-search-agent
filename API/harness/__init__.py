"""Hand-written harness for the raw Messages API. One file per responsibility."""
from pathlib import Path


def log(file: str, msg: str) -> None:
    """Every runtime action is printed with the harness file that performed it."""
    print(f"[harness/{Path(file).name}] {msg}", flush=True)
