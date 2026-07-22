# semantic-gateway 研究 pipeline 狀態
stage: experiments
venue: 不投稿。deliverable = 可重現實驗 + REPORT.md（對齊 coding-gateway 格式）

## Gates
- [x] G1 proposal 核准（2026-07-22）
- [x] G2 環境 + 實驗計畫核准（2026-07-22）
- [x] G3 實作驗收（2026-07-22，smoke 通過，H1 機制可見）
- [ ] G3 實作驗收（pipeline end-to-end 會動）
- [ ] G4 實驗結果過目（數據真實且足夠）
- [ ] G5 報告草稿核准
- [ ] G6 review 迴圈收斂（winlab:cc 老師視角 review 取代 PC reviewers）

## Decisions
- 2026-07-22 — 沿用 paper pipeline 但目標是研究不是投稿：venue 階段改為定義 deliverable；writing 產 REPORT.md 不產 LaTeX；review 用 winlab:cc — 使用者指示
- 2026-07-22 — pipeline 檔案放 research/ 不放 paper/ — repo 是研究專案，命名對齊用途
- 2026-07-22 — 功能一（AP transcode）放掉；聚焦 drop policy + frame vs feature — 老師與詠翔信件討論定案
- 2026-07-22 — 命名 semantic-gateway，與 coding-gateway 成對 — 使用者選定
- 2026-07-22 — FPGA（openwifi PL）drop module 列正式目標 H5，排 11 至 12 月；H4 改為 ARM PS 前哨（10 月底）；H2 縮小為 queue-depth 代理版 — 使用者決定

## Decisions（Stage 2）
- 2026-07-22 — 模型路線：king 無 WSL，放棄 mmaction2，改純 PyTorch + torchvision R(2+1)D-18 fine-tune UCF101 — Windows 原生可跑，不需重開機裝 WSL
- 2026-07-22 — 離線重播法：sandbox 跑網路實驗出 trace，king 批次推論算 accuracy — 解耦 GPU 與網路實驗，可重現
- 2026-07-22 — H2 模擬階段用 queue depth 當代理訊號；retry / MCS 上板（H5）才量 — tc netem 給不出 link-layer 訊號

## Stage 3 進度（2026-07-22）
- pipeline + model 腳本 + runner 完成，15 tests 過，PR #1-#5 merged
- synthetic smoke（50% 頻寬）：semantic 24.4 > uniform 20.9 >> tail 8.4 ≈ keyframe 7.1（usable%）
- 真實 manifests smoke（20 支、50%）：semantic 39.9 ≈ uniform 37.4 >> keyframe 18.0 ≈ tail 17.1
- king：UCF101 13,320 支就位、3,783 test manifests 建畢、fine-tune 跑中（GPU 98%）
- 教訓：uniform baseline 的 modulo 抽樣會跟 temporal layer 重合，改 Bernoulli（詳 IMPLEMENTATION_NOTES）

## G3 smoke 結果（2026-07-22，20 支、50% 頻寬、seed 1）
- top-1：semantic 0.90 > uniform 0.80 > keyframe 0.75 >> tail 0.30
- clean-video baseline 93.5%；semantic 半頻寬只掉 3.5pp，tail 崩到 30%
- tail 有 14/20 支 zero-usable（盲丟壞 GOP 鏈）
- 全鏈路驗證通過：trace → usable → decode → model → accuracy
- 記錄在 research/experiments/2026-07-22-smoke-g3/

## Stage 4 前必修（G3 發現）
- **影片選取要分層**：testlist01 前 20 支全同一類，絕對 accuracy 有偏差（跨 policy 排序仍有效）
- queue cap 改用鏈路 RTT 換算，不用固定 256KB
- ≥5 seeds + error bar（plan.md rigor budget）

## Stage 4 進度（2026-07-22）
- G3 三修完成：subset_manifests（分層 3/class=303 支）、proxy --queue-ms（依鏈路 rate 換算，預設 100ms）、aggregate（跨 seed mean±std）
- RQ1 網路掃描啟動：4 policy × 6 budget（1.0/0.75/0.5/0.375/0.25/0.125）× 3 seed = 72 runs
- 單 config 約 4m24s（303 支、x8）；全掃描約 5.3h，resumable（跳過有 summary.json 的）
- 掃描完 → king eval_all 算 accuracy → aggregate 出 mean±std → results.md → G4

## Open questions
- 津貼與 ZedBoard 排程（等 twisc 確定）
- feature path（RQ3）的 feature 壓縮格式：int8 quantization 起手，top-k 備選（實作時定）
- queue cap 深度：改成以鏈路 ms 計（AP 實務 50-200ms），Stage 4 定案；第一次真實 smoke 用固定 256KB 導致 latency 偏高
- semantic vs uniform 在真實 frame 大小下 usable% 接近，勝負要靠 accuracy（L2 frame 很小，byte 上省不多）
