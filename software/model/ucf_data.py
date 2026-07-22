"""UCF101 clip dataset for fine-tune / evaluation (PyAV decode, no cache)."""

from __future__ import annotations

import random
from pathlib import Path

import av
import numpy as np
import torch
from torch.utils.data import Dataset

MEAN = torch.tensor([0.43216, 0.394666, 0.37645]).view(3, 1, 1, 1)
STD = torch.tensor([0.22803, 0.22145, 0.216989]).view(3, 1, 1, 1)
CLIP_LEN = 16


def read_class_index(class_ind: Path) -> dict[str, int]:
    out = {}
    for line in class_ind.read_text().splitlines():
        if line.strip():
            idx, name = line.split()
            out[name] = int(idx) - 1
    return out


def read_split(split_file: Path, class_to_idx: dict[str, int]) -> list[tuple[str, int]]:
    items = []
    for line in split_file.read_text().splitlines():
        rel = line.strip().split()[0]
        if rel:
            items.append((rel, class_to_idx[rel.split("/")[0]]))
    return items


def decode_all_frames(path: Path) -> list[np.ndarray]:
    with av.open(str(path)) as c:
        return [f.to_ndarray(format="rgb24") for f in c.decode(video=0)]


def to_clip_tensor(frames: list[np.ndarray], size: int = 112,
                   train: bool = False) -> torch.Tensor:
    """frames: CLIP_LEN rgb24 arrays -> normalized (C,T,H,W) tensor."""
    t = torch.from_numpy(np.stack(frames)).permute(3, 0, 1, 2).float() / 255.0
    _, _, h, w = t.shape
    scale = 128 / min(h, w)
    t = torch.nn.functional.interpolate(
        t.permute(1, 0, 2, 3), scale_factor=scale, mode="bilinear",
        align_corners=False).permute(1, 0, 2, 3)
    _, _, h, w = t.shape
    if train:
        y = random.randint(0, h - size)
        x = random.randint(0, w - size)
        t = t[:, :, y : y + size, x : x + size]
        if random.random() < 0.5:
            t = torch.flip(t, dims=[3])
    else:
        y, x = (h - size) // 2, (w - size) // 2
        t = t[:, :, y : y + size, x : x + size]
    return (t - MEAN) / STD


def sample_window(n: int, clip_len: int = CLIP_LEN, train: bool = False,
                  k: int = 0, n_clips: int = 1) -> list[int]:
    """Indices of one clip window over a list of n usable frames."""
    if n <= 0:
        return []
    if n < clip_len:
        return (list(range(n)) * clip_len)[:clip_len]
    if train:
        start = random.randint(0, n - clip_len)
    else:
        span = max(0, n - clip_len)
        start = round(span * k / max(1, n_clips - 1)) if n_clips > 1 else span // 2
    return list(range(start, start + clip_len))


class UCFClips(Dataset):
    def __init__(self, ucf_dir: Path, items: list[tuple[str, int]],
                 train: bool):
        self.ucf_dir = ucf_dir
        self.items = items
        self.train = train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, i):
        rel, label = self.items[i]
        frames = decode_all_frames(self.ucf_dir / rel)
        idx = sample_window(len(frames), train=self.train)
        clip = to_clip_tensor([frames[j] for j in idx], train=self.train)
        return clip, label
