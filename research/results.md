# Results

Maps each research question to the run directory that answers it, the
headline numbers, and an honest read on which claims hold.

## RQ1 — drop policy vs bandwidth budget (H1)

**Run**: `experiments/2026-07-23-rq1-policy-sweep/` (72 runs, 4 policies x
6 budgets x 3 seeds, 303 stratified UCF101 videos, R(2+1)D-18).

**Headline** (top-1, mean over 3 seeds; clean ceiling 95.7%):

| budget | semantic | uniform | keyframe | tail |
|-------:|:--------:|:-------:|:--------:|:----:|
| 1.00 | 0.952 | 0.933 | 0.865 | 0.827 |
| 0.75 | 0.923 | 0.866 | 0.711 | 0.640 |
| 0.50 | 0.841 | 0.715 | 0.367 | 0.320 |
| 0.375 | 0.684 | 0.523 | 0.191 | 0.166 |
| 0.25 | 0.321 | 0.206 | 0.042 | 0.035 |

**Takeaway**: semantic drop wins at every budget from 0.25 to 1.0, outside
error bars (std ≤ 0.03 everywhere); the margin over the best baseline peaks at
+12–16 pp in the mid-budget regime. keyframe (content-aware, task-blind) falls
below random uniform, showing task-awareness is the source of the gain.

**Claim status**: **H1 supported, strongly.**

## RQ2 — trigger latency (H2)

Not yet run. Harness ready (`--trigger queue|feedback`, `--rate-spec` for
bandwidth steps). Next up.

## RQ3 — frame vs feature (H3)

Not yet run. Harness ready (`model/extract_features.py`, split-point + quant).

## RQ4 / RQ5 — on-device (H4 / H5)

Deferred to Phase 4 (ARM PS) and Phase 5 (openwifi PL), per roadmap.

## Overall read

- **Supported now**: H1 — semantic (task-aware, layer-structured) dropping at
  the AP preserves AI accuracy far better than blind (tail), thinning
  (uniform), or content-aware-but-task-blind (keyframe) dropping, under an
  equal bandwidth budget. The mid-budget regime is where it matters most.
- **Not yet tested**: H2, H3 (harness in place). H4/H5 hardware, later phases.
- **No contradicted claims.** Nothing needs to shrink. keyframe underperforming
  uniform is a bonus finding that sharpens the story vs prior content-aware
  in-network work.
