# Airdrop Intel Pipeline – Project Structure

本文件說明本專案的目錄結構、各元件責任分工與資料流，方便後續維護與擴充。

---

## 1. Top-level 結構總覽

```text
airdrop-intel-pipeline/
├─ config/
│  ├─ tokens.yml
│  ├─ wallets.yml
│  ├─ rules.yml
│  └─ sources.yml
├─ scripts/
│  ├─ fetch_sources.py
│  ├─ check_wallets.py
│  ├─ aggregate.py
│  ├─ notify_github.py
│  └─ notify_discord.py
├─ output/
│  ├─ events_sources.json
│  ├─ wallets_report.json
│  ├─ alerts.json
│  └─ latest_report.md
├─ .github/
│  └─ workflows/
│      └─ pipeline.yml
├─ requirements.txt
├─ README.md
└─ project_structure.md
```

## 2. 目錄與檔案職責說明

### 2.1 config/ – 設定與策略

集中管理所有可調整設定，盡量避免把 magic number / hard-code 寫在程式內。

#### config/tokens.yml

定義追蹤的幣種與專案，例如 MON、BGB，以及未來關注的 L1 / L2 / DeFi 專案。

**用途**：
- `scripts/fetch_sources.py` 可利用 `coingecko_id` / `coinmarketcap_id` 查詢市場資訊
- `scripts/aggregate.py` 可利用 `watch` 標誌決定哪些 event 需要提高優先級

#### config/wallets.yml

定義需要檢查的自有錢包（多鏈、多地址皆可）。

**用途**：
- `scripts/check_wallets.py` 會針對每個地址呼叫對應鏈的區塊瀏覽器 API（目前示範 Ethereum / Etherscan）
- `output/wallets_report.json` 會輸出這些地址的活動指標（例如交易次數）
- `latest_report.md` 會列出這些地址供使用者在 EarnDrop / Bankless Claimables 等網站手動查詢

#### config/rules.yml

定義「什麼樣的情況需要提醒」的規則與優先級（Rule Engine）。

**用途**：
- `scripts/aggregate.py` 透過這些規則，將 `events_sources.json` 與 `wallets_report.json` 匹配，產生 `alerts.json` 與對應優先級
- 將策略從程式碼抽離，方便日後調整判斷標準（例如提高 tx 門檻、改變關注鏈別…）

#### config/sources.yml

定義外部資訊來源（空投追蹤站、列表站、錢包工具），並標記其類型。

**用途與設計**：
- `mode = "list"`: 表示此來源提供「可爬取的空投／活動列表」，由 `fetch_sources.py` 調用對應的收集函式
- `mode = "wallet_tool"`: 表示是與錢包互動的網站（EarnDrop / Bankless Claimables），不做爬蟲或自動操作，僅在 `latest_report.md` 中提供官方入口鏈結與需檢查的地址

### 2.2 scripts/ – Pipeline 核心邏輯

這個資料夾放的是整條情資管線的 Python 腳本。它們透過 GitHub Actions 依序執行。

#### scripts/fetch_sources.py

**職責**：
- 讀取 `config/sources.yml` 與 `config/tokens.yml`
- 根據啟用的來源，抓取空投 / 活動清單，例如：
  - Airdrops.io
  - CoinMarketCap Airdrops
  - Airdrop Checklist
  - 以及未來的 AltcoinTrading / AirdropsAlert / ICOMarks …
- 將不同網站的資料轉成統一 event 格式，輸出為：`output/events_sources.json`

**特性**：
- 包含錯誤處理與重試機制
- 日誌記錄
- Rate limiting 處理
- 驗證 URL 與回應格式

#### scripts/check_wallets.py

**職責**：
- 讀取 `config/wallets.yml`
- 呼叫對應鏈的公開 API（目前示範 Ethereum / Etherscan）：
  - 取得交易次數等活動指標
- 產生錢包活動報告：`output/wallets_report.json`

**未來可擴充**：
- 多鏈支援（Arbitrum / Optimism / Solana 等），接對應區塊瀏覽器 API
- 資料維度（例如 DeFi 合約互動、NFT 持有等）

#### scripts/aggregate.py

**職責**：
- 讀取：
  - `output/events_sources.json`
  - `output/wallets_report.json`
  - `config/rules.yml`
  - `config/sources.yml`
- 根據規則引擎將 event 與錢包活動匹配，產生 alert：
  - 判斷優先級（high / medium / low）
  - 標記 alert 類型（新 Launchpool、新空投、潛在 retroactive 空投 profile …）
- 輸出：
  - `output/alerts.json` – 給機器讀取，後續用於建立 GitHub Issues / 通知
  - `output/latest_report.md` – 給人閱讀的每日報告

**報告包含**：
- 高優先級的空投 / 活動清單
- 你的錢包活動摘要
- EarnDrop / Bankless Claimables 等錢包工具入口與需檢查的地址列表

#### scripts/notify_github.py

