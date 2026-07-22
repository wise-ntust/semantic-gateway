# semantic-gateway 研究 pipeline 狀態
stage: setup
venue: 不投稿。deliverable = 可重現實驗 + REPORT.md（對齊 coding-gateway 格式）

## Gates
- [x] G1 proposal 核准（2026-07-22）
- [ ] G2 環境 + 實驗計畫核准
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

## Open questions
- H2 的 link-layer 訊號在 docker 模擬階段怎麼仿真（tc netem 沒有 MCS/retry；可能要用 mac80211_hwsim 或先用 queue depth 代理）
- 津貼與 ZedBoard 排程（等 twisc 確定）
