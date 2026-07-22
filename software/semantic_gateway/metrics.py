"""Machine-readable run output: every run directory gets run.json (config,
git SHA, seed) plus one or more .jsonl streams. No log scraping."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import IO, Any


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        return "unknown"


def write_run_meta(run_dir: Path, component: str, args: dict[str, Any]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "component": component,
        "git_sha": git_sha(),
        "argv": sys.argv,
        "args": {k: str(v) for k, v in args.items()},
        "started_unix": time.time(),
    }
    with open(run_dir / f"{component}.run.json", "w") as fh:
        json.dump(meta, fh, indent=2)


class JsonlWriter:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh: IO[str] = open(path, "w", buffering=1)

    def write(self, record: dict[str, Any]) -> None:
        self._fh.write(json.dumps(record, separators=(",", ":")) + "\n")

    def close(self) -> None:
        self._fh.close()
