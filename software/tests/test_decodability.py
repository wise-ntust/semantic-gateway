from semantic_gateway.decodability import usable_frames
from semantic_gateway.manifest import GOP, ancestor, layer_of


def test_layer_pattern():
    assert layer_of(0) == 0 and layer_of(4) == 0
    assert layer_of(2) == 1 and layer_of(6) == 1
    assert layer_of(1) == 2 and layer_of(3) == 2


def test_ancestor_chain():
    assert ancestor(0) is None
    assert ancestor(GOP) is None  # next I frame
    assert ancestor(4) == 0
    assert ancestor(2) == 0
    assert ancestor(3) == 2
    assert ancestor(6) == 4


def test_all_received_all_usable():
    n = 2 * GOP
    assert usable_frames(set(range(n)), n) == set(range(n))


def test_layer_drop_keeps_everything_usable():
    """Dropping whole layers (semantic policy) never strands a survivor."""
    n = 2 * GOP
    kept = {i for i in range(n) if layer_of(i) <= 1}
    assert usable_frames(kept, n) == kept


def test_blind_drop_strands_descendants():
    """Losing an L0 frame makes its whole subtree unusable."""
    n = GOP
    received = set(range(n)) - {4}
    usable = usable_frames(received, n)
    assert 4 not in usable
    assert 6 not in usable  # L1 refs frame 4
    assert 5 not in usable and 7 not in usable  # L2 chain
    assert 8 not in usable  # next L0 refs frame 4
    assert 0 in usable and 1 in usable and 2 in usable and 3 in usable


def test_lost_i_frame_kills_gop():
    n = 2 * GOP
    received = set(range(n)) - {0}
    usable = usable_frames(received, n)
    assert not any(i in usable for i in range(GOP))
    assert all(i in usable for i in range(GOP, 2 * GOP))
