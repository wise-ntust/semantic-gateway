# G3 smoke experiment (2026-07-22)

Miniature end-to-end run through the real harness. Not a headline result:
its job is to prove the whole chain works before Stage 4 scales up.

## Setup

- **Workload**: first 20 videos of UCF101 testlist01 (real x264 manifests)
- **Model**: R(2+1)D-18, Kinetics-400 pretrained, fine-tuned on UCF101 split 1
  (best val 93.5% on clean full video, epoch 10, seed 0)
- **Link**: token-bucket AP, budget = 50% of each run's stream byte rate
- **Trigger**: queue-depth, seed 1, netns testbed (2ms each way)
- **Chain**: sender → AP proxy (policy) → receiver → trace → usable frames
  → decode → model → top-1

## Result

| policy | top-1 | usable% | zero-usable | mean latency |
|--------|------:|--------:|------------:|-------------:|
| **semantic (ours)** | **0.90** | 39.9 | 0 / 20 | 1225 ms |
| uniform | 0.80 | 37.4 | 0 / 20 | 1286 ms |
| keyframe | 0.75 | 18.0 | 0 / 20 | 2154 ms |
| tail | 0.30 | 17.1 | 14 / 20 | 2579 ms |

## Reading

- Clean-video accuracy is 93.5%. At half the bandwidth, **semantic loses only
  3.5 points** (90.0%) while **tail-drop collapses to 30%**.
- tail-drop strands **14 of 20 videos with zero decodable frames**: blind
  drop breaks GOP reference chains, so received-but-unusable dominates.
- semantic beats uniform by 10 points at nearly identical usable% — dropping
  by layer keeps the frames that carry temporal information, not just *some*
  frames. This is the H1 mechanism, visible even at smoke scale.
- Latency here is inflated by a fixed 256 KB queue cap; Stage 4 will set the
  cap from link RTT. Ordering across policies is still meaningful.

## Known limitations (fixed before Stage 4)

- **Single class**: testlist01's first 20 videos are all `ApplyEyeMakeup`, so
  absolute top-1 carries class bias. The cross-policy *ordering* is still
  valid (same videos, only surviving frames differ), but Stage 4 must select
  videos stratified across classes. Tracked in STATE open questions.
- **Queue cap**: fixed 256 KB inflates absolute latency; set from link RTT
  in Stage 4.
- **One seed**: smoke uses seed 1 only; Stage 4 uses ≥5 seeds with error bars
  per plan.md rigor budget.

## Provenance

- code: see `git_sha` in each run's `*.run.json` (on king)
- `results.csv` / `results.json`: aggregated by `model/eval_all.py`
- per-video predictions: in each policy's `accuracy.json` (`details`)
- `train_log_seed0.jsonl`: fine-tune curve
