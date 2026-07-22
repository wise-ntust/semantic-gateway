from semantic_gateway import rtp


def test_roundtrip():
    p = rtp.Packet(ptype=rtp.T_DATA, video_id=42, frame_idx=1337, layer=2,
                   diff_q=200, frag_idx=3, frag_cnt=9, last_frag=False,
                   send_ns=123456789, payload_len=1400)
    q = rtp.unpack(rtp.pack(p))
    assert q == p


def test_fragments_cover_size():
    frags = rtp.fragments(1, 2, 0, 0, size=45000, send_ns=0)
    assert sum(f.payload_len for f in frags) == 45000
    assert frags[-1].last_frag and not frags[0].last_frag
    assert all(f.frag_cnt == len(frags) for f in frags)


def test_zero_size_frame_still_one_packet():
    frags = rtp.fragments(1, 2, 0, 0, size=0, send_ns=0)
    assert len(frags) == 1 and frags[0].payload_len == 0
