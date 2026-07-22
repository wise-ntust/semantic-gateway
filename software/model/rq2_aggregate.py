"""RQ2: aggregate per-run trigger analyses across seeds, per trigger.

Walks two run trees (one per trigger), runs analyze_trigger on each run that
lacks trigger.json, then reports mean +/- std of adaptation latency and
drops-in-gap for each trigger. A faster trigger has lower both.

  python model\\rq2_aggregate.py --dirs queue=PATH1 feedback=PATH2 --out OUT.json
"""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

from analyze_trigger import analyze


def stat(xs):
    xs = [x for x in xs if x is not None]
    if not xs:
        return None, None
    return statistics.fmean(xs), (statistics.stdev(xs) if len(xs) > 1 else 0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True,
                    help="label=path pairs, e.g. queue=/tmp/q feedback=/tmp/f")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    report = {}
    for pair in args.dirs:
        label, path = pair.split("=", 1)
        root = Path(path)
        adapts, gaps = [], []
        per_run = []
        for run in sorted(d for d in root.iterdir() if (d / "events.jsonl").exists()):
            res = analyze(run)
            (run / "trigger.json").write_text(json.dumps(res, indent=2))
            for sd in res["stepdowns"]:
                if sd["adapt_ms"] is not None:
                    adapts.append(sd["adapt_ms"])
                gaps.append(sd["drops_in_gap"])
            per_run.append({"run": run.name, **res})
        a_m, a_s = stat(adapts)
        g_m, g_s = stat(gaps)
        report[label] = {"n_runs": len(per_run),
                         "adapt_ms_mean": a_m, "adapt_ms_std": a_s,
                         "drops_in_gap_mean": g_m, "drops_in_gap_std": g_s,
                         "runs": per_run}

    args.out.write_text(json.dumps(report, indent=2))
    print(f"{'trigger':<10}{'runs':>6}{'adapt_ms':>16}{'drops_in_gap':>16}")
    for label, r in report.items():
        a = f"{r['adapt_ms_mean']:.0f}±{r['adapt_ms_std']:.0f}" if r["adapt_ms_mean"] is not None else "NA"
        g = f"{r['drops_in_gap_mean']:.0f}±{r['drops_in_gap_std']:.0f}" if r["drops_in_gap_mean"] is not None else "NA"
        print(f"{label:<10}{r['n_runs']:>6}{a:>16}{g:>16}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