**職責**：
- 讀取 `output/alerts.json`
- 使用 `GITHUB_TOKEN` 連線至當前 repo
- 根據每一條 alert 建立對應的 GitHub Issue：
  - title 範例：`[MON] Monad - New listing / campaign`
  - body 包含：類型、優先級、來源、交易所/錢包資訊、notes、連結
  - labels 預設為：airdrop、launchpool、wallet-profile 等
- 包含去重邏輯，避免重複建立相同 Issue

**搭配使用**：
- GitHub Projects 自動化規則，可將新 Issue 自動加入「Airdrop & Launchpool」看板，作為後續手動操作的任務卡片

#### scripts/notify_discord.py（選用）

**職責**：
- 讀取 `output/alerts.json`
- 從中挑出高優先級 alert（例如前 3 筆）
- 若有設定 `DISCORD_WEBHOOK_URL`，則發送簡短摘要訊息到指定 Discord channel

**特性**：
- 此模組為選用，未設定 webhook 也不影響主流程
- 包含錯誤處理與日誌記錄

### 2.3 output/ – Pipeline 輸出

此目錄由程式自動產出與覆寫，不建議手動修改。

#### events_sources.json

從各空投追蹤站與列表站抓回的原始 event 集合（已做基本 normalize）。

#### wallets_report.json

各錢包在不同鏈上的活動指標（例如交易次數）。

#### alerts.json

經規則引擎篩選後的 alert，供 `notify_github.py` / `notify_discord.py` 使用。

#### latest_report.md

每次 pipeline 跑完對人類友好的摘要報告，包含：
- 高優先級事件清單
- 錢包活動摘要
- EarnDrop / Bankless Claimables 等工具入口與需檢查的地址

### 2.4 .github/workflows/ – CI / 定時任務

#### .github/workflows/pipeline.yml

**職責**：
- 定義 Airdrop Intel Pipeline 的執行時機與步驟

**主要特性**：
- **觸發條件**：
  - `schedule`: 例如每小時一次（`cron: "0 * * * *"`）
  - `workflow_dispatch`: 可於 GitHub 網頁介面手動觸發
- **典型步驟**：
  1. checkout repo
  2. 安裝 Python 與依賴套件（對應 `requirements.txt`）
  3. 依序執行：
     - `scripts/fetch_sources.py`
     - `scripts/check_wallets.py`
     - `scripts/aggregate.py`
     - `scripts/notify_github.py`
     - `scripts/notify_discord.py`（若有 webhook）
- **透過 GitHub Secrets 注入敏感資訊**：
  - `CMC_API_KEY`
  - `ETHERSCAN_API_KEY`
  - `DISCORD_WEBHOOK_URL`
  - `GITHUB_TOKEN`（由 GitHub 自動提供，不需手動設定）

### 2.5 其他檔案

#### requirements.txt

列出 Python 依賴套件，例如：
- requests
- PyYAML
- beautifulsoup4
- PyGithub

#### README.md

專案說明與使用教學，包含功能簡介、安裝步驟、設定檔樣板與安全注意事項。

#### project_structure.md

即本文件，用於說明架構設計與各元件責任。

## 3. 資料流與控制流程

以下描述從資料來源 → 分析 → 通知的完整流程。

```
GitHub Actions (pipeline.yml)
    │
    ├─→ fetch_sources.py ──→ events_sources.json ──┐
    │                                                 │
    ├─→ check_wallets.py ──→ wallets_report.json ──┤
    │                                                 │
    │                                                 ├─→ aggregate.py ──→ alerts.json ──┐
    │                                                 │                    latest_report.md │
    │                                                 │                                    │
    │                                                 └─→ rules.yml ──────────────────────┤
    │                                                                                      │
    └─→ notify_github.py ←───────────────────────────────────────────────────────────────┘
    │
    └─→ notify_discord.py ←───────────────────────────────────────────────────────────────┘
            │
            └─→ GitHub Issues + Projects 看板
            └─→ Discord Channel
```

**功能邊界**：

本專案只做：
- 資訊蒐集 / 監控
- 錢包資格預檢（read-only API）
- 任務管理 & 通知（Issues / 看板 / Discord）

不做：
- 自動下單 / 買幣
- 自動質押 / Launchpool 參與
- 自動簽名 / 授權 / 轉帳

所有實際操作均由使用者在交易所或錢包介面手動完成。

## 4. 後續擴充方向（簡要）

- **新增更多「列表來源」**：例如專門追蹤 L2 / NFT / DeFi 的空投站
- **新增更多「鏈」與 API**：Arbitrum / Optimism / Base / Solana / Sui 等
- **增加規則**：針對特定專案自訂條件（如 MON 第二輪空投、特定 DeFi 互動…）
- **加上快照紀錄**：保存歷史 alerts，做長期策略回顧（哪些提醒實際有收益）

本結構刻意模組化，讓你可以針對來源、規則、通知方式各自演進，而不影響整體流水線。
