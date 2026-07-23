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

## RQ2 — trigger signal (H2)

**Run**: `experiments/2026-07-23-rq2-trigger-latency/` (semantic policy,
queue vs loss-feedback trigger, bandwidth step 60→18→60 KB/s, 5 seeds,
real-time).

**Headline**: queue-depth adapts in **196 ms** (median) and recovers to level 0
every time; loss-feedback latches at max pressure and **never recovers**,
because it cannot tell the AP's intended semantic drops from congestion loss
and traps itself. Queue occupancy has a stable dead-band; end-to-end loss does
not (75–83 vs 16–24 level changes).

**Claim status**: **H2 partially supported (characterization).** Direction and
mechanism hold; no precise "N× faster" claim (emulated adapt_ms is noisy). The
definitive test needs real link-layer signals (retry/MCS) on hardware — H5.

## RQ3 — frame vs feature (H3)

**Run**: `experiments/2026-07-23-rq3-frame-vs-feature/` (6 split points, int8,
303 videos).

**Headline**: no split shallow enough for AP-side computing beats the frame
path — the deepest conv split (layer4) is still 2.1× the compressed frames,
shallower up to 133×. Only avgpool (whole net at sender = edge inference) is
smaller. A modern codec compresses frames better than naive int8 compresses
activations.

**Claim status**: **H3 not supported.** Honest negative; sharpens scope toward
AP-side dropping (RQ1). No RQ1 claim depends on it.

## RQ4 / RQ5 — on-device (H4 / H5)

Deferred to Phase 4 (ARM PS) and Phase 5 (openwifi PL), per roadmap.

## Overall read

- **H1 — strongly supported.** Semantic (task-aware, layer-structured) dropping
  at the AP preserves AI accuracy far better than blind (tail), thinning
  (uniform), or content-aware-but-task-blind (keyframe) dropping, at equal
  budget; the gain peaks (+12–16 pp) in the mid-budget regime. This is the
  headline result.
- **H2 — partially supported (characterization).** Queue-depth is a faster and,
  crucially, stable/self-correcting control signal; loss-feedback is confounded
  by the policy's own drops and latches at max pressure. Direction holds; the
  precise, hardware-grade comparison is deferred to H5.
- **H3 — not supported (honest negative).** For this model + codec, forwarding
  compressed frames beats forwarding int8 features at every AP-side split. This
  sharpens scope: the value is in dropping at the AP, not feature extraction.
- **No RQ1 claim shrinks.** keyframe < uniform and the H3 negative both sharpen
  the story rather than weaken it: the win is specifically *task-aware layer
  dropping at the AP*, differentiated from prior content-aware in-network work.
- **Next**: H4/H5 on hardware (ARM PS then openwifi PL), later phases.
