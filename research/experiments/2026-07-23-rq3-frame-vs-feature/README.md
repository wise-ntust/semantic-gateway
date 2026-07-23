# RQ3 — frame vs feature (2026-07-23)

Under an equal bandwidth budget, is it better to forward surviving *frames*,
or *features* extracted from them? Where is the crossover?

## Setup

- **Workload**: 303 stratified UCF101 videos (same subset as RQ1).
- **Model**: R(2+1)D-18 fine-tuned, split at six points; sender runs the head,
  the (int8-quantized) activation crosses the link, receiver runs the tail.
- **Frame-path reference**: send the clip's 16 encoded frames. Average encoded
  frame = **1512 B** (I-frame 7786 B, P-frame 1291 B); a 16-frame clip =
  **24,186 B**.
- **Metric**: bytes per 16-frame clip on the wire, and top-1. int8 is the most
  aggressive of our quantizers, so it is the feature path's best case.

## Result

| split point | feature bytes/clip | vs frame clip (24,186 B) | top-1 | sender compute |
|-------------|-------------------:|:------------------------:|:-----:|----------------|
| stem | 3,211,272 | 133× larger | 0.951 | ~none |
| layer1 | 3,211,272 | 133× larger | 0.951 | tiny |
| layer2 | 802,824 | 33× larger | 0.951 | small |
| layer3 | 200,712 | 8.3× larger | 0.951 | medium |
| layer4 | 50,184 | 2.1× larger | 0.951 | most of the net |
| avgpool | 520 | **47× smaller** | 0.951 | ~entire net |

int8 quantization is near-lossless: accuracy is 0.951 at every split (clean
ceiling 0.957).

## Takeaway

- **H3 not supported in the intended regime.** For every split shallow enough
  to leave real work downstream (stem…layer4), the feature is *larger* than the
  compressed frames — 2× at the deepest conv split, up to 133× at the stem.
  There is no bandwidth budget where an AP-side feature path beats the frame
  path: it costs more bytes *and* adds sender compute.
- **The only byte win is at avgpool** (520 B/clip), but that means running the
  entire conv network at the sender and shipping a 512-D embedding. That is
  full edge inference with the AP forwarding a result, not the AP-assisted
  in-network computing this project is about.
- **Root cause**: a modern video codec already exploits temporal redundancy
  (P-frames ~1.3 KB), so compressed frames are cheap; naive int8 features do
  not get that for free. Beating frames would need feature compression far more
  aggressive than int8 (learned/entropy coding) — itself a research problem
  that adds the very sender latency the idea was meant to save.

## Consequence for the project

This is a clean negative result that *sharpens scope*: the value is in
task-aware **dropping** at the AP (RQ1, strongly supported), not in feature
extraction at the AP. Feature transmission stays a "bonus" only under a
different architecture (deep split = edge inference) or future work on
aggressive feature compression. Recorded honestly; no RQ1 claim depends on it.

## Provenance

- `feat_<split>_int8.json`: per-split bytes + accuracy (via
  `model/extract_features.py`)
- frame-path reference computed from `manifests_strat3.jsonl` (see run log)
- model = ckpt r2plus1d18_ucf101_seed0
