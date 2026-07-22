"""Summarize a run: trace.jsonl + manifests -> received %, usable %, latency.

Usage: python -m semantic_gateway.summarize --run-dir RUN --manifests M.jsonl
Prints one JSON object; also appends it to RUN/summary.json.
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from .decodability import usable_frames
from .manifest import load_manifests


def summarize(run_dir: Path, manifests_path: Path) -> dict:
    manifests = load_manifests(manifests_path)
    total = received = usable = 0
    lats: list[float] = []
    with open(run_dir / "trace.jsonl") as fh:
        for line in fh:
            rec = json.loads(line)
            m = manifests[rec["video_id"]]
            got = set(rec["received"])
            use = usable_frames(got, m.n_frames)
            total += m.n_frames
            received += len(got)
            usable += len(use)
            lats.extend(ms for _, ms in rec["lat_ms"])
    out = {
        "run_dir": str(run_dir),
        "frames_total": total,
        "frames_received": received,
        "frames_usable": usable,
        "received_pct": round(100 * received / total, 2) if total else 0,
        "usable_pct": round(100 * usable / total, 2) if total else 0,
        "lat_ms_mean": round(statistics.fmean(lats), 2) if lats else None,
        "lat_ms_p99": round(
            statistics.quantiles(lats, n=100)[98], 2) if len(lats) >= 100 else None,
    }
    with open(run_dir / "summary.json", "w") as fh:
        json.dump(out, fh, indent=2)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--manifests", type=Path, required=True)
    args = ap.parse_args()
    print(json.dumps(summarize(args.run_dir, args.manifests), indent=2))


if __name__ == "__main__":
    main()
