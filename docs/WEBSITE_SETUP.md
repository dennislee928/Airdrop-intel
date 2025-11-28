# Airdrop Intel Website 設置指南

## 概述

這是一個使用 Next.js 構建的 8-bit 復古電玩風格的空投情報儀表板網站。網站會自動從 Airdrop Intel Pipeline 生成的 JSON 文件中讀取數據並顯示。

## 功能特點

- 🎮 **8-bit 像素風格設計**：使用 Press Start 2P 字體和像素化視覺效果
- ⚡ **實時數據視覺化**：顯示空投事件、統計數據和警報
- 🎯 **互動式過濾和排序**：可按狀態、來源等篩選空投
- 📊 **統計儀表板**：顯示總事件數、活躍空投、警報等統計信息
- 🎨 **動態視覺效果**：使用 Framer Motion 實現流暢動畫

## 技術棧

- **Next.js 14**：React 框架，使用 App Router
- **TypeScript**：類型安全
- **Framer Motion**：動畫庫
- **CSS Modules**：樣式管理

## 本地開發

### 前置要求

- Node.js 20 或更高版本
- npm 或 yarn

### 設置步驟

1. 進入網站目錄：
```bash
cd website
```

2. 安裝依賴：
```bash
npm install
```

3. 確保數據文件存在：
   - 將 `output/events_sources.json` 複製到 `website/public/data/`
   - 將 `output/wallets_report.json` 複製到 `website/public/data/`（可選）
   - 將 `output/alerts.json` 複製到 `website/public/data/`（可選）

4. 啟動開發服務器：
```bash
npm run dev
```

5. 在瀏覽器中打開 `http://localhost:3000`

## 構建和部署

### GitHub Pages 部署

網站會通過 GitHub Actions 自動構建和部署到 GitHub Pages。

#### 設置 GitHub Pages

1. 前往倉庫的 Settings > Pages
2. 在 "Source" 下選擇 "GitHub Actions"
3. 確保 `Generate_Website.yml` workflow 有正確的權限

#### Workflow 觸發條件

- **自動觸發**：當 `Airdrop Intel Pipeline` workflow 完成時
- **手動觸發**：通過 GitHub Actions 界面手動觸發
- **定時觸發**：每小時執行一次（在 pipeline 之後）

### 本地構建

```bash
cd website
npm run build
```

構建輸出會在 `website/out/` 目錄中。

## 數據文件格式

### events_sources.json

```json
[
  {
    "token": null,
    "project": "Project Name",
    "campaign_name": "Campaign Name",
    "source": "airdrops_io",
    "status": "active",
    "type": "airdrop",
    "reward_type": "token",
    "est_value_usd": null,
    "deadline": null,
    "requirements": [],
    "links": {
      "details": "https://example.com"
    }
  }
]
```

### wallets_report.json

```json
[
  {
    "name": "main_eth",
    "chain": "ethereum",
    "address": "0x...",
    "tx_count": 100,
    "has_defi_activity": true
  }
]
```

### alerts.json

```json
[
  {
    "id": "alert-1",
    "type": "listing",
    "priority": "high",
    "project": "Project Name",
    "message": "Alert message",
    "links": {
      "details": "https://example.com"
    }
  }
]
```

## 自定義樣式

所有樣式定義在 `app/globals.css` 中。主要變量：

- `--bg-primary`：主背景色
- `--pixel-green`：綠色像素色
- `--pixel-cyan`：青色像素色
- `--pixel-yellow`：黃色像素色
- `--pixel-red`：紅色像素色

## 組件結構

```
website/
├── app/
│   ├── layout.tsx       # 根布局
│   ├── page.tsx         # 主頁面
│   └── globals.css      # 全局樣式
├── components/
│   ├── Header.tsx       # 頁面標題
│   ├── StatsPanel.tsx   # 統計面板
│   ├── AirdropList.tsx # 空投列表
│   ├── AirdropCard.tsx # 空投卡片
│   └── LoadingScreen.tsx # 載入畫面
└── public/
    └── data/            # 數據文件目錄
```

## 故障排除

### 數據文件未載入

- 確保 JSON 文件在 `public/data/` 目錄中
- 檢查瀏覽器控制台是否有錯誤
- 確認 JSON 文件格式正確

### 樣式未應用

- 清除瀏覽器緩存
- 確認 `globals.css` 已正確導入
- 檢查字體是否正確載入

### 構建失敗

- 檢查 Node.js 版本（需要 20+）
- 確認所有依賴已正確安裝
- 查看 GitHub Actions 日誌獲取詳細錯誤信息

## 更新日誌

- v1.0.0：初始版本，包含基本功能和 8-bit 風格設計

