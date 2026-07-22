# semantic-gateway: AP 上的語意感知封包丟棄

> Stage 1 proposal。目標是研究本身，不是投稿。deliverable 是可重現實驗 + 成果報告。

## Problem

無線 AP 轉發影像串流給 AI 推論時，頻寬會因使用者變多或 channel 變差而掉下來。現有 AP 用 tail-drop：queue 滿了就丟最後到的封包，完全不看內容。

對 AI 來說，丟掉 scene-change frame 和丟掉冗餘 frame 的代價差非常多，但 AP 分不出來。錯的 bits 被丟掉，accuracy 就崩，即使總量丟得不多。

## Key insight

本研究的核心想法是：**frame 對 AI 的價值可以在 sender 端算好、寫進 RTP header，讓 AP 由 link-layer 訊號觸發、只讀 header 就做出對 AI 最無害的丟棄**。

運算（價值判斷）搬到 sender，決策（丟誰、何時丟）留在最早知道頻寬變化的 AP。

## Hypotheses（可否證，各自對應實驗）

- **H1（policy）**：同樣頻寬預算下，semantic drop（sender-tagged）的 accuracy 顯著高於 uniform drop 與 tail-drop。
  證據：UCF101 上 3 種 policy 的 accuracy vs bandwidth 曲線。
- **H2（trigger，縮小版）**：queue depth 代理訊號觸發的 drop，比 application-layer 回饋反應快，transient 期間損失的關鍵 frame 更少。
  證據：頻寬階躍情境下的 adaptation latency 與 transient accuracy。完整 link-layer 訊號（retry / MCS）版併入 H5 上板時量。
- **H3（frame vs feature）**：存在一個頻寬門檻：低於它時傳 feature 的 accuracy-latency 優於傳 frame，高於它則相反。
  證據：等頻寬預算下 split-point 掃描的 crossover 圖。
- **H4（deployability，ARM）**：header-only 決策在 ZedBoard ARM PS 上 per-packet overhead < 10 µs，throughput 不降。
  證據：上板 microbenchmark。10 月底前完成，當 H5 的前哨驗證。
- **H5（deployability，FPGA，正式目標）**：drop 決策可以放進 openwifi TX datapath 的 PL 端（RTP tag parser + queue / retry / MCS 直讀），資源 < 2K LUTs，轉發 throughput 不降、決策零 PS 參與。
  證據：Vivado synthesis 資源報告 + 上板 throughput / latency 對比 ARM 版。排 11 至 12 月。

## Closest prior work

| 工作 | 他們做什麼 | 我們差在哪 |
|------|-----------|-----------|
| Gobatto et al. 2022 (arXiv:2202.04703) | NetFPGA L2 switch 上 content-aware drop：congestion 時保 IRAP NAL、先丟 non-IRAP | 他們目標是影像品質、有線 switch、模擬評估。我們目標是 AI accuracy、真實 WiFi link-layer 訊號、GOP 階層（temporal layer）丟棄正是他們自列的 future work，另加 frame vs feature |
| Reducto (SIGCOMM '20) | on-camera frame filtering，low-level feature differencing 動態調門檻保 query accuracy | 過濾在 sender、由 compute 成本驅動。我們丟棄在網路內、由鏈路狀態驅動，sender 只標記不決策 |
| DDS (SIGCOMM '20) | server-driven streaming，server DNN 回饋決定哪些區域重送高畫質 | 回饋迴圈跨整個網路，反應以 RTT 計。我們決策在 AP，以 link-layer 訊號即時反應 |
| Vigil (MobiCom '15) | edge node co-located with camera 挑 frame 上傳，省無線頻寬 | application layer、edge 要跑視覺分析。我們 AP 只讀 header，µs 級成本 |
| Split computing 線（Neurosurgeon；Matsubara et al. survey, CSUR '22；Lee et al. '19） | device 與 server 之間切 DNN、傳 intermediate feature | 我們把 frame drop 與 feature 傳輸放進同一個 AP 頻寬預算下直接對比，回答 tradeoff 本身 |

Novelty scan 結論：**gap 乾淨**。「AP 上、link-layer 訊號觸發、以 AI accuracy 為目標的 semantic drop + frame vs feature 對比」這個組合沒有人做。

## Feasibility

- **Build**：sender（GStreamer/Python，temporal layer 或 frame-diff 標記）→ UDP proxy（policy 引擎，重用 coding-gateway 的 transport / EWMA）→ receiver（mmaction2 預訓練 TSN/TSM）
- **Measure**：accuracy、end-to-end latency、bandwidth、adaptation latency、(H4) per-packet overhead
- **Resources**：king（RTX 3080）跑模型、docker testbed 重用 coding-gateway、實驗室 ZedBoard openwifi、UCF101（約 7 GB）

## Risks

1. **Encoder 的 temporal-layer 支援**：x264 沒有 temporal SVC。fallback：RTP header extension 塞 frame-diff score，不需要真 SVC。
2. **Clip sampling 與 frame drop 的交互**：預訓練模型的取樣協定會影響 accuracy 定義。mitigation：固定 receiver-side sampling，Phase 1 先跑 sanity check。
3. **FPGA 時程（H5）**：Vivado + openwifi rebuild 坑多。mitigation：11 月初 timebox 兩週探路；卡死就交付 ARM 版（H4），PL 版留下一期。可行性依據：Gobatto 的 drop module 只要 47 LUTs + 73 FFs，我們估 1-2K LUTs，openwifi 之外的 7020 剩餘資源 >10K LUTs。
4. **淺層 feature 比 frame 大**：split computing 已知問題。mitigation：quantization / top-k 壓縮，本來就是 H3 要掃的軸。

## Deliverable

- `REPORT.md` 成果報告，對齊 coding-gateway 格式
- `research/experiments/` 可重現實驗：每個 run 一個目錄，script + raw data + 環境快照
