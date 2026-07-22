from semantic_gateway.manifest import GOP, layer_of
from semantic_gateway.policies import (
    POLICIES,
    QueueDepthTrigger,
    QueueState,
    SemanticDrop,
    UniformDrop,
)


def admitted_set(policy, pressure, n=2 * GOP):
    q = QueueState(queue_bytes=0, queue_cap=10**9, pressure=pressure)
    return {
        i for i in range(n)
        if policy.admit(i, layer_of(i), 128, 5000, q)
    }


def test_semantic_keep_ratios():
    p = SemanticDrop()
    n = 2 * GOP
    assert len(admitted_set(p, 0, n)) == n
    assert len(admitted_set(p, 1, n)) == n // 2
    assert len(admitted_set(p, 2, n)) == n // 4
    assert len(admitted_set(p, 3, n)) == n // GOP


def test_uniform_keep_ratio_statistical():
    u = UniformDrop(seed=7)
    n = 64 * GOP
    kept = admitted_set(u, 1, n)
    assert abs(len(kept) / n - 0.5) < 0.05  # Bernoulli(1/2) within 5%


def test_uniform_is_layer_blind():
    """Uniform must NOT reproduce the temporal-layer pattern."""
    u = UniformDrop(seed=7)
    kept = admitted_set(u, 1, 8 * GOP)
    assert any(i % 2 == 1 for i in kept)   # keeps some L2 frames
    assert any(i % 2 == 0 for i in kept)   # and some base-layer frames
    from semantic_gateway.decodability import usable_frames
    n = 8 * GOP
    assert usable_frames(kept, n) != kept  # chains do break


def test_semantic_survivors_form_decodable_set():
    from semantic_gateway.decodability import usable_frames
    p = SemanticDrop()
    n = 2 * GOP
    for lvl in (0, 1, 2, 3):
        kept = admitted_set(p, lvl, n)
        assert usable_frames(kept, n) == kept


def test_tail_drop_ignores_pressure_until_full():
    t = POLICIES["tail"]()
    q = QueueState(queue_bytes=0, queue_cap=10000, pressure=3)
    assert t.admit(1, 2, 0, 5000, q)
    q.queue_bytes = 9000
    assert not t.admit(2, 2, 0, 5000, q)


def test_trigger_hysteresis_and_dwell():
    tr = QueueDepthTrigger(up=0.7, down=0.25, dwell_s=0.3)
    t = 100.0
    assert tr.update(0.9, t) == 0          # dwell not elapsed since init
    assert tr.update(0.9, t + 0.31) == 1   # escalate
    assert tr.update(0.9, t + 0.32) == 1   # dwell blocks double-escalation
    assert tr.update(0.9, t + 0.63) == 2
    assert tr.update(0.1, t + 0.95) == 1   # de-escalate
    assert tr.update(0.5, t + 1.3) == 1    # in-band: hold
