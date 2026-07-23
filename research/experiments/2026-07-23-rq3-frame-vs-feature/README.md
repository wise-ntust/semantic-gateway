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

### Latency axis (compute placement)

`model/measure_split_latency.py`, per 16-frame clip (sandbox CPU, random-init;
timing is weight-independent, so absolute ms are a proxy for the *trend*, not
edge hardware; GPU numbers pending):

| path | sender compute | receiver compute | feature bytes |
|------|---------------:|-----------------:|--------------:|
| frame | 0.0 ms | 64.6 ms (full model) | 24 KB |
| feature @ stem | 1.8 ms | 68.6 ms | 3211 KB |
| feature @ layer2 | 50.1 ms | 10.5 ms | 803 KB |
| feature @ layer3 | 55.3 ms | 4.2 ms | 201 KB |
| feature @ layer4 | 64.1 ms | 0.0 ms | 50 KB |
| feature @ avgpool | 63.6 ms | 0.0 ms | 520 B |

Sender compute climbs monotonically with split depth (1.8 → 64 ms). The only
split that shrinks the feature below the frames (avgpool) makes the sender run
essentially the whole model. **There is no split that is both small-bytes and
low-sender-compute** — the two axes agree.

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
