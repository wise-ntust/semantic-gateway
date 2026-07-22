"""Per-video frame manifests.

A manifest describes one encoded video as a list of frames, each with:
  i      frame index (display order)
  size   encoded size in bytes (from a real x264 hierarchical-P pass,
         or synthetic for pipeline tests)
  layer  temporal layer id (0 = base / I or L0-P, 1 = L1, 2 = L2)
  diff   frame-difference score vs previous frame, quantized 0-255

The GOP structure is hierarchical-P with an I frame every GOP frames and a
4-frame temporal pattern: L0 at g % 4 == 0, L1 at g % 4 == 2, L2 at odd g.
Dropping all frames of layer >= k keeps the stream decodable by design;
that is the whole point of the semantic policy.
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass, field
from pathlib import Path

GOP = 32  # I-frame period (frames)


def layer_of(i: int) -> int:
    """Temporal layer of display-order frame i."""
    g = i % GOP
    if g % 4 == 0:
        return 0
    if g % 2 == 0:
        return 1
    return 2


def ancestor(i: int) -> int | None:
    """The single reference frame of display-order frame i (None for I frames).

    Hierarchical-P referencing within a GOP:
      I  (g == 0)      -> no reference
      L0 (g % 4 == 0)  -> previous L0 (i - 4)
      L1 (g % 4 == 2)  -> previous L0 (i - 2)
      L2 (odd g)       -> previous even frame (i - 1)
    """
    g = i % GOP
    if g == 0:
        return None
    if g % 4 == 0:
        return i - 4
    if g % 2 == 0:
        return i - 2
    return i - 1


@dataclass
class FrameMeta:
    i: int
    size: int
    layer: int
    diff: int  # 0-255


@dataclass
class VideoManifest:
    video: str          # e.g. "v_ApplyEyeMakeup_g01_c01"
    label: str          # class name
    fps: float
    frames: list[FrameMeta] = field(default_factory=list)

    @property
    def n_frames(self) -> int:
        return len(self.frames)

    def to_json(self) -> str:
        return json.dumps(
            {
                "video": self.video,
                "label": self.label,
                "fps": self.fps,
                "frames": [[f.i, f.size, f.layer, f.diff] for f in self.frames],
            }
        )

    @classmethod
    def from_json(cls, line: str) -> "VideoManifest":
        d = json.loads(line)
        return cls(
            video=d["video"],
            label=d["label"],
            fps=d["fps"],
            frames=[FrameMeta(*f) for f in d["frames"]],
        )


def load_manifests(path: Path) -> list[VideoManifest]:
    with open(path) as fh:
        return [VideoManifest.from_json(line) for line in fh if line.strip()]


def save_manifests(manifests: list[VideoManifest], path: Path) -> None:
    with open(path, "w") as fh:
        for m in manifests:
            fh.write(m.to_json() + "\n")


def make_synthetic(
    n_videos: int, n_frames: int = 240, fps: float = 30.0, seed: int = 0
) -> list[VideoManifest]:
    """Synthetic manifests for pipeline tests: I frames big, higher layers small."""
    rng = random.Random(seed)
    base = {0: 12000, 1: 6000, 2: 3000}
    out = []
    for v in range(n_videos):
        frames = []
        for i in range(n_frames):
            lay = layer_of(i)
            size = 45000 if i % GOP == 0 else int(base[lay] * rng.uniform(0.6, 1.4))
            frames.append(FrameMeta(i, size, lay, rng.randint(0, 255)))
        out.append(
            VideoManifest(video=f"synth_{v:04d}", label="synth", fps=fps, frames=frames)
        )
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Generate synthetic manifests")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--videos", type=int, default=4)
    ap.add_argument("--frames", type=int, default=240)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    save_manifests(make_synthetic(args.videos, args.frames, seed=args.seed), args.out)
    print(f"wrote {args.videos} synthetic manifests to {args.out}")


if __name__ == "__main__":
    main()
