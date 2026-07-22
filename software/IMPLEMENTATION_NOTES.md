# Implementation notes

> 給 REPORT.md 的 Implementation 段用。邊做邊記。

## 組成

- 語言：Python 3.10+（pipeline 與模型側共用 `semantic_gateway` package）
- pipeline：`sender.py` / `proxy.py` / `receiver.py`，asyncio UDP，約 600 LOC
- 模型側（king）：`model/`，PyTorch + torchvision + PyAV，約 700 LOC
- 測試床：Linux netns + veth + `tc netem`（delay only），`testbed/netns.sh`

## 關鍵設計決策

1. **Manifest 驅動重播，不送真實 bitstream**。
   sender 重播「每 frame 的真實編碼大小 + tag」，payload 是 dummy bytes。
   accuracy 由 king 離線用 trace（哪些 frame 活下來）對原始影片算。
   理由：網路行為只取決於封包大小與時序；解耦後 GPU 與網路實驗互不綁死，
   且每個 run 完全可重現。

2. **頻寬由 proxy 的 token bucket 模擬，不用 tc rate**。
   AP 要能看到自己的 queue（H2 的觸發訊號），tc 的 qdisc queue 對
   userspace 不可見。token bucket rate = 模擬的無線鏈路速率，
   rate schedule 直接對應 MCS 變化。tc netem 只加傳播延遲。

3. **Decodability 規則是單一事實來源**（`decodability.py`）。
   hierarchical-P 參考鏈：I←L0←L1←L2。收到但祖先斷了 = 不可用。
   semantic policy 按層丟，倖存集必可解；uniform / tail 盲丟會壞鏈，
   這個差距正是實驗要量的東西。receiver 統計與 tests 共用同一函式。

4. **時間壓縮重播（speed factor）**。
   frame 到達率與鏈路速率同倍縮放，queue 行為（以封包計）不變，
   牆鐘時間除以 speed。全 test set 一個 config 從 ~7.4h 壓到 ~55min（x8）。

## Modeling assumptions（報告要誠實寫）

- x264 出的是 IPPP，不是真 hierarchical-P；frame 大小取自真編碼，
  參考結構用我們的 pattern（GOP 32、4-frame 階層）。
- B-frame 不存在（`bframes=0`），符合低延遲串流實務。
- feedback trigger 的 loss 估計來自 frame index gap，等效 RTCP RR 粒度。

## 踩過的坑

- Windows ssh 不吃 `;` 串接、輸出是 UTF-16（`tr -d '\0'` 處理）。
- king 無 WSL：mmaction2 放棄，torchvision 模型 zoo 就夠。
- `QueueDepthTrigger` 的 dwell 基準時間要 lazy init，不然測試沒法注入時鐘。
- **uniform baseline 不能用 `i % mod == 0`**：temporal layer 本身就是
  index 奇偶 pattern，modulo 抽樣會跟 semantic policy 完全重合（偽 baseline）。
  改成 seeded Bernoulli。第一次 smoke 之後才發現。
- **layer drop 省的是 frame 數不是 bytes**：L2 佔 50% frames 但只佔 ~21% bytes，
  所以 semantic 在同 byte 預算下會走到比表面 keep-ratio 更深的 level。
  公平性由共同的 token-bucket link rate 保證，不用 keep-ratio 對齊。

## 第一次 smoke（synthetic，50% 頻寬，2026-07-22）

semantic：received 29.1% / usable 24.4% / mean 146ms
tail：received 82.1% / usable **7.9%** / mean 269ms
→ 同鏈路下 semantic 可用 frame 是 tail 的 3 倍，H1 方向正確。
