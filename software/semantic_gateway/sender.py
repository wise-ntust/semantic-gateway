"""Replays video manifests as paced UDP packets toward the proxy.

Pacing is real time divided by --speed (time-compressed replay: both the
frame arrival rate and the link rate schedule scale together, so queueing
behaviour in packets is preserved while wall-clock shrinks).
"""

from __future__ import annotations

import argparse
import asyncio
import random
import socket
import time
from pathlib import Path

from . import rtp
from .manifest import load_manifests
from .metrics import write_run_meta


async def amain(args):
    run_dir = Path(args.run_dir)
    write_run_meta(run_dir, "sender", vars(args))
    manifests = load_manifests(Path(args.manifests))
    if args.videos:
        manifests = manifests[: args.videos]
    order = list(range(len(manifests)))
    random.Random(args.seed).shuffle(order)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    dest = (args.proxy_host, args.proxy_port)

    t0 = time.monotonic()
    clock = 0.0  # virtual stream time in seconds
    sent_frames = 0
    for vid in order:
        m = manifests[vid]
        for f in m.frames:
            clock += 1.0 / m.fps
            target = t0 + clock / args.speed
            delay = target - time.monotonic()
            if delay > 0:
                await asyncio.sleep(delay)
            send_ns = time.monotonic_ns()
            for pkt in rtp.fragments(vid, f.i, f.layer, f.diff, f.size, send_ns):
                sock.sendto(rtp.pack(pkt), dest)
            sent_frames += 1
    # END marker: give the queue a moment, then send through the same path
    await asyncio.sleep(0.2)
    end = rtp.Packet(ptype=rtp.T_END, video_id=0, frame_idx=0, layer=0,
                     diff_q=0, frag_idx=0, frag_cnt=1, last_frag=True,
                     send_ns=time.monotonic_ns(), payload_len=0)
    sock.sendto(rtp.pack(end), dest)
    elapsed = time.monotonic() - t0
    print(f"sender: {sent_frames} frames / {len(manifests)} videos "
          f"in {elapsed:.1f}s (speed x{args.speed})")


def main():
    ap = argparse.ArgumentParser(description="semantic-gateway sender")
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--videos", type=int, default=0, help="limit, 0 = all")
    ap.add_argument("--speed", type=float, default=8.0)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--proxy-host", default="127.0.0.1")
    ap.add_argument("--proxy-port", type=int, default=5000)
    ap.add_argument("--run-dir", required=True)
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
