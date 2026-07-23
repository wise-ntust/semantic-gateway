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
        return None, None, None
    mean = statistics.fmean(xs)
    med = statistics.median(xs)
    sd = statistics.stdev(xs) if len(xs) > 1 else 0.0
    return mean, med, sd


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
        adapts, ovf_total, lvl_changes = [], [], []
        per_run = []
        for run in sorted(d for d in root.iterdir() if (d / "events.jsonl").exists()):
            res = analyze(run)
            (run / "trigger.json").write_text(json.dumps(res, indent=2))
            for sd in res["stepdowns"]:
                if sd["adapt_ms"] is not None:
                    adapts.append(sd["adapt_ms"])
            ovf_total.append(res["overflow_total"])
            lvl_changes.append(res["level_changes"])
            per_run.append({"run": run.name, **res})
        a_m, a_med, a_s = stat(adapts)
        ot_m, ot_med, _ = stat(ovf_total)
        lc_m, lc_med, _ = stat(lvl_changes)
        report[label] = {"n_runs": len(per_run), "n_adapted": len(adapts),
                         "adapt_ms_mean": a_m, "adapt_ms_median": a_med,
                         "adapt_ms_std": a_s,
                         "overflow_total_mean": ot_m, "overflow_total_median": ot_med,
                         "level_changes_mean": lc_m, "level_changes_median": lc_med,
                         "runs": per_run}

    args.out.write_text(json.dumps(report, indent=2))
    print(f"{'trigger':<10}{'adapted':>8}{'adapt_ms(med)':>16}"
          f"{'ovf_total':>11}{'lvl_chg':>9}")
    for label, r in report.items():
        a = (f"{r['adapt_ms_median']:.0f} (mu{r['adapt_ms_mean']:.0f})"
             if r["adapt_ms_median"] is not None else "NA")
        print(f"{label:<10}{r['n_adapted']:>3}/{r['n_runs']:<4}{a:>16}"
              f"{r['overflow_total_mean']:>11.0f}{r['level_changes_median']:>9.0f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
