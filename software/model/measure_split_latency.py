"""RQ3 latency axis: per-clip compute time of the head (sender) and tail
(receiver) at each split point, so the frame-vs-feature comparison covers
compute latency, not only on-wire bytes.

  frame path : sender compute ~0, receiver runs the FULL model.
  feature path (split X): sender runs head(X), receiver runs tail(X).

Deeper split -> smaller feature bytes but MORE sender compute. This script
measures that trade with real GPU timings (CUDA-synchronized, warmed up).

  python model\\measure_split_latency.py --ckpt ckpt\\r2plus1d18_ucf101_seed0.pt ^
      --iters 50 --out C:\\Users\\king\\sgw\\rq3\\split_latency.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from torchvision.models.video import r2plus1d_18

from model.evaluate_trace import load_model
from model.extract_features import SPLITS, split_model


def build_model(ckpt, dev):
    """Load fine-tuned weights if given; otherwise random init. Timing is
    weight-independent, so latency can be measured without the checkpoint."""
    if ckpt is not None:
        return load_model(ckpt, dev)
    m = r2plus1d_18()
    m.fc = torch.nn.Linear(m.fc.in_features, 101)
    return m.to(dev).eval()


def timed(fn, x, iters, dev):
    for _ in range(5):  # warmup
        fn(x)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.perf_counter()
    for _ in range(iters):
        fn(x)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    return (time.perf_counter() - t0) / iters * 1000.0  # ms/clip


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ckpt", type=Path, default=None,
                    help="fine-tuned weights; optional (timing is weight-free)")
    ap.add_argument("--iters", type=int, default=50)
    ap.add_argument("--device", default=None, help="cuda | cpu (auto if unset)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dev = torch.device(args.device or ("cuda" if torch.cuda.is_available() else "cpu"))
    model = build_model(args.ckpt, dev)
    clip = torch.randn(1, 3, 16, 112, 112, device=dev)  # one clip

    # frame path: full model at receiver, ~0 at sender
    with torch.no_grad(), torch.amp.autocast(dev.type):
        full_ms = timed(lambda x: model(x), clip, args.iters, dev)

    rows = [{"path": "frame", "split": None, "sender_ms": 0.0,
             "receiver_ms": round(full_ms, 3), "e2e_compute_ms": round(full_ms, 3)}]
    for split in SPLITS:
        head, tail = split_model(model, split)
        with torch.no_grad(), torch.amp.autocast(dev.type):
            feat = head(clip)
            h_ms = timed(lambda x: head(x), clip, args.iters, dev)
            t_ms = timed(lambda f: tail(f), feat, args.iters, dev)
        rows.append({"path": "feature", "split": split,
                     "sender_ms": round(h_ms, 3), "receiver_ms": round(t_ms, 3),
                     "e2e_compute_ms": round(h_ms + t_ms, 3)})

    args.out.write_text(json.dumps({"device": dev.type, "iters": args.iters,
                                    "weights": "finetuned" if args.ckpt else "random-init",
                                    "rows": rows}, indent=2))
    print(f"device={dev.type} weights={'finetuned' if args.ckpt else 'random-init'}")
    print(f"{'path':<8}{'split':<9}{'sender_ms':>10}{'receiver_ms':>12}{'e2e_ms':>9}")
    for r in rows:
        print(f"{r['path']:<8}{str(r['split']):<9}{r['sender_ms']:>10.2f}"
              f"{r['receiver_ms']:>12.2f}{r['e2e_compute_ms']:>9.2f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
