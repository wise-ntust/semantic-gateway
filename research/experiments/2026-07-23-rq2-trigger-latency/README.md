# RQ2 — trigger signal: queue-depth vs loss-feedback (2026-07-23)

When bandwidth drops, does a link-local queue-depth signal drive adaptation
better than an application-layer loss-feedback signal (H2)?

This is a **characterization**, not a headline claim. H2 was flagged at G1 as
the hardest hypothesis to test in emulation: `tc netem` cannot produce real
link-layer signals (retry / MCS), so the definitive test is deferred to
hardware (H5). What we can test here is the *shape* of the two control signals.

## Setup

- Semantic policy held constant; only the trigger differs.
- 24 videos, speed 1 (real-time, so trigger constants map to real AP time),
  5 seeds. AP queue = 100 ms of link rate.
- Bandwidth schedule: 60 KB/s → **18 KB/s at t=15 s** → 60 KB/s at t=35 s
  (a congestion episode then recovery).
- queue trigger: escalate when occupancy > 0.7 for 0.3 s, de-escalate < 0.25.
  feedback trigger: fast-up / slow-down on receiver loss reports (every 0.5 s).

## Result

See `../figures/rq2_pressure_over_time.png` for one representative pair.

| trigger | behaviour at ample bandwidth (0–15 s) | under congestion (15–35 s) | after recovery (35 s+) | level changes |
|---------|:-------------------------------------:|:--------------------------:|:----------------------:|:-------------:|
| queue-depth | steady at 0 | escalates to 3 (~196 ms median) | returns to ~0 | 16–24 |
| loss-feedback | already oscillating 0↔3 | ~2, still bouncing | keeps oscillating 2↔3, never settles to 0 | 75–83 |

overflow drops = 0 for both in this scenario.

## Takeaway

- **Queue-depth is a clean control signal.** Idle (level 0) when bandwidth is
  ample, escalates within ~200 ms when the link drops, and returns toward 0
  when bandwidth recovers. It tracks the true backlog.
- **Loss-feedback is chronically unstable.** It oscillates across the whole
  run — including *before* any congestion, when bandwidth is ample — and never
  settles back to no-pressure after recovery (75–83 level changes vs 16–24).
  The reason is fundamental, not a tuning bug: the receiver's loss estimate
  conflates three things it cannot tell apart — the AP's *intended* semantic
  drops, transient I-frame-burst loss, and real *congestion*. Any of them reads
  as "loss," so a loss-driven controller chases its own tail. Queue occupancy
  reflects the real backlog regardless of policy drops, so it has no confound
  and a stable operating point (its hysteresis dead-band).

## Claim status: H2 partially supported (characterization)

The defensible positive result is the **queue-depth trigger's clean behaviour**:
fast, stable, self-correcting. The loss-feedback arm illustrates *why* a local
signal is preferable — the end-to-end signal is confounded — but it is not a
tuned production controller, and the emulated `adapt_ms` is too noisy for a
precise "N× faster" claim (feedback is already oscillating before the step; the
queue arm has one content-driven 3.0 s outlier at seed 3). The definitive
trigger comparison, using real retry / MCS / queue signals, is **H5 on
hardware**. H2 was flagged at G1 as the hardest hypothesis to emulate; this
result is consistent with that and does not overreach.

## Limitations

- `tc netem` gives propagation delay only; no real link-layer signal.
- adapt_ms contaminated by pre-step oscillation (feedback) and content-driven
  queue fill rate (queue seed-3 outlier). Median reported, not mean.
- No overflow differentiation in this scenario (both 0).

## Provenance

- `rq2_agg.json`: per-trigger aggregate + per-run detail
- `traces.tgz`: all 10 runs (queue/feedback x 5 seeds), events + trigger.json
- `sweep.log`: raw run log; analysis via `model/analyze_trigger.py`
