# Deliverable 定義（取代 paper pipeline 的 venue.md）

不投稿。產出兩件事：

## 1. REPORT.md 成果報告

- 位置：repo 根目錄，對齊 coding-gateway 的成果報告
- 格式：GitHub alerts 版 Markdown（zyx:project-docs 骨架：前言 → 專案簡介 → 系統設計 → 實驗 → 結果 → 結論與交接）
- 語言：繁體中文，技術名詞保留英文
- 圖表：實驗數據全部可追溯到 `research/experiments/` 的 run

## 2. 可重現實驗

- `research/experiments/<date>-<rq>-<tag>/`：script、config、raw data、環境快照
- 任何寫進報告的數字都要能指到一個 run 目錄

## Review 迴圈（取代 PC reviewers）

- `winlab:cc` agent（建超老師視角）review 報告草稿
- 全部意見處理完 + Loki 簽核 = G6
