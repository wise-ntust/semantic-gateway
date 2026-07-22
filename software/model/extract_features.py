"""RQ3 feature path: split-point features, their wire size, and accuracy.

Splits the fine-tuned R(2+1)D-18 at a named point; the head runs at the
sender, the (quantized) activation crosses the network, the tail runs at the
edge. For each (split, quant) this script reports bytes-per-clip and top-1
over the test manifests, using the SAME usable-frame sets as the frame path
(pass a trace) or full videos (no trace = no drop).

  python model\\extract_features.py --manifests M.jsonl --ucf-dir ... ^
      --splits-dir ... --ckpt ckpt\\r2plus1d18_ucf101_seed0.pt ^
      --split layer2 --quant int8 [--trace RUN\\trace.jsonl] --out feat.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch

from model.evaluate_trace import load_model
from model.ucf_data import (decode_all_frames, read_class_index,
                            sample_window, to_clip_tensor)
from semantic_gateway.decodability import usable_frames
from semantic_gateway.manifest import load_manifests

SPLITS = ["stem", "layer1", "layer2", "layer3", "layer4", "avgpool"]


def split_model(model, split: str):
    mods = {"stem": model.stem, "layer1": model.layer1, "layer2": model.layer2,
            "layer3": model.layer3, "layer4": model.layer4,
            "avgpool": model.avgpool}
    order = SPLITS
    cut = order.index(split) + 1
    head = torch.nn.Sequential(*[mods[m] for m in order[:cut]])
    tail_mods = [mods[m] for m in order[cut:]]

    def tail(x):
        for m in tail_mods:
            x = m(x)
        return model.fc(torch.flatten(x, 1))

    return head, tail


def quantize(x: torch.Tensor, mode: str) -> tuple[torch.Tensor, int]:
    """Returns dequantized tensor (what the tail sees) and wire bytes."""
    if mode == "fp32":
        return x, x.numel() * 4
    if mode == "fp16":
        return x.half().float(), x.numel() * 2
    if mode == "int8":
        lo, hi = x.min(), x.max()
        scale = (hi - lo).clamp(min=1e-8) / 255.0
        q = ((x - lo) / scale).round().clamp(0, 255)
        return q * scale + lo, x.numel() + 8  # payload + scale/offset
    raise ValueError(mode)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifests", type=Path, required=True)
    ap.add_argument("--ucf-dir", type=Path, required=True)
    ap.add_argument("--splits-dir", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--split", choices=SPLITS, required=True)
    ap.add_argument("--quant", choices=["fp32", "fp16", "int8"], default="int8")
    ap.add_argument("--trace", type=Path, default=None)
    ap.add_argument("--clips", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(args.ckpt, dev)
    head, tail = split_model(model, args.split)
    cls = read_class_index(args.splits_dir / "classInd.txt")
    manifests = load_manifests(args.manifests)

    received = {}
    if args.trace:
        with open(args.trace) as fh:
            for line in fh:
                rec = json.loads(line)
                received[rec["video_id"]] = set(rec["received"])

    good = tot = 0
    bytes_per_clip = None
    for vid, m in enumerate(manifests):
        label_idx = cls[m.label]
        got = received.get(vid, set(range(m.n_frames)))
        usable = sorted(usable_frames(got, m.n_frames))
        tot += 1
        if not usable:
            continue
        frames = decode_all_frames(args.ucf_dir / m.label / f"{m.video}.avi")
        usable = [i for i in usable if i < len(frames)]
        if not usable:
            continue
        logits = torch.zeros(101)
        with torch.no_grad(), torch.amp.autocast(dev.type):
            for k in range(args.clips):
                win = sample_window(len(usable), k=k, n_clips=args.clips)
                clip = to_clip_tensor([frames[usable[j]] for j in win])
                feat = head(clip.unsqueeze(0).to(dev)).float()
                deq, nbytes = quantize(feat.cpu(), args.quant)
                bytes_per_clip = nbytes
                logits += tail(deq.to(dev)).float().cpu()[0]
        good += int(logits.argmax()) == label_idx

    out = {"split": args.split, "quant": args.quant,
           "bytes_per_clip": bytes_per_clip,
           "top1": round(good / tot, 4) if tot else None, "n": tot,
           "trace": str(args.trace) if args.trace else None}
    args.out.write_text(json.dumps(out, indent=2))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
