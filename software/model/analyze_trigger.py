"""RQ2: adaptation latency of a run's trigger from events.jsonl.

Reads the proxy event log and reports, per bandwidth step-down:
  - adapt_ms : time from the rate drop to the first pressure escalation
  - drops_in_gap : frames the policy dropped between the step and the reaction
                   (frames stranded because the trigger had not yet reacted)
plus the run's final pressure level and total drops. A faster trigger yields
smaller adapt_ms and fewer drops_in_gap.

  python model\\analyze_trigger.py --run-dir RUN [--out RUN\\trigger.json]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def analyze(run_dir: Path) -> dict:
    events = [json.loads(l) for l in (run_dir / "events.jsonl").read_text().splitlines() if l.strip()]
    rates = [(e["t"], e["bps"]) for e in events if e.get("ev") == "rate"]
    levels = [(e["t"], e["level"]) for e in events if e.get("ev") == "level"]
    drops = [e["t"] for e in events if e.get("ev") == "drop"]
    # overflow drops are logged every time (not sampled): mid-frame queue
    # overflow that severs a reference chain. This is the damage a lagging
    # trigger causes before it reacts.
    overflow = [e["t"] for e in events
                if e.get("ev") == "drop" and e.get("reason") == "overflow"]

    # step-downs: a rate event lower than the previous rate
    stepdowns = []
    for i in range(1, len(rates)):
        if rates[i][1] < rates[i - 1][1]:
            stepdowns.append(rates[i][0])

    results = []
    for t_step in stepdowns:
        up = [t for t, lv in levels if t >= t_step and lv > 0]
        adapt = (up[0] - t_step) if up else None
        gap_drops = sum(1 for t in drops if up and t_step <= t < up[0])
        results.append({"t_step": t_step,
                        "adapt_ms": round(adapt * 1000, 1) if adapt is not None else None,
                        "drops_in_gap": gap_drops})

    trigger = None
    for e in events:
        if e.get("ev") == "level":
            trigger = e.get("trigger")
            break
    # overflow drops between the first step-down and the trigger's reaction
    overflow_in_gap = 0
    if stepdowns:
        t0 = stepdowns[0]
        up = [t for t, lv in levels if t >= t0 and lv > 0]
        if up:
            overflow_in_gap = sum(1 for t in overflow if t0 <= t < up[0])
    summ = next((e for e in events if e.get("ev") == "summary"), {})
    return {"trigger": trigger, "stepdowns": results,
            "overflow_total": len(overflow),
            "overflow_in_gap": overflow_in_gap,
            "level_changes": len(levels),  # stability: fewer = steadier control
            "total_dropped": summ.get("dropped"),
            "final_level": levels[-1][1] if levels else 0}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()
    res = analyze(args.run_dir)
    out = args.out or (args.run_dir / "trigger.json")
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
