"""Which received frames are actually usable (decodable)?

A frame is usable iff it was received AND its reference ancestor chain is
fully usable. Layer-aware dropping (semantic policy) always yields usable
sets by construction; index-blind dropping (uniform, tail) breaks reference
chains and loses extra frames beyond the ones it dropped. This function is
the single source of truth for that rule, shared by the receiver-side trace
evaluation and the tests.
"""

from __future__ import annotations

from .manifest import ancestor


def usable_frames(received: set[int], n_frames: int) -> set[int]:
    usable: set[int] = set()
    for i in range(n_frames):
        if i not in received:
            continue
        a = ancestor(i)
        if a is None or a in usable:
            usable.add(i)
    return usable
