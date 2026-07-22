# 實驗計畫（Stage 2）

> 這份是 implementation 要滿足的合約。寫在 build 之前。

## Research questions

| RQ | 對應假設 | 問題 | 主圖 |
|----|---------|------|------|
| RQ1 | H1 | 同頻寬預算下，哪種 drop policy 保住最多 accuracy？ | accuracy vs bandwidth 曲線，4 policy 對照 |
| RQ2 | H2 | queue-depth 觸發比 application-layer 回饋快多少？ | 頻寬階躍下的 adaptation latency + transient accuracy |
| RQ3 | H3 | 傳 drop 後的 frame 還是傳 feature？crossover 在哪？ | 等預算下 accuracy-latency crossover 圖 |
| RQ4 | H4 | ARM PS 上決策的 per-packet overhead？ | microbenchmark 表 |
| RQ5 | H5 | PL 版塞得下嗎？決策延遲贏 ARM 多少？ | LUT/FF 資源表 + latency 對比 |

## Baselines

1. **tail-drop**：naive baseline，queue 滿丟尾巴（現況 AP 行為）
2. **uniform drop**：平均抽 frame，不看內容
3. **keyframe-protect**：只保 I-frame（Gobatto 風格的近似，content-aware 但 task-blind）
4. **semantic drop（ours）**：sender 標記 temporal layer / diff score，AP 按層丟

RQ3 另加兩條路：**frame path**（drop 後傳 frame）vs **feature path**（drop 後 sender 抽 feature 傳）。

## Dataset 與模型

- **UCF101** split 1（101 類、13,320 支影片），標準 test split，不挑子集
- 模型：**R(2+1)D-18**（torchvision，Kinetics-400 預訓練）fine-tune UCF101
- checkpoint 訓一次就凍結，所有 RQ 共用；baseline top-1 目標 ≥ 92%
- 影片編碼：x264 `zerolatency bframes=0` + **RTP header extension 帶 tag**（layer id + frame-diff score，codec-agnostic）；openh264 temporal SVC 為備案

## 架構決策：離線重播法

網路實驗與 GPU 推論解耦：

1. sandbox（Linux）跑 sender → proxy（policy）→ receiver，`tc netem` 控頻寬，輸出「每 run 實際收到的 frame 集合」trace
2. trace 送 king 批次推論算 accuracy
3. e2e latency = 管線各段實測相加；推論延遲另計

好處：網路 run 不需要 GPU 即時推論，重播可重現，兩台機器各做擅長的事。

## Metrics

- **top-1 accuracy**（全 test set）
- **goodput / 頻寬用量**（proxy 出口實測）
- **e2e latency**：mean 與 **p99** 都報
- **adaptation latency**（RQ2）：階躍到 policy 生效的時間
- **per-packet overhead**（RQ4/5）：µs；**PL 資源**（RQ5）：LUT / FF / BRAM
- ML 成本一併報：feature path 的 sender 端運算時間

## Rigor budget

- 網路實驗：每組 config **≥ 5 runs**（不同 seed 的 loss pattern），報 mean ± std + error bar
- Fine-tune：3 seeds 取中位 checkpoint；之後全程凍結
- 每 run 存：git SHA、config dump、pip freeze、原始 pcap/trace
- 目錄：`research/experiments/<date>-<rq>-<tag>/`

## Kill criteria

| RQ | 否證條件 | 然後呢 |
|----|---------|--------|
| RQ1 | semantic ≤ uniform（誤差內、所有預算點） | 檢查是不是 action recognition 對隨機丟太魯棒；換更吃 temporal 的任務或縮 claims |
| RQ2 | 觸發優勢 < 回饋 RTT 量級 | 縮成 characterization，不當賣點 |
| RQ3 | 沒有 crossover（單邊全贏） | 報 dominance region，一樣是結果 |
| RQ4/5 | overhead 爆表 / PL 塞不下 | 交付量測數據與原因分析；PL 留下一期 |

## 環境 inventory（已探測，2026-07-22）

| 資源 | 路徑 | 狀態 | 用途 |
|------|------|------|------|
| king | `ssh king` | RTX 3080 10GB、driver 610.47、Win11 原生 Python 3.13、**無 WSL** | fine-tune + 批次推論 + feature 抽取 |
| sandbox | `ssh sandbox`（PVE VM 104） | Ubuntu、4C / 7.8G / 89G 空、**docker 未裝**（實作階段補） | 管線 + tc netem 網路實驗 |
| ZedBoard openwifi | 實驗室，11 月起 | 操作手冊在 coding-gateway `fpga/docs/` | RQ4 / RQ5 |
| UCF101 | crcv.ucf.edu，約 6.5 GB | 待下載到 king | dataset |

限制：king 不裝 WSL（要 admin + 重開機，遠端風險高；純 Windows 路線不需要）。iCloud clone 只放文件，實驗程式碼跑在 sandbox / king 的本地 clone。

## 時程對照 roadmap

- Phase 1（8 月）：baseline pipeline = RQ1 的地基
- Phase 2（9 月）：RQ1 + RQ2
- Phase 3（10 月）：RQ3；10 月底 H4 前哨（RQ4）
- Phase 4-5（11 至 12 月）：RQ5 上板 + REPORT.md
