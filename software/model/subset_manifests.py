"""Stratified subset of a manifest file: N videos per class, re-indexed.

The output is a normal manifest file with video_ids 0..M-1 in class order;
sender, receiver, and evaluator all load this same file so video_id stays
consistent across the pipeline. Deterministic given --seed.

  python model\\subset_manifests.py --in manifests_test01.jsonl ^
      --out manifests_strat3.jsonl --per-class 3 --seed 0
"""

from __future__ import annotations

import argparse
import random
from collections import defaultdict
from pathlib import Path

from semantic_gateway.manifest import load_manifests, save_manifests


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--per-class", type=int, default=3)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    by_class: dict[str, list] = defaultdict(list)
    for m in load_manifests(args.inp):
        by_class[m.label].append(m)

    rng = random.Random(args.seed)
    chosen = []
    for label in sorted(by_class):
        vids = sorted(by_class[label], key=lambda m: m.video)
        rng.shuffle(vids)
        chosen.extend(vids[: args.per_class])

    save_manifests(chosen, args.out)
    print(f"{len(by_class)} classes x {args.per_class} -> {len(chosen)} "
          f"videos, {args.out}")


if __name__ == "__main__":
    main()
