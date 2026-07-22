"""Aggregate results.json (per-run rows) across seeds -> mean +/- std.

Groups by (policy, budget), reports mean and sample std of top-1, usable_pct,
and latency across seeds, plus the seed count. Writes agg.json + agg.csv next
to the input and prints a table ready for the results write-up.

  python model\\aggregate.py --results C:\\...\\sweep\\results.json
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path


def stats(xs: list[float]) -> tuple[float | None, float | None]:
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    mean = statistics.fmean(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return mean, sd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", type=Path, required=True)
    args = ap.parse_args()
    rows = json.loads(args.results.read_text())

    groups: dict[tuple, list] = defaultdict(list)
    for r in rows:
        groups[(r["policy"], r["budget"])].append(r)

    out = []
    for (policy, budget), rs in sorted(groups.items(),
                                       key=lambda kv: (kv[0][1] or 0, kv[0][0])):
        t_m, t_s = stats([r["top1"] for r in rs])
        u_m, u_s = stats([r["usable_pct"] for r in rs])
        l_m, l_s = stats([r["lat_ms_mean"] for r in rs])
        out.append({"policy": policy, "budget": budget, "seeds": len(rs),
                    "top1_mean": t_m, "top1_std": t_s,
                    "usable_mean": u_m, "usable_std": u_s,
                    "lat_mean": l_m, "lat_std": l_s})

    (args.results.parent / "agg.json").write_text(json.dumps(out, indent=2))
    with open(args.results.parent / "agg.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)

    print(f"{'policy':<10}{'budget':>7}{'seeds':>6}{'top1':>16}{'usable%':>14}")
    for r in out:
        t = f"{r['top1_mean']:.3f}±{r['top1_std']:.3f}" if r["top1_mean"] is not None else "NA"
        u = f"{r['usable_mean']:.1f}±{r['usable_std']:.1f}" if r["usable_mean"] is not None else "NA"
        print(f"{r['policy']:<10}{r['budget'] or 0:>7}{r['seeds']:>6}{t:>16}{u:>14}")
    print(f"\nwrote {args.results.parent / 'agg.json'} and agg.csv")


if __name__ == "__main__":
    main()
