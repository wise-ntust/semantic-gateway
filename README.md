# semantic-gateway

> Semantic-aware frame dropping at the wireless AP: when bandwidth falls, spend the remaining bits on what the AI actually needs.

---

## The Problem

Video analytics pipelines stream frames from cameras to AI models over wireless links. When bandwidth drops (more users join, the channel degrades), something has to give.

Today that "something" is decided blindly. Queues overflow and tail-drop discards whatever arrives last, regardless of content. A frame carrying a scene change is worth exactly as much as a frame nearly identical to its predecessor. The AI's accuracy collapses not because too many bits were lost, but because the wrong bits were lost.

Transcoding at the AP would help, but is off the table on real hardware: the ZedBoard's Zynq-7020 has no video codec unit, and openwifi already occupies most of the FPGA fabric.

**The AP forwards packets it does not understand. That is the missing piece.**

## The Idea

Make the drop decision semantic, and make it cheap enough to run on an AP.

1. **The sender does the thinking.** Frames are encoded into temporal layers (or tagged with frame-difference scores), and the tag rides in the RTP header.
2. **The AP does the choosing.** It watches link-layer signals (queue depth, retry rate, MCS). When the link degrades, it drops the least valuable layer first. Reading a header costs microseconds: no decoding, no transcoding.
3. **Features instead of frames (bonus).** For frames that survive the drop, an edge node can extract and forward only the intermediate features the AI needs, in fewer bits than the frame itself.

## Research Questions

| # | Question |
|---|----------|
| RQ1 | Which drop policy preserves accuracy best under a bandwidth budget: uniform, size-based, or sender-tagged? |
| RQ2 | Under the same budget, is it better to forward the surviving frames, or extracted features? (latency + accuracy) |
| RQ3 | Can the decision run on the AP itself (ZedBoard ARM PS, openwifi) with negligible forwarding overhead? |

## Relation to coding-gateway

[coding-gateway](https://github.com/wise-ntust/coding-gateway) keeps the link alive: erasure coding across paths, so blockage never stalls the stream. semantic-gateway decides what deserves the link: when capacity shrinks, the bits that matter to inference go first.

Same series, opposite direction. One adds redundancy to survive loss; the other removes redundancy to survive scarcity.

## Roadmap

| Phase | Scope | Status |
|-------|-------|--------|
| 1 | Baseline pipeline: UCF101 + pretrained action-recognition model, RTP sender → proxy → receiver | planned |
| 2 | Drop policies: uniform / size-based / sender-tagged, under emulated bandwidth (`tc netem`) | planned |
| 3 | Frame vs feature: split-point and quantization sweep under an equal bandwidth budget | planned |
| 4 | On-device: RTP-header drop on ZedBoard ARM PS (openwifi), as the sighting shot for Phase 5 | planned |
| 5 | In-fabric: drop module inside the openwifi TX datapath (PL), plus the final report | planned |

## License

[MIT](LICENSE.md), Copyright (c) 2026 WISE Lab, National Taiwan University of Science and Technology
