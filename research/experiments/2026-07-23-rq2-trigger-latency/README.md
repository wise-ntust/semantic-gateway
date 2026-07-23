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

| trigger | adapt to step (median) | level changes | recovered after step-up? |
|---------|:----------------------:|:-------------:|:------------------------:|
| queue-depth | **196 ms** (4/5 runs 112–315 ms) | 16–24 | **yes**, all 5 → level 0 |
| loss-feedback | 537 ms (33 ms–2.0 s, very noisy) | 75–83 | **no**, all 5 pinned at level 3 |

overflow drops = 0 for both in this scenario.

## Takeaway

- **Queue-depth is a clean control signal.** It reacts in ~200 ms and, when
  bandwidth returns, de-escalates all the way back to level 0 every time.
- **Loss-feedback latches at maximum pressure and never recovers.** The reason
  is fundamental, not a tuning bug: the receiver's loss estimate cannot
  distinguish the AP's *intended* semantic drops from *congestion* loss. Once
  the trigger escalates, the policy drops most frames by design; the receiver
  reports that as loss; the feedback trigger reads it as continuing congestion
  and stays pinned — a self-reinforcing trap. Queue occupancy reflects the true
  backlog regardless of policy drops, so it has no such confound.
- The loss-feedback arm also oscillates 3–4× more (75–83 vs 16–24 level
  changes): end-to-end loss has no stable operating point, queue occupancy does
  (its hysteresis dead-band).

## Claim status: H2 partially supported (characterization)

Supported in direction and mechanism: the local queue signal is faster in the
common case and, more importantly, *stable and self-correcting* where the
end-to-end loss signal is confounded by the policy's own drops. **Not** claimed
as a precise "N× faster" result — the emulated adapt_ms is noisy (feedback was
already oscillating before the step, contaminating the first-reaction time; the
queue arm has one content-driven 3.0 s outlier at seed 3). The definitive
trigger comparison, using real retry / MCS / queue signals, is H5 on hardware.

## Limitations

- `tc netem` gives propagation delay only; no real link-layer signal.
- adapt_ms contaminated by pre-step oscillation (feedback) and content-driven
  queue fill rate (queue seed-3 outlier). Median reported, not mean.
- No overflow differentiation in this scenario (both 0).

## Provenance

- `rq2_agg.json`: per-trigger aggregate + per-run detail
- `traces.tgz`: all 10 runs (queue/feedback x 5 seeds), events + trigger.json
- `sweep.log`: raw run log; analysis via `model/analyze_trigger.py`
