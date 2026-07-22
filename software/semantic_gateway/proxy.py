"""The AP: token-bucket egress link + bounded queue + drop policy.

  sender --UDP--> [proxy: policy -> queue -> token bucket] --UDP--> receiver

The token-bucket rate models the wireless link rate (it is what an MCS
change would move); a rate schedule like "0:8e6,10:2e6" steps it during a
run. The queue is the AP tx queue. Admission decisions are frame-granular:
the decision is made on fragment 0 and remembered for the rest of the frame.

Events out (events.jsonl):
  {"ev":"stats", t, queue, pressure, admitted, dropped, sent_bytes}
  {"ev":"rate",  t, bps}
  {"ev":"level", t, level, trigger}
  {"ev":"drop",  t, video_id, frame_idx, layer, reason}   (sampled)
"""

from __future__ import annotations

import argparse
import asyncio
import time
from collections import deque
from pathlib import Path

from . import rtp
from .metrics import JsonlWriter, write_run_meta
from .policies import POLICIES, FeedbackTrigger, QueueDepthTrigger, QueueState


def parse_schedule(spec: str) -> list[tuple[float, float]]:
    """"0:8e6,10:2e6" -> [(0.0, 8e6), (10.0, 2e6)] (bytes/s)."""
    out = []
    for part in spec.split(","):
        t, r = part.split(":")
        out.append((float(t), float(r)))
    return sorted(out)


class Proxy(asyncio.DatagramProtocol):
    def __init__(self, args, events: JsonlWriter):
        self.args = args
        self.events = events
        self.policy = POLICIES[args.policy](seed=args.seed)
        self.q = QueueState(queue_cap=args.queue_cap)
        self.queue: deque[bytes] = deque()
        self.schedule = parse_schedule(args.rate)
        self.trigger_mode = args.trigger
        self.qtrig = QueueDepthTrigger()
        self.ftrig = FeedbackTrigger()
        self.decisions: dict[tuple[int, int], bool] = {}
        self.admitted = 0
        self.dropped = 0
        self.sent_bytes = 0
        self.t0 = time.monotonic()
        self.transport: asyncio.DatagramTransport | None = None
        self.receiver_addr = (args.receiver_host, args.receiver_port)
        self.sender_addr = None
        self.done = asyncio.get_running_loop().create_future()

    # -- ingress ---------------------------------------------------------
    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        try:
            p = rtp.unpack(data)
        except ValueError:
            return
        if p.ptype == rtp.T_FEEDBACK:
            if self.trigger_mode == "feedback":
                lvl = self.ftrig.on_report(p.diff_q / 255.0)
                if lvl != self.q.pressure:
                    self.q.pressure = lvl
                    self.events.write({"ev": "level", "t": self.now(),
                                       "level": lvl, "trigger": "feedback"})
            return
        if p.ptype == rtp.T_END:
            self.sender_addr = addr
            self.queue.append(data)  # forward END through the queue
            self.q.queue_bytes += len(data)
            return

        key = (p.video_id, p.frame_idx)
        if p.frag_idx == 0:
            ok = self.policy.admit(p.frame_idx, p.layer, p.diff_q,
                                   p.frag_cnt * (rtp.HEADER_LEN + rtp.MTU_PAYLOAD),
                                   self.q)
            self.decisions[key] = ok
            if not ok:
                self.dropped += 1
                if self.dropped % self.args.drop_log_every == 0:
                    self.events.write({"ev": "drop", "t": self.now(),
                                       "video_id": p.video_id,
                                       "frame_idx": p.frame_idx,
                                       "layer": p.layer, "reason": "policy"})
            else:
                self.admitted += 1
        if not self.decisions.get(key, False):
            return
        if self.q.queue_bytes + len(data) > self.q.queue_cap:
            # overflow mid-frame: the frame can never complete downstream
            self.decisions[key] = False
            self.events.write({"ev": "drop", "t": self.now(),
                               "video_id": p.video_id, "frame_idx": p.frame_idx,
                               "layer": p.layer, "reason": "overflow"})
            return
        self.queue.append(data)
        self.q.queue_bytes += len(data)

    # -- egress ----------------------------------------------------------
    async def drain(self):
        tokens = 0.0
        last = time.monotonic()
        rate_i = 0
        stats_at = 0.0
        while True:
            await asyncio.sleep(0.001)
            now = time.monotonic()
            t = now - self.t0
            while rate_i < len(self.schedule) and t >= self.schedule[rate_i][0]:
                self.rate = self.schedule[rate_i][1]
                self.events.write({"ev": "rate", "t": t, "bps": self.rate * 8})
                rate_i += 1
            tokens = min(tokens + self.rate * (now - last), self.rate * 0.05)
            last = now
            while self.queue and tokens >= len(self.queue[0]):
                data = self.queue.popleft()
                self.q.queue_bytes -= len(data)
                tokens -= len(data)
                self.sent_bytes += len(data)
                self.transport.sendto(data, self.receiver_addr)
                if rtp.unpack(data).ptype == rtp.T_END:
                    self.events.write({"ev": "end", "t": t})
                    self.done.set_result(True)
                    return
            if self.trigger_mode == "queue":
                lvl = self.qtrig.update(self.q.occupancy, now)
                if lvl != self.q.pressure:
                    self.q.pressure = lvl
                    self.events.write({"ev": "level", "t": t, "level": lvl,
                                       "trigger": "queue"})
            if t >= stats_at:
                self.events.write({"ev": "stats", "t": round(t, 3),
                                   "queue": self.q.queue_bytes,
                                   "pressure": self.q.pressure,
                                   "admitted": self.admitted,
                                   "dropped": self.dropped,
                                   "sent_bytes": self.sent_bytes})
                stats_at += 0.1

    def now(self) -> float:
        return round(time.monotonic() - self.t0, 4)


async def amain(args):
    run_dir = Path(args.run_dir)
    write_run_meta(run_dir, "proxy", vars(args))
    events = JsonlWriter(run_dir / "events.jsonl")
    loop = asyncio.get_running_loop()
    proxy = Proxy(args, events)
    proxy.rate = proxy.schedule[0][1]
    await loop.create_datagram_endpoint(
        lambda: proxy, local_addr=(args.listen_host, args.listen_port))
    drain = asyncio.create_task(proxy.drain())
    await proxy.done
    drain.cancel()
    events.write({"ev": "summary", "admitted": proxy.admitted,
                  "dropped": proxy.dropped, "sent_bytes": proxy.sent_bytes})
    events.close()


def main():
    ap = argparse.ArgumentParser(description="semantic-gateway AP proxy")
    ap.add_argument("--policy", choices=sorted(POLICIES), required=True)
    ap.add_argument("--trigger", choices=["queue", "feedback"], default="queue")
    ap.add_argument("--rate", default="0:2.5e6",
                    help="schedule t_sec:bytes_per_sec[,t:r...]")
    ap.add_argument("--queue-cap", type=int, default=256 * 1024)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--listen-host", default="0.0.0.0")
    ap.add_argument("--listen-port", type=int, default=5000)
    ap.add_argument("--receiver-host", default="127.0.0.1")
    ap.add_argument("--receiver-port", type=int, default=6000)
    ap.add_argument("--drop-log-every", type=int, default=50)
    ap.add_argument("--run-dir", required=True)
    asyncio.run(amain(ap.parse_args()))


if __name__ == "__main__":
    main()
