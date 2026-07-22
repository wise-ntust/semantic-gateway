"""Build per-video manifests from real UCF101 videos (runs on king).

Two passes per video:
  1. ffmpeg x264 encode (closed GOP 32, no B frames, CRF 23) piped to
     ffprobe -> real per-frame encoded sizes;
  2. PyAV decode -> frame-difference score (mean abs diff, 32x32 gray).

Temporal layer ids follow semantic_gateway.manifest.layer_of. Modeling note:
x264 emits IPPP (not hierarchical-P), so sizes approximate a hierarchical
encoder; the reference structure used for decodability is OUR pattern. This
is a documented modeling assumption, recorded in IMPLEMENTATION_NOTES.md.

Usage (king):
  python model\\prepare_manifests.py --ucf-dir C:\\Users\\king\\sgw\\data\\UCF-101 ^
      --split-file C:\\Users\\king\\sgw\\data\\ucfTrainTestlist\\testlist01.txt ^
      --out C:\\Users\\king\\sgw\\data\\manifests_test01.jsonl --workers 6
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np  # noqa: E402
import av  # noqa: E402

from semantic_gateway.manifest import FrameMeta, VideoManifest, layer_of  # noqa: E402

X264_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-an",
    "-x264-params", "keyint=32:min-keyint=32:scenecut=0:bframes=0",
]


def frame_sizes(video: Path) -> list[int]:
    """Encode once, read back per-frame packet sizes."""
    enc = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(video), *X264_ARGS,
         "-f", "h264", "pipe:1"],
        capture_output=True, check=True,
    )
    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-f", "h264", "-show_frames",
         "-show_entries", "frame=pkt_size", "-of", "json", "pipe:0"],
        input=enc.stdout, capture_output=True, check=True,
    )
    frames = json.loads(probe.stdout)["frames"]
    return [int(f["pkt_size"]) for f in frames]


def diff_scores(video: Path) -> tuple[list[int], float]:
    """Quantized mean-abs-diff per frame (0 for the first), plus fps."""
    scores = [0]
    prev = None
    with av.open(str(video)) as container:
        stream = container.streams.video[0]
        fps = float(stream.average_rate or 25.0)
        for frame in container.decode(stream):
            img = frame.to_ndarray(format="gray")
            small = img[:: max(1, img.shape[0] // 32),
                        :: max(1, img.shape[1] // 32)].astype(np.int16)
            if prev is not None and prev.shape == small.shape:
                scores.append(int(min(255, np.abs(small - prev).mean() * 4)))
            elif prev is not None:
                scores.append(128)
            prev = small
    return scores, fps


def process_one(args: tuple[Path, str]) -> str | None:
    video, label = args
    try:
        sizes = frame_sizes(video)
        diffs, fps = diff_scores(video)
        n = min(len(sizes), len(diffs))
        frames = [FrameMeta(i, sizes[i], layer_of(i), diffs[i]) for i in range(n)]
        m = VideoManifest(video=video.stem, label=label, fps=fps, frames=frames)
        return m.to_json()
    except Exception as e:  # noqa: BLE001 - collect and report, don't die
        print(f"FAIL {video.name}: {e}", file=sys.stderr)
        return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ucf-dir", type=Path, required=True)
    ap.add_argument("--split-file", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    jobs: list[tuple[Path, str]] = []
    for line in args.split_file.read_text().splitlines():
        rel = line.strip().split()[0]
        if not rel:
            continue
        label = rel.split("/")[0]
        jobs.append((args.ucf_dir / rel.replace("/", "\\" if "\\" in str(args.ucf_dir) else "/"), label))
    if args.limit:
        jobs = jobs[: args.limit]

    done = 0
    with open(args.out, "w") as fh, ProcessPoolExecutor(args.workers) as ex:
        for res in ex.map(process_one, jobs, chunksize=8):
            if res:
                fh.write(res + "\n")
            done += 1
            if done % 200 == 0:
                print(f"{done}/{len(jobs)}")
    print(f"wrote manifests for {done} videos -> {args.out}")


if __name__ == "__main__":
    main()
