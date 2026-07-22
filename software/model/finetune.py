"""Fine-tune R(2+1)D-18 (Kinetics-400 pretrained) on UCF101 split 1.

Runs on king (RTX 3080 10GB). One checkpoint is trained per seed, then
frozen and shared by every experiment. Training log is train_log.jsonl.

  python model\\finetune.py --ucf-dir ...\\UCF-101 --splits-dir ...\\ucfTrainTestlist ^
      --out-dir C:\\Users\\king\\sgw\\ckpt --seed 0 --epochs 12 --batch 12
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch
from torch.utils.data import DataLoader
from torchvision.models.video import R2Plus1D_18_Weights, r2plus1d_18

from model.ucf_data import UCFClips, read_class_index, read_split


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ucf-dir", type=Path, required=True)
    ap.add_argument("--splits-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=12)
    ap.add_argument("--batch", type=int, default=12)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--val-every", type=int, default=1)
    ap.add_argument("--val-videos", type=int, default=800,
                    help="fixed random subset for per-epoch val (speed)")
    args = ap.parse_args()

    torch.manual_seed(args.seed)
    random.seed(args.seed)
    np.random.seed(args.seed)

    cls = read_class_index(args.splits_dir / "classInd.txt")
    train_items = read_split(args.splits_dir / "trainlist01.txt", cls)
    test_items = read_split(args.splits_dir / "testlist01.txt", cls)
    val_items = random.Random(42).sample(test_items,
                                         min(args.val_videos, len(test_items)))

    train_ds = UCFClips(args.ucf_dir, train_items, train=True)
    val_ds = UCFClips(args.ucf_dir, val_items, train=False)
    train_dl = DataLoader(train_ds, batch_size=args.batch, shuffle=True,
                          num_workers=args.workers, pin_memory=True,
                          drop_last=True, persistent_workers=True)
    val_dl = DataLoader(val_ds, batch_size=args.batch, shuffle=False,
                        num_workers=args.workers, pin_memory=True)

    dev = torch.device("cuda")
    model = r2plus1d_18(weights=R2Plus1D_18_Weights.KINETICS400_V1)
    model.fc = torch.nn.Linear(model.fc.in_features, 101)
    model.to(dev)

    opt = torch.optim.SGD(model.parameters(), lr=args.lr, momentum=0.9,
                          weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=args.epochs)
    scaler = torch.amp.GradScaler("cuda")
    loss_fn = torch.nn.CrossEntropyLoss(label_smoothing=0.1)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    log = open(args.out_dir / f"train_log_seed{args.seed}.jsonl", "w",
               buffering=1)
    best = 0.0
    for epoch in range(args.epochs):
        model.train()
        t0, seen, loss_sum = time.time(), 0, 0.0
        for clips, labels in train_dl:
            clips, labels = clips.to(dev, non_blocking=True), labels.to(dev)
            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda"):
                loss = loss_fn(model(clips), labels)
            scaler.scale(loss).backward()
            scaler.step(opt)
            scaler.update()
            seen += labels.numel()
            loss_sum += loss.item() * labels.numel()
        sched.step()

        acc = None
        if (epoch + 1) % args.val_every == 0:
            model.eval()
            good = tot = 0
            with torch.no_grad(), torch.amp.autocast("cuda"):
                for clips, labels in val_dl:
                    pred = model(clips.to(dev)).argmax(1).cpu()
                    good += (pred == labels).sum().item()
                    tot += labels.numel()
            acc = good / tot
            if acc > best:
                best = acc
                torch.save({"model": model.state_dict(), "seed": args.seed,
                            "epoch": epoch, "val_acc": acc},
                           args.out_dir / f"r2plus1d18_ucf101_seed{args.seed}.pt")
        log.write(json.dumps({"epoch": epoch, "loss": round(loss_sum / seen, 4),
                              "val_acc": acc, "lr": sched.get_last_lr()[0],
                              "secs": round(time.time() - t0, 1)}) + "\n")
        print(f"epoch {epoch}: loss {loss_sum / seen:.4f} val {acc} "
              f"({time.time() - t0:.0f}s)")
    log.close()
    print(f"best val acc {best:.4f}")


if __name__ == "__main__":
    main()
