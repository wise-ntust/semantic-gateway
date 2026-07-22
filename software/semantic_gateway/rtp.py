"""Minimal RTP-like wire format.

Real RTP with a header extension would carry the same information; for the
research pipeline we use a fixed 24-byte header that the proxy can parse in
one struct call, which is also the exact field set the FPGA parser (H5) will
implement.

Header (network byte order):
  magic     u16   0x5347 ("SG")
  ver_type  u8    high nibble version (1), low nibble type
  layer     u8    temporal layer id
  video_id  u32   index into the manifest list for this run
  frame_idx u32   display-order frame index
  diff_q    u8    quantized frame-difference score 0-255
  flags     u8    bit0: last fragment of frame
  frag_idx  u16   fragment index within frame
  frag_cnt  u16   total fragments of frame
  paylen    u16   payload bytes that follow
  send_ns   u32   sender timestamp, lower 32 bits of ns (latency measurement)

Types: DATA = 0, FEEDBACK = 1, END = 2.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

MAGIC = 0x5347
VERSION = 1
T_DATA, T_FEEDBACK, T_END = 0, 1, 2

_HDR = struct.Struct("!HBBIIBBHHHI")
HEADER_LEN = _HDR.size  # 24
MTU_PAYLOAD = 1400


@dataclass
class Packet:
    ptype: int
    video_id: int
    frame_idx: int
    layer: int
    diff_q: int
    frag_idx: int
    frag_cnt: int
    last_frag: bool
    send_ns: int
    payload_len: int

    @property
    def wire_len(self) -> int:
        return HEADER_LEN + self.payload_len


def pack(p: Packet) -> bytes:
    hdr = _HDR.pack(
        MAGIC,
        (VERSION << 4) | p.ptype,
        p.layer,
        p.video_id,
        p.frame_idx,
        p.diff_q,
        1 if p.last_frag else 0,
        p.frag_idx,
        p.frag_cnt,
        p.payload_len,
        p.send_ns & 0xFFFFFFFF,
    )
    return hdr + b"\x00" * p.payload_len


def unpack(data: bytes) -> Packet:
    (magic, ver_type, layer, video_id, frame_idx, diff_q, flags,
     frag_idx, frag_cnt, paylen, send_ns) = _HDR.unpack_from(data)
    if magic != MAGIC:
        raise ValueError(f"bad magic {magic:#x}")
    return Packet(
        ptype=ver_type & 0x0F,
        video_id=video_id,
        frame_idx=frame_idx,
        layer=layer,
        diff_q=diff_q,
        frag_idx=frag_idx,
        frag_cnt=frag_cnt,
        last_frag=bool(flags & 1),
        send_ns=send_ns,
        payload_len=paylen,
    )


def fragments(video_id: int, frame_idx: int, layer: int, diff_q: int,
              size: int, send_ns: int) -> list[Packet]:
    """Split one encoded frame of `size` bytes into MTU-sized packets."""
    n = max(1, (size + MTU_PAYLOAD - 1) // MTU_PAYLOAD)
    out = []
    remaining = size
    for k in range(n):
        pay = min(MTU_PAYLOAD, remaining) if remaining > 0 else 0
        remaining -= pay
        out.append(
            Packet(
                ptype=T_DATA,
                video_id=video_id,
                frame_idx=frame_idx,
                layer=layer,
                diff_q=diff_q,
                frag_idx=k,
                frag_cnt=n,
                last_frag=(k == n - 1),
                send_ns=send_ns,
                payload_len=pay,
            )
        )
    return out
