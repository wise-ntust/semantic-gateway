"""Evaluate every run under a directory tree and collect one results table.

Walks --runs-dir for run subdirectories containing trace.jsonl, runs the
trace evaluator on each (skipping any that already have accuracy.json unless
--force), then writes results.json + results.csv summarizing policy, budget,
seed, top-1, zero-usable count, and the run's own usable_pct from summary.json.

Run naming convention (from experiments/run.sh): <policy>-b<budget>-s<seed>.

  python model\\eval_all.py --runs-dir C:\\...\\sgw-real-smoke ^
      --manifests manifests_test01.jsonl --ucf-dir ...\\UCF-101 ^
      --splits-dir ...\\ucfTrainTestlist --ckpt ckpt\\r2plus1d18_ucf101_seed0.pt
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

RUN_RE = re.compile(r"^(?P<policy>\w+)-b(?P<budget>[\d.]+)-s(?P<seed>\d+)$")


def parse_run_name(name: str) -> dict:
    m = RUN_RE.match(name)
    if not m:
        return {"policy": name, "budget": None, "seed": None}
    return {"policy": m["policy"], "budget": float(m["budget"]),
            "seed": int(m["seed"])}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs-dir", type=Path, required=True)
    ap.add_argument("--manifests", type=Path, required=True)
    ap.add_argument("--ucf-dir", type=Path, required=True)
    ap.add_argument("--splits-dir", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--clips", type=int, default=4)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent
    runs = sorted(d for d in args.runs_dir.iterdir()
                  if (d / "trace.jsonl").exists())
    rows = []
    for run in runs:
        acc_path = run / "accuracy.json"
        if args.force or not acc_path.exists():
            print(f"eval {run.name} ...", flush=True)
            subprocess.run(
                [sys.executable, str(here / "evaluate_trace.py"),
                 "--trace", str(run / "trace.jsonl"),
                 "--manifests", str(args.manifests),
                 "--ucf-dir", str(args.ucf_dir),
                 "--splits-dir", str(args.splits_dir),
                 "--ckpt", str(args.ckpt), "--clips", str(args.clips),
                 "--out", str(acc_path)],
                check=True,
            )
        acc = json.loads(acc_path.read_text())
        meta = parse_run_name(run.name)
        summ = {}
        if (run / "summary.json").exists():
            summ = json.loads((run / "summary.json").read_text())
        rows.append({**meta, "top1": acc["top1"], "n": acc["n"],
                     "zero_usable": acc["zero_usable"],
                     "usable_pct": summ.get("usable_pct"),
                     "received_pct": summ.get("received_pct"),
                     "lat_ms_mean": summ.get("lat_ms_mean"),
                     "lat_ms_p99": summ.get("lat_ms_p99"),
                     "run": run.name})

    rows.sort(key=lambda r: (r["budget"] or 0, r["policy"]))
    (args.runs_dir / "results.json").write_text(json.dumps(rows, indent=2))
    with open(args.runs_dir / "results.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"\n{'policy':<10}{'budget':>7}{'top1':>8}{'usable%':>9}"
          f"{'zero':>6}{'lat_ms':>9}")
    for r in rows:
        print(f"{r['policy']:<10}{r['budget'] or 0:>7}"
              f"{(r['top1'] or 0):>8.3f}{(r['usable_pct'] or 0):>9.1f}"
              f"{r['zero_usable']:>6}{(r['lat_ms_mean'] or 0):>9.0f}")
    print(f"\nwrote {args.runs_dir / 'results.json'} and results.csv")


if __name__ == "__main__":
    main()
