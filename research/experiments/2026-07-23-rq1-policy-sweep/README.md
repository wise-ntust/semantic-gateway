# RQ1 — drop policy vs bandwidth budget (2026-07-23)

Which drop policy preserves the most AI accuracy under a bandwidth budget?

## Setup

- **Workload**: 303 videos, stratified 3 per class over all 101 UCF101
  classes (testlist01, seed 0). File `manifests_strat3.jsonl`.
- **Model**: R(2+1)D-18 fine-tuned on UCF101 split 1, frozen (clean-video
  ceiling 95.7% top-1 on this subset, 3 clips).
- **Grid**: 4 policies x 6 budgets x 3 seeds = 72 runs.
  Budget = fraction of each run's stream byte rate carried by the AP link.
- **AP**: token-bucket link, queue sized to 100 ms of the link rate,
  queue-depth trigger. netns testbed, 2 ms each way.
- **Metric**: top-1 over the frames that survived and stayed decodable,
  3 evenly-spaced clips per video. Mean ± std over 3 seeds.

## Result: top-1 accuracy (mean ± std)

| budget | semantic (ours) | uniform | keyframe | tail |
|-------:|:---------------:|:-------:|:--------:|:----:|
| 1.00 | **0.952 ± 0.005** | 0.933 ± 0.005 | 0.865 ± 0.009 | 0.827 ± 0.030 |
| 0.75 | **0.923 ± 0.007** | 0.866 ± 0.012 | 0.711 ± 0.014 | 0.640 ± 0.013 |
| 0.50 | **0.841 ± 0.015** | 0.715 ± 0.011 | 0.367 ± 0.008 | 0.320 ± 0.003 |
| 0.375 | **0.684 ± 0.019** | 0.523 ± 0.014 | 0.191 ± 0.009 | 0.166 ± 0.002 |
| 0.25 | **0.321 ± 0.015** | 0.206 ± 0.019 | 0.042 ± 0.005 | 0.035 ± 0.002 |
| 0.125 | 0.001 | 0.001 | 0.000 | 0.000 |

## Takeaway

- **H1 supported.** Semantic drop wins at every operating budget (0.25–1.0),
  outside the error bars. The margin over the best baseline (uniform) peaks in
  the mid-budget regime: **+12.6 pp at 0.5, +16.1 pp at 0.375** — exactly where
  choosing *what* to drop matters most (enough link to keep some frames, too
  little for it not to matter which).
- **Task-aware beats merely content-aware.** keyframe (protect I-frames,
  Gobatto-style) lands *below* even random uniform. Protecting only I-frames
  strands one frame per 32-frame GOP; an action model needs temporal context,
  so keyframe starves it. This is the concrete argument for task-aware (H1)
  over content-aware dropping, and the clearest separation from prior work.
- **Blind drop breaks chains.** tail leaves 30–40 videos undecodable even at
  budget 1.0 (bursty I-frames overflow the 100 ms queue; blind drop severs
  reference chains). semantic has 0 undecodable at budget ≥ 0.75.
- **Floor at 0.125.** Below ~1/8 budget even the base layer cannot get
  through; all policies collapse. Expected, not a failure — it bounds the
  operating range.

## Provenance

- `results.json/csv`: per-run rows (policy, budget, seed, top1, usable%, ...)
- `agg.json/csv`: cross-seed mean ± std (via `model/aggregate.py`)
- `traces.tgz`: all 72 raw traces + summaries + per-run env.txt
- `network-sweep.log`, `eval.log`: raw stdout of both stages
- code SHA in each run's env.txt; model = ckpt r2plus1d18_ucf101_seed0
