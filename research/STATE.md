# semantic-gateway 研究 pipeline 狀態
stage: implementation
venue: 不投稿。deliverable = 可重現實驗 + REPORT.md（對齊 coding-gateway 格式）

## Gates
- [x] G1 proposal 核准（2026-07-22）
- [x] G2 環境 + 實驗計畫核准（2026-07-22）
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

## Open questions
- 津貼與 ZedBoard 排程（等 twisc 確定）
- feature path（RQ3）的 feature 壓縮格式：int8 quantization 起手，top-k 備選（實作時定）
