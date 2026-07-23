"""Drop policies and pressure triggers.

The proxy models the AP: a token-bucket egress link with a bounded queue.
When the link cannot carry the offered load, something must be dropped.
Policies differ only in HOW they choose; the link and queue are identical.

Pressure levels (rate-adaptive policies):
  0: no pressure          keep all frames        (30 fps)
  1: drop layer 2         keep 1/2 of frames     (15 fps)
  2: drop layers >= 1     keep 1/4 of frames     (7.5 fps)
  3: keep I frames only   keep 1/GOP of frames   (~1 fps)

`uniform` mirrors the same keep ratios but picks frames by index, blind to
layers, so it breaks reference chains. That contrast is the experiment.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

from .manifest import GOP

KEEP_MOD = {0: 1, 1: 2, 2: 4, 3: GOP}  # keep frames where i % mod == 0


@dataclass
class QueueState:
    """What a policy is allowed to see."""
    queue_bytes: int = 0
    queue_cap: int = 256 * 1024
    pressure: int = 0

    @property
    def occupancy(self) -> float:
        return self.queue_bytes / self.queue_cap if self.queue_cap else 0.0


class Policy:
    name = "base"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def admit(self, frame_idx: int, layer: int, diff_q: int, size: int,
              q: QueueState) -> bool:
        raise NotImplementedError


class TailDrop(Policy):
    """Blind AP behaviour: admit until the queue is full."""
    name = "tail"

    def admit(self, frame_idx, layer, diff_q, size, q):
        return q.queue_bytes + size <= q.queue_cap


class UniformDrop(Policy):
    """Layer-blind random thinning at the same keep-ratio ladder as the
    semantic policy (seeded Bernoulli per frame).

    NOT `frame_idx % mod == 0`: temporal layers are index-parity based, so a
    modulo rule would accidentally reproduce the semantic policy exactly.
    Random thinning is what an AP that cannot read tags could actually do,
    and it breaks reference chains — that contrast is the experiment."""
    name = "uniform"

    def __init__(self, seed: int = 0):
        super().__init__(seed)
        self.rng = random.Random(seed)

    def admit(self, frame_idx, layer, diff_q, size, q):
        if q.queue_bytes + size > q.queue_cap:
            return False
        return self.rng.random() < 1.0 / KEEP_MOD[q.pressure]


class KeyframeProtect(Policy):
    """Content-aware but task-blind (Gobatto-style): I frames may use the
    whole queue; non-I frames only the first 90%, so under congestion the
    remaining headroom is reserved for keyframes."""
    name = "keyframe"
    NON_I_FRAC = 0.9

    def admit(self, frame_idx, layer, diff_q, size, q):
        cap = q.queue_cap if frame_idx % GOP == 0 \
            else int(q.queue_cap * self.NON_I_FRAC)
        return q.queue_bytes + size <= cap


class SemanticDrop(Policy):
    """Ours: drop whole temporal layers, highest first."""
    name = "semantic"

    def admit(self, frame_idx, layer, diff_q, size, q):
        if q.queue_bytes + size > q.queue_cap:
            return False
        if q.pressure == 0:
            return True
        if q.pressure == 1:
            return layer <= 1
        if q.pressure == 2:
            return layer == 0
        return frame_idx % GOP == 0


POLICIES: dict[str, type[Policy]] = {
    p.name: p for p in (TailDrop, UniformDrop, KeyframeProtect, SemanticDrop)
}


@dataclass
class QueueDepthTrigger:
    """Instant link-local signal: queue occupancy with hysteresis + dwell."""
    up: float = 0.70
    down: float = 0.25
    dwell_s: float = 0.3
    level: int = 0
    _last_change: float | None = None

    def update(self, occupancy: float, now: float | None = None) -> int:
        now = time.monotonic() if now is None else now
        if self._last_change is None:
            self._last_change = now
            return self.level
        if now - self._last_change >= self.dwell_s:
            if occupancy > self.up and self.level < 3:
                self.level += 1
                self._last_change = now
            elif occupancy < self.down and self.level > 0:
                self.level -= 1
                self._last_change = now
        return self.level


@dataclass
class FeedbackTrigger:
    """Application-layer baseline: an AP that adapts from receiver loss reports
    instead of its own queue. Two inherent limits vs the queue trigger, both
    fundamental rather than tunable: (1) it sees loss only AFTER frames were
    already dropped downstream, and (2) only once per report interval.

    Uses fast-up / slow-down hysteresis (escalate on the first high-loss
    report, de-escalate only after `hold_reports` sustained low-loss reports)
    so it is a fair controller, not a strawman that oscillates every report.
    The remaining gap to the queue trigger is the signal itself, which is
    exactly what H2 is about."""
    up: float = 0.05         # escalate above 5% observed loss
    down: float = 0.01
    hold_reports: int = 4    # sustained low-loss reports before de-escalating
    level: int = 0
    _low_streak: int = 0

    def on_report(self, loss_ratio: float) -> int:
        if loss_ratio > self.up and self.level < 3:
            self.level += 1
            self._low_streak = 0
        elif loss_ratio < self.down:
            self._low_streak += 1
            if self._low_streak >= self.hold_reports and self.level > 0:
                self.level -= 1
                self._low_streak = 0
        else:
            self._low_streak = 0
        return self.level
