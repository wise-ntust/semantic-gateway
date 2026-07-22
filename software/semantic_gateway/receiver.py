"""Receives packets after the proxy, reassembles frames, writes the trace.

Output trace.jsonl, one record per video:
  {"video_id", "video", "n_frames", "received": [idx...],
   "lat_ms": [[idx, ms]...]}

The trace is the contract with the king-side evaluator: accuracy is computed
offline from (trace, manifests, checkpoint). The receiver also emits periodic
FEEDBACK packets carrying the observed loss ratio (application-layer trigger
baseline for RQ2).
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import defaultdict
from pathlib import Path

from . import rtp
from .manifest import load_manifests
from .metrics import JsonlWriter, write_run_meta


class Receiver(asyncio.DatagramProtocol):
    def __init__(self, args, manifests):
        self.args = args
        self.manifests = manifests
        self.frags: dict[tuple[int, int], int] = defaultdict(int)
        self.received: dict[int, list[int]] = defaultdict(list)
        self.lat: dict[int, list[list[float]]] = defaultdict(list)
        self.win_expected = 0
        self.win_missing = 0
        self.last_idx: dict[int, int] = {}
        self.transport = None
        self.done = asyncio.get_running_loop().create_future()

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        p = rtp.unpack(data)
        self.proxy_addr = addr
        if p.ptype == rtp.T_END:
            self.done.set_result(True)
            return
        key = (p.video_id, p.frame_idx)
        self.frags[key] += 1
        if p.frag_idx == 0:
            last = self.last_idx.get(p.video_id)
            if last is not None and p.frame_idx > last + 1:
                self.win_missing += p.frame_idx - last - 1
            self.win_expected += (p.frame_idx - last) if last is not None else 1
            self.last_idx[p.video_id] = p.frame_idx
        if self.frags[key] == p.frag_cnt:
            self.received[p.video_id].append(p.frame_idx)
            # 32-bit modular difference; valid while frame latency < ~4.29 s
            ms = ((time.monotonic_ns() - p.send_ns) & 0xFFFFFFFF) / 1e6
            self.lat[p.video_id].append([p.frame_idx, round(ms, 2)])

    async def feedback_loop(self):
        while True:
            await asyncio.sleep(self.args.feedback_interval)
            total = self.win_expected
            loss = self.win_missing / total if total else 0.0
            self.win_expected = self.win_missing = 0
            pkt = rtp.Packet(ptype=rtp.T_FEEDBACK, video_id=0, frame_idx=0,
                             layer=0, diff_q=min(255, int(loss * 255)),
                             frag_idx=0, frag_cnt=1, last_frag=True,
                             send_ns=time.monotonic_ns(), payload_len=0)
            self.transport.sendto(rtp.pack(pkt),
                                  (self.args.proxy_host, self.args.proxy_port))


async def amain(args):
    run_dir = Path(args.run_dir)
    write_run_meta(run_dir, "receiver", vars(args))
    manifests = load_manifests(Path(args.manifests))
    loop = asyncio.get_running_loop()
    recv = Receiver(args, manifests)
    await loop.create_datagram_endpoint(
        lambda: recv, local_addr=(args.listen_host, args.listen_port))
    fb = asyncio.create_task(recv.feedback_loop())
    try:
        await asyncio.wait_for(recv.done, timeout=args.timeout)
    except asyncio.TimeoutError:
        print("receiver: timeout waiting for END, flushing what we have")
    fb.cancel()

    trace = JsonlWriter(run_dir / "trace.jsonl")
    total_recv = 0
    for vid, m in enumerate(manifests):
        got = sorted(recv.received.get(vid, []))
        total_recv += len(got)
        trace.write({"video_id": vid, "video": m.video, "label": m.label,
                     "n_frames": m.n_frames, "received": got,
                     "lat_ms": recv.lat.get(vid, [])})
    trace.close()
    print(f"receiver: {total_recv} complete frames across "
          f"{len(recv.received)} videos -> {run_dir / 'trace.jsonl'}")


def main():
    ap = argparse.ArgumentParser(description="semantic-gateway receiver")
    ap.add_argument("--manifests", required=True)
    ap.add_argument("--listen-host", default="0.0.0.0")
    ap.add_argument("--listen-port", type=int, default=6000)
    ap.add_argument("--proxy-host", default="127.0.0.1")
    ap.add_argument("--proxy-port", type=int, default=5000)
    ap.add_argument("--feedback-interval", type=float, default=0.5)
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--run-dir", required=True)
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
