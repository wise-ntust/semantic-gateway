"""Accuracy of a run: trace.jsonl (what survived the AP) -> top-1.

For each video: received set -> usable set (decodability rule) -> sample
--clips evenly spaced 16-frame windows over the usable frames in display
order (what a receiver could actually decode and feed the model) -> mean
logits -> prediction. Videos with zero usable frames count as errors.

  python model\\evaluate_trace.py --trace RUN\\trace.jsonl --manifests M.jsonl ^
      --ucf-dir ...\\UCF-101 --splits-dir ...\\ucfTrainTestlist ^
      --ckpt ckpt\\r2plus1d18_ucf101_seed0.pt --out RUN\\accuracy.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch
from torchvision.models.video import r2plus1d_18

from model.ucf_data import (decode_all_frames, read_class_index,
                            sample_window, to_clip_tensor)
from semantic_gateway.decodability import usable_frames
from semantic_gateway.manifest import load_manifests


def load_model(ckpt: Path, dev):
    model = r2plus1d_18()
    model.fc = torch.nn.Linear(model.fc.in_features, 101)
    state = torch.load(ckpt, map_location="cpu", weights_only=True)
    model.load_state_dict(state["model"])
    return model.to(dev).eval()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--manifests", type=Path, required=True)
    ap.add_argument("--ucf-dir", type=Path, required=True)
    ap.add_argument("--splits-dir", type=Path, required=True)
    ap.add_argument("--ckpt", type=Path, required=True)
    ap.add_argument("--clips", type=int, default=4)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(args.ckpt, dev)
    cls = read_class_index(args.splits_dir / "classInd.txt")
    manifests = load_manifests(args.manifests)
    good = tot = zero_usable = 0
    details = []
    with open(args.trace) as fh:
        for line in fh:
            rec = json.loads(line)
            m = manifests[rec["video_id"]]
            label_idx = cls[m.label]
            usable = sorted(usable_frames(set(rec["received"]), m.n_frames))
            tot += 1
            if not usable:
                zero_usable += 1
                details.append({"video": m.video, "pred": -1,
                                "label": label_idx, "usable": 0})
                continue
            frames = decode_all_frames(args.ucf_dir / m.label / f"{m.video}.avi")
            usable = [i for i in usable if i < len(frames)]
            if not usable:
                zero_usable += 1
                details.append({"video": m.video, "pred": -1,
                                "label": label_idx, "usable": 0})
                continue
            logits = torch.zeros(101)
            with torch.no_grad(), torch.amp.autocast(dev.type):
                for k in range(args.clips):
                    win = sample_window(len(usable), k=k, n_clips=args.clips)
                    clip = to_clip_tensor([frames[usable[j]] for j in win])
                    logits += model(clip.unsqueeze(0).to(dev)).float().cpu()[0]
            pred = int(logits.argmax())
            good += pred == label_idx
            details.append({"video": m.video, "pred": pred,
                            "label": label_idx, "usable": len(usable)})
    out = {"top1": round(good / tot, 4) if tot else None, "n": tot,
           "zero_usable": zero_usable, "clips": args.clips,
           "ckpt": str(args.ckpt)}
    args.out.write_text(json.dumps({**out, "details": details}))
    print(json.dumps(out))


if __name__ == "__main__":
    main()
