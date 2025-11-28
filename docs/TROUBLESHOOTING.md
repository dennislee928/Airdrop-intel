# 故障排除指南

## 問題：某些來源沒有收集到資料

### 症狀

執行 pipeline 後，`events_sources.json` 中只有部分來源的資料，例如：
- ✅ `airdrops_io`: 有資料
- ✅ `cmc_airdrops`: 有資料
- ❌ `airdrop_checklist`: 沒有資料
- ❌ `altcointrading_airdrops`: 沒有資料
- ❌ `airdropsalert`: 沒有資料
- ❌ `icomarks_airdrops`: 沒有資料

### 可能原因

1. **CSS Selector 不正確**
   - 網站的 HTML 結構可能與預期不同
   - 網站可能更新了頁面結構

2. **JavaScript 動態載入**
   - 某些網站使用 JavaScript 動態載入內容
   - BeautifulSoup 無法執行 JavaScript，只能解析靜態 HTML

3. **反爬蟲機制**
   - 網站可能檢測到自動化請求並阻擋
   - 可能需要 User-Agent 或其他 headers

4. **URL 不正確**
   - 網站可能改變了 URL 結構
   - 某些頁面可能需要登入

5. **Rate Limiting**
   - 網站可能限制請求頻率
   - 需要增加請求間隔

### 診斷步驟

#### 1. 檢查 Workflow 日誌

在 GitHub Actions 的執行日誌中，查看：
- 是否有錯誤訊息
- 每個來源的執行狀態
- 找到的項目數量

例如：
```
--- 開始處理 Airdrop Checklist ---
抓取 Airdrop Checklist: https://airdropchecklist.com/
Airdrop Checklist 找到 0 個可能的項目
Airdrop Checklist 總共收集到 0 個事件
```

#### 2. 手動測試網站

在瀏覽器中開啟網站，檢查：
- 網站是否正常運作
- 頁面結構是否與預期相同
- 是否需要登入或特殊權限

#### 3. 檢查 HTML 結構

使用瀏覽器開發者工具（F12）：
1. 開啟目標網站
2. 檢查空投項目的 HTML 結構
3. 找出正確的 CSS selector
4. 更新 `fetch_sources.py` 中的 selector

### 解決方案

#### 方案 1：更新 CSS Selector

如果網站結構改變，需要更新 CSS selector：

1. 在瀏覽器中開啟目標網站
2. 使用開發者工具檢查空投項目的 HTML
3. 找出正確的 class 或 id
4. 更新 `scripts/fetch_sources.py` 中對應的 selector

例如，如果 Airdrop Checklist 的結構是：
```html
<div class="airdrop-card">
  <h3 class="project-name">Project Name</h3>
  <a href="/airdrop/123">Details</a>
</div>
```

則需要更新 `fetch_airdrop_checklist` 函數中的 selector。

#### 方案 2：加入 User-Agent

某些網站可能阻擋沒有 User-Agent 的請求。在 `fetch_with_retry` 函數中加入 headers：

```python
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
resp = requests.get(url, timeout=timeout, headers=headers)
```

#### 方案 3：處理 JavaScript 動態內容

如果網站使用 JavaScript 動態載入內容，需要：
- 使用 Selenium 或 Playwright（需要額外設定）
- 或尋找網站的 API endpoint
- 或使用無頭瀏覽器

**注意**：這會大幅增加複雜度和執行時間。

#### 方案 4：暫時停用有問題的來源

如果某個來源持續無法運作，可以在 `config/sources.yml` 中暫時停用：

```yaml
airdrop_checklist:
  enabled: false  # 暫時停用
  mode: "list"
  urls:
    main: "https://airdropchecklist.com/"
```

### 常見問題

#### Q: 為什麼 CMC 的資料顯示 "Loading data..."？

**A**: 這表示 CoinMarketCap 的頁面使用 JavaScript 動態載入內容，BeautifulSoup 無法解析。需要：
1. 檢查 CMC 是否有公開 API
2. 或使用 Selenium 等工具處理 JavaScript

#### Q: 為什麼有些來源的資料都是 "Unknown"？

**A**: 這表示 CSS selector 找到了元素，但無法正確提取標題。需要：
1. 檢查實際的 HTML 結構
2. 更新 selector 或提取邏輯

#### Q: 如何知道某個來源是否被執行？

**A**: 查看 workflow 日誌，應該會看到：
```
--- 開始處理 [來源名稱] ---
抓取 [來源名稱]: [URL]
[來源名稱] 找到 X 個可能的項目
[來源名稱] 總共收集到 X 個事件
```

如果沒有看到這些日誌，表示該來源可能：
- 未在 `sources.yml` 中啟用
- 或配置有誤

### 建議

1. **優先使用有 API 的來源**
   - 如果有公開 API，優先使用 API 而非網頁爬蟲
   - API 更穩定、更快速

2. **定期檢查日誌**
   - 每次執行後檢查日誌
   - 如果某個來源持續失敗，考慮停用或更新

3. **備用方案**
   - 不要完全依賴單一來源
   - 多個來源可以互相補充

4. **尊重網站政策**
   - 遵守 robots.txt
   - 不要過度請求
   - 遵守網站的使用條款

### 需要幫助？

如果遇到問題：
1. 檢查 GitHub Actions 的完整日誌
2. 手動測試目標網站
3. 開啟 Issue 並附上相關日誌和錯誤訊息

