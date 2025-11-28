# GitHub Secrets 設定指南

本文件說明如何申請和設定 Airdrop Intel Pipeline 所需的所有環境變數（GitHub Secrets）。

## 設定步驟

### 1. 進入 GitHub Repository Settings

1. 開啟你的 GitHub repository
2. 點擊 **Settings**（設定）
3. 在左側選單中找到 **Secrets and variables** → **Actions**
4. 點擊 **New repository secret** 來新增每個 secret

---

## 必要的 Secrets

### 1. ETHERSCAN_API_KEY（必要）

**用途**：用於查詢以太坊鏈上錢包交易次數

**申請方式**：
1. 前往 [Etherscan API](https://etherscan.io/apis)
2. 註冊/登入 Etherscan 帳號
3. 進入 **API-KEYs** 頁面
4. 點擊 **Add** 建立新的 API Key
5. 選擇 **Free** 方案（免費版每 5 秒可發送 5 次請求）
6. 複製生成的 API Key

**在 GitHub 設定**：
- Name: `ETHERSCAN_API_KEY`
- Secret: 貼上你的 Etherscan API Key

**注意**：免費版有 rate limit，如果有多個錢包，建議使用付費方案或增加請求間隔。

---

### 2. CMC_API_KEY（選用）

**用途**：用於 CoinMarketCap Pro API 查詢幣種上市資訊

**申請方式**：
1. 前往 [CoinMarketCap API](https://coinmarketcap.com/api/)
2. 註冊/登入 CoinMarketCap 帳號
3. 選擇 **Basic** 方案（免費版）
4. 填寫申請表單（需要說明用途）
5. 等待審核通過（通常 1-2 天）
6. 在 Dashboard 中複製 API Key

**在 GitHub 設定**：
- Name: `CMC_API_KEY`
- Secret: 貼上你的 CoinMarketCap API Key

**注意**：
- 如果不需要從 CMC API 查詢上市資訊，可以跳過此項
- `fetch_sources.py` 會自動處理 API Key 不存在的情況

---

### 3. DISCORD_WEBHOOK_URL（選用）

**用途**：發送高優先級 alerts 到 Discord channel

**申請方式**：
1. 開啟 Discord，進入你想要接收通知的 Server
2. 進入 Server 設定 → **Integrations** → **Webhooks**
3. 點擊 **New Webhook** 或 **Create Webhook**
4. 設定 Webhook 名稱（例如：`Airdrop Alerts`）
5. 選擇要發送訊息的 Channel
6. 點擊 **Copy Webhook URL**
7. 可以選擇是否顯示頭像和名稱

**在 GitHub 設定**：
- Name: `DISCORD_WEBHOOK_URL`
- Secret: 貼上你的 Discord Webhook URL（格式：`https://discord.com/api/webhooks/...`）

**注意**：
- 如果不使用 Discord 通知，可以跳過此項
- `notify_discord.py` 會自動處理 Webhook URL 不存在的情況

---

### 4. GITHUB_TOKEN（自動提供）

**用途**：用於建立 GitHub Issues

**設定方式**：
- **不需要手動設定**
- GitHub Actions 會自動提供 `GITHUB_TOKEN`
- 在 workflow 中已經自動注入：`${{ secrets.GITHUB_TOKEN }}`

**注意**：如果你的 repository 是 private，可能需要確認 Actions 權限設定。

---

## 驗證設定

### 方法 1：檢查 Secrets 列表

1. 進入 **Settings** → **Secrets and variables** → **Actions**
2. 確認以下 Secrets 已存在：
   - ✅ `ETHERSCAN_API_KEY`（必要）
   - ⚪ `CMC_API_KEY`（選用）
   - ⚪ `DISCORD_WEBHOOK_URL`（選用）
   - ✅ `GITHUB_TOKEN`（自動提供，不需要手動設定）

### 方法 2：執行 Workflow 測試

1. 進入 **Actions** 分頁
2. 選擇 **Airdrop Intel Pipeline**
3. 點擊 **Run workflow** → **Run workflow**
4. 檢查執行日誌，確認：
   - 沒有出現 "API key not found" 錯誤
   - 各腳本正常執行

---

## 常見問題

### Q: Etherscan API Key 有 rate limit 怎麼辦？

**A**: 
- 免費版：每 5 秒 5 次請求
- 如果有多個錢包，可以：
  1. 升級到付費方案
  2. 在 `check_wallets.py` 中增加請求間隔
  3. 減少錢包數量

### Q: CMC API Key 審核需要多久？

**A**: 
- 通常 1-2 個工作天
- 如果被拒絕，檢查申請表單中的用途說明是否清楚
- 可以重新申請

### Q: Discord Webhook 安全嗎？

**A**: 
- Webhook URL 包含 token，應該保密
- 不要將 URL 提交到公開 repository
- 如果 URL 洩漏，立即刪除並建立新的 Webhook

### Q: 可以只設定部分 Secrets 嗎？

**A**: 
- 可以！只有 `ETHERSCAN_API_KEY` 是必要的
- 其他都是選用的，程式會自動處理不存在的情況
- 但建議至少設定 `ETHERSCAN_API_KEY` 和 `DISCORD_WEBHOOK_URL`

---

## 安全建議

1. **不要將 Secrets 提交到 Git**
   - 所有 Secrets 都應該透過 GitHub Secrets 設定
   - 檢查 `.gitignore` 確保沒有敏感檔案被提交

2. **定期輪換 API Keys**
   - 建議每 3-6 個月更新一次 API Keys
   - 如果發現異常活動，立即撤銷並重新申請

3. **限制 Secrets 權限**
   - 只給必要的權限
   - 定期檢查誰有權限存取這些 Secrets

---

## 下一步

設定完成後，請：

1. 更新 `config/wallets.yml` 填入你的實際錢包地址
2. 更新 `config/tokens.yml` 填入你想追蹤的幣種
3. 執行一次 workflow 測試是否正常運作
4. 檢查 `output/latest_report.md` 確認資料收集正常

如有問題，請查看 workflow 執行日誌或開啟 Issue。

