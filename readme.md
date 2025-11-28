一、整體架構（只到通知為止）

用一個 GitHub repo，例如 airdrop-intel-pipeline：

airdrop-intel-pipeline/
├─ config/
│  ├─ tokens.yml          # 追蹤幣種 & 專案 (MON, BGB, 其他)
│  ├─ wallets.yml         # 你自己的地址列表
│  └─ rules.yml           # 什麼樣的條件算「有價值的機會」
├─ scripts/
│  ├─ fetch_sources.py    # 1. 資訊蒐集 / 監控
│  ├─ check_wallets.py    # 2. 錢包資格預檢
│  ├─ aggregate.py        # 統整所有結果，打分數 / 標 priority
│  ├─ notify_github.py    # 3. 建 Issue，給 GitHub Project 使用
│  └─ notify_discord.py   # (選用) 丟到 Discord / Telegram
├─ output/
│  ├─ latest_report.md    # 人看用的報告
│  └─ alerts.json         # 機器用，給後續 workflow 開 Issue
├─ .github/
│  └─ workflows/
│      └─ pipeline.yml    # 定時跑整個流程
├─ requirements.txt
└─ README.md

config 範例

config/tokens.yml：

tokens:
  - symbol: MON
    coingecko_id: "monad"
    coinmarketcap_id: 12345
    watch:
      launchpool: true
      listings: true
      blog: true
  - symbol: BGB
    coinmarketcap_id: 5195
    watch:
      launchpool: true
      listings: false
      blog: false


config/wallets.yml：

wallets:
  - name: main_eth
    chain: ethereum
    address: "0x1111..."
  - name: arb_farming
    chain: arbitrum
    address: "0x2222..."


config/rules.yml（怎樣會被判定成「值得你手動看」）：

rules:
  - id: new_launchpool_for_watched_token
    type: listing
    priority: high
    match:
      category: "launchpool"
      token_in_watchlist: true

  - id: potential_retrospective_airdrop
    type: wallet_activity
    priority: medium
    match:
      has_defi_activity: true
      chain_in: ["ethereum", "arbitrum", "optimism", "solana"]
      tx_count_min: 20

二、GitHub Actions：單一 workflow 跑完整 pipeline
# .github/workflows/pipeline.yml
name: Airdrop Intel Pipeline

on:
  schedule:
    - cron: "0 * * * *"   # 每小時跑一次
  workflow_dispatch:       # 允許手動觸發

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run collectors & analyzers
        env:
          CMC_API_KEY: ${{ secrets.CMC_API_KEY }}
          ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_API_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python scripts/fetch_sources.py
          python scripts/check_wallets.py
          python scripts/aggregate.py
          python scripts/notify_github.py
          python scripts/notify_discord.py


這裡只有用 GITHUB_TOKEN 建 Issue，不動你的金流或私鑰。

三、模組 1：資訊蒐集 / 監控（MON / BGB 等）

只做 HTTP GET，讀公開 API / RSS / HTML，不動資產。

# scripts/fetch_sources.py
import yaml
import json
import os
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TOKENS = ROOT / "config" / "tokens.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

CMC_API_KEY = os.environ.get("CMC_API_KEY")

def load_tokens():
    with open(CONFIG_TOKENS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["tokens"]

def fetch_cmc_market_data(token):
    """示範從 CMC 拉單一幣種資料（上市交易所/市場）。"""
    if not token.get("coinmarketcap_id") or not CMC_API_KEY:
        return None

    url = "https://pro-api.coinmarketcap.com/v2/cryptocurrency/market-pairs/latest"
    params = {"id": token["coinmarketcap_id"], "limit": 100}
    headers = {"X-CMC_PRO_API_KEY": CMC_API_KEY}

    resp = requests.get(url, params=params, headers=headers, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return {
        "token": token["symbol"],
        "source": "coinmarketcap",
        "raw": data,
    }

def normalize_listings(cmc_data):
    """把 CMC 的 listings 轉成統一格式：exchange & pair."""
    if not cmc_data:
        return []

    result = []
    for item in cmc_data["raw"].get("data", {}).get("market_pairs", []):
        result.append({
            "token": cmc_data["token"],
            "type": "listing",
            "exchange": item.get("exchange", {}).get("name"),
            "pair": f'{item.get("base_symbol")}/{item.get("quote_symbol")}',
            "category": "spot",  # 可再細分 margin / derivatives 等
            "source": "coinmarketcap",
        })
    return result

def run():
    tokens = load_tokens()
    all_events = []

    for token in tokens:
        cmc_raw = fetch_cmc_market_data(token)
        listings = normalize_listings(cmc_raw)
        all_events.extend(listings)

        # 日後可以在這邊加：官方 blog / twitter / airdrop 站的 monitoring
        # e.g. monitor_monad_blog(token), monitor_bitget_announcements(token), ...

    with open(OUTPUT_DIR / "events_sources.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()


之後要擴充：

monitor_bitget_launchpool()：抓 Bitget 公告裡含有 Launchpool 且關於 BGB 的

monitor_monad_blog()：抓 Monad 官方 blog / docs 是否出現新的 airdrop / reward 關鍵字

這些都可以 append 到 all_events 同一個 JSON 裡。

四、模組 2：錢包資格預檢（只讀 API）

目標：

檢查你自己的地址是否有足夠的 on-chain 活動，符合「可能空投」的 profile

完全不簽名、不授權、不交易

# scripts/check_wallets.py
import yaml
import json
import os
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_WALLETS = ROOT / "config" / "wallets.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")

def load_wallets():
    with open(CONFIG_WALLETS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["wallets"]

def get_eth_tx_count(address: str) -> int:
    """用 Etherscan API 查看這個地址目前有多少 tx。"""
    if not ETHERSCAN_API_KEY:
        return 0

    url = "https://api.etherscan.io/api"
    params = {
        "module": "proxy",
        "action": "eth_getTransactionCount",
        "address": address,
        "tag": "latest",
        "apikey": ETHERSCAN_API_KEY,
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    return int(data["result"], 16)

def analyze_wallet_activity(wallet):
    """回傳這個錢包的一些指標：tx 數量、是否達標。"""
    chain = wallet["chain"]
    addr = wallet["address"]

    if chain == "ethereum":
        tx_count = get_eth_tx_count(addr)
    else:
        # 其他鏈之後可以接 Arbiscan / Optimistic / Solscan 等
        tx_count = 0

    has_defi_activity = tx_count >= 20  # 先用 tx_count 當粗略 proxy

    return {
        "name": wallet["name"],
        "chain": chain,
        "address": addr,
        "tx_count": tx_count,
        "has_defi_activity": has_defi_activity,
    }

def run():
    wallets = load_wallets()
    reports = [analyze_wallet_activity(w) for w in wallets]

    with open(OUTPUT_DIR / "wallets_report.json", "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    run()


後續可以逐步加強：

查 internal tx / DeFi 協議互動（例如看是否呼叫特定合約地址）

查 NFT balance（例如某些系列被列為空投條件）

對不同鏈（Arbitrum、Optimism、Solana）接對應瀏覽器 API

仍然維持「只查詢、不簽名、不變動資產」。

五、模組 3：整合 & 打分數 → 產出 alerts.json + report

將 events_sources.json + wallets_report.json 合併，再按照 rules.yml 判斷哪些值得你看。

# scripts/aggregate.py
import yaml
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
CONFIG_RULES = ROOT / "config" / "rules.yml"

def load_json(path):
    p = OUTPUT_DIR / path
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def load_rules():
    with open(CONFIG_RULES, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["rules"]

def apply_rules(events, wallets, rules):
    alerts = []

    # 1) 針對 events（上市、Launchpool 等）
    for ev in events:
        for rule in rules:
            if rule["type"] != "listing":
                continue
            if "launchpool" in ev.get("category", "").lower() or \
               "earn" in ev.get("category", "").lower():
                alerts.append({
                    "token": ev["token"],
                    "project": ev.get("project", ev["token"]),
                    "type": "New listing / campaign",
                    "priority": rule["priority"],
                    "source": ev["source"],
                    "exchange": ev.get("exchange"),
                    "pair": ev.get("pair"),
                    "notes": f"Detected new listing/campaign on {ev.get('exchange')} ({ev.get('pair')}).",
                    "labels": ["airdrop", "launchpool"],
                })

    # 2) 針對 wallets（活動量 / 潛在空投 profile）
    for w in wallets:
        for rule in rules:
            if rule["type"] != "wallet_activity":
                continue
            if w["chain"] in rule["match"].get("chain_in", []) and \
               w["tx_count"] >= rule["match"].get("tx_count_min", 0):
                alerts.append({
                    "token": "MULTI",
                    "project": "Generic Airdrop Profile",
                    "type": "Wallet potentially qualifies for retroactive airdrops",
                    "priority": rule["priority"],
                    "source": "wallets_report",
                    "wallet_name": w["name"],
                    "wallet_address": w["address"],
                    "notes": f"Wallet {w['name']} on {w['chain']} has {w['tx_count']} txs.",
                    "labels": ["airdrop", "wallet-profile"],
                })

    return alerts

def write_human_report(alerts):
    lines = ["# Airdrop / Launchpool Daily Report\n"]
    if not alerts:
        lines.append("目前沒有高優先級 alert。")
    else:
        for a in alerts:
            lines.append(f"## [{a['priority'].upper()}] {a['project']} - {a['type']}")
            lines.append(f"- Token: {a['token']}")
            if a.get("exchange"):
                lines.append(f"- Exchange: {a['exchange']} ({a.get('pair')})")
            if a.get("wallet_name"):
                lines.append(f"- Wallet: {a['wallet_name']} ({a['wallet_address']})")
            lines.append(f"- Source: {a['source']}")
            lines.append(f"- Notes: {a['notes']}")
            lines.append("")
    (OUTPUT_DIR / "latest_report.md").write_text("\n".join(lines), encoding="utf-8")

def run():
    events = load_json("events_sources.json")
    wallets = load_json("wallets_report.json")
    rules = load_rules()

    alerts = apply_rules(events, wallets, rules)

    with open(OUTPUT_DIR / "alerts.json", "w", encoding="utf-8") as f:
        json.dump(alerts, f, ensure_ascii=False, indent=2)

    write_human_report(alerts)

if __name__ == "__main__":
    run()

六、模組 4：GitHub Issue / Project 通知（任務管理）

只用 GitHub 官方 token 建 Issue，讓你在看板自己安排「手動操作」。

# scripts/notify_github.py
import json
import os
from pathlib import Path

from github import Github  # PyPI: PyGithub

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"

def load_alerts():
    p = OUTPUT_DIR / "alerts.json"
    if not p.exists():
        return []
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)

def run():
    alerts = load_alerts()
    if not alerts:
        print("No alerts to create issues for.")
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        print("No GITHUB_TOKEN provided.")
        return

    g = Github(token)
    repo = g.get_repo(os.environ["GITHUB_REPOSITORY"])

    for alert in alerts:
        title = f"[{alert['token']}] {alert['project']} - {alert['type']}"
        body_lines = [
            f"**Type:** {alert['type']}",
            f"**Priority:** {alert['priority']}",
            f"**Source:** {alert['source']}",
            "",
            f"**Notes**",
            alert["notes"],
        ]
        if alert.get("exchange"):
            body_lines.insert(3, f"**Exchange:** {alert['exchange']} ({alert.get('pair')})")

        if alert.get("wallet_name"):
            body_lines.insert(3, f"**Wallet:** {alert['wallet_name']} ({alert['wallet_address']})")

        body = "\n".join(body_lines)

        repo.create_issue(
            title=title,
            body=body,
            labels=alert.get("labels", ["airdrop"])
        )

if __name__ == "__main__":
    run()


之後你在 GitHub Project 裡設定規則：

任何新 Issue 標籤包含 airdrop / launchpool → 自動加入 Airdrop & Launchpool 看板

你就可以在看板上手動拖：To Review → Researching → Decide / Buy manually → Done

整個系統到這邊為止：

不下單

不轉帳

不簽名

只幫你「收集情報 → 分類 → 建卡片提醒你處理」。

七、(選用) Discord / Telegram 簡易通知

如果你想再加一層「即時提醒」，可以用 webhook：

# scripts/notify_discord.py
import json
import os
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

def run():
    if not WEBHOOK_URL:
        print("No DISCORD_WEBHOOK_URL set, skipping Discord notify.")
        return

    p = OUTPUT_DIR / "alerts.json"
    if not p.exists():
        return

    alerts = json.loads(p.read_text(encoding="utf-8"))
    if not alerts:
        return

    # 簡單版：只發最高優先級幾則
    top = [a for a in alerts if a["priority"] == "high"][:3]
    if not top:
        return

    content_lines = ["**Airdrop / Launchpool Alerts (High Priority)**"]
    for a in top:
        line = f"- {a['project']} | {a['type']} | {a['notes']}"
        content_lines.append(line)

    payload = {"content": "\n".join(content_lines)}
    requests.post(WEBHOOK_URL, json=payload, timeout=10)

if __name__ == "__main__":
    run()

八、總結一下你現在這個版本的定位

功能邊界正好停在你說的這三層：

資訊蒐集 / 監控（MON / BGB / 其他）

錢包資格預檢（read-only 链上資料）

任務管理 & 通知（Issue + Project + 選用 Webhook）

後續你要人工決策：

要不要去 Bitget / 其他 CEX/DEX 手動買

要不要手動參加 Launchpool / 鎖倉 / Claim

如果你接下來想要，我可以幫你把這套再拆成：

MVP 版本：只用 CMC + Etherscan + GitHub Issues，不接 Discord

進階版本：加入 Airdrops 站、Twitter 監控、更多鏈的瀏覽器 API（Arbiscan / Optimistic / Solscan 等）

你可以先開一個 repo，把你打算用的 tokens.yml / wallets.yml 草稿貼過來，我可以幫你對這份 config 做第一次優化。

你說：
專業空投追蹤網站​Airdrops.io：最大的空投資訊庫，列出進行中、已完成、未來的空投。​Airdrop Checklist：預測並追蹤有潛力的項目空投，已成功預測 Starknet、Dymension 等。​EarnDrop：通知你錢包何時符合空投資格，免費版可追蹤 8 個錢包。​Bankless Claimables：貼上你的公開錢包地址，自動檢測你是否有未領取的空投。​CoinMarketCap Airdrops：425+ 已驗證的空投，大多是任務型的。​AltcoinTrading / AirdropsAlert / ICOMarks：都有不同的篩選和分類方式。​
沒有被加入阿

ChatGPT 說：
已思考 20s

你說得對，上一版 pipeline 只有把 CMC / 鏈上 API 接進來，那些專業空投追蹤站還沒真的「接線」。下面我幫你把它們系統化地「加進去」，而且維持你要求的邊界：只做「情資＋提醒」，不做自動下單。

我會分成三層來處理：

哪些網站可以程式抓「列表」（適合自動化整合）

哪些是「錢包／帳號綁定工具」，適合做「快速入口產生器」，讓你點開手動查

具體怎麼改 config + fetch_sources.py 才算是真的「加進去」

一、把這些網站分類一下

你列的站點拆開來大致是：

1. 適合用爬蟲 / API 抓「空投列表」的

這些通常有「進行中 / 即將開始 / 已結束」清單，可以直接當作新的 event source：

Airdrops.io

優點：有 active / upcoming / ended 分類

Airdrop Checklist

偏「預測型」，列出有機會空投的項目與條件

CoinMarketCap Airdrops

有一個專門的 Airdrops 區域，標示任務、官方連結等

AltcoinTrading / AirdropsAlert / ICOMarks

各自有「Airdrop」或「Bounty / Campaign」欄位

這一組，我們會在 fetch_sources.py 裡加「對應的收集函式」，輸出成統一格式的 events。

2. 帳號 / 錢包綁定工具（不適合偷偷抓，只適合產生快捷入口）

EarnDrop（需要帳號登入＋綁錢包）

Bankless Claimables（需要你貼地址或連接錢包）

這些站點本身就是「UI 工具」，通常：

要 login / connect wallet

在瀏覽器完成簽名或授權

有可能有風控或防爬措施

這種我們不會去反向工程 API，而是：

在 pipeline 的 latest_report.md 裡，幫你生成：

EarnDrop 的錢包檢查網址（如果有 public 地址參數就用，沒有就放靜態 URL）

Bankless Claimables 檢查入口

你每天看到 report，直接點過去手動操作

這樣既算「被加入」，又不會踩服務條款或安全雷。

二、config：新增 sources.yml，正式把它們列進系統
config/sources.yml 範例
sources:
  airdrops_io:
    enabled: true
    mode: "list"           # list: 可程式抓列表
    urls:
      active: "https://airdrops.io/latest"   # 實作時你可以改成 /latest 或 /active
      upcoming: "https://airdrops.io/upcoming"
      ended: "https://airdrops.io/ended"

  airdrop_checklist:
    enabled: true
    mode: "list"
    urls:
      main: "https://airdropchecklist.com/"  # 實際 URL 請依你實測為準

  cmc_airdrops:
    enabled: true
    mode: "list"
    urls:
      main: "https://coinmarketcap.com/airdrop/"

  altcointrading_airdrops:
    enabled: false   # 等你有空再開
    mode: "list"
    urls:
      main: "https://www.altcointrading.net/airdrops/"

  airdropsalert:
    enabled: false
    mode: "list"
    urls:
      main: "https://airdropsalert.com/"

  icomarks_airdrops:
    enabled: false
    mode: "list"
    urls:
      main: "https://icomarks.com/airdrops"

  earndrop:
    enabled: true
    mode: "wallet_tool"    # 不爬，只產生入口
    urls:
      main: "https://earndrop.io/"   # 若未來有 wallet URL pattern 再補

  bankless_claimables:
    enabled: true
    mode: "wallet_tool"
    urls:
      main: "https://claimables.bankless.com"

三、資料模型：統一 event 格式

不管從哪個列表來，最後都轉成一個統一 dict，例如：

{
  "token": "MON",                         # 盡量填，真的抓不到就 None
  "project": "Monad",                    # 專案名稱
  "campaign_name": "Monad Community Airdrop",
  "source": "airdrops_io",               # 來源站名稱
  "status": "active",                    # active | upcoming | ended
  "type": "airdrop",                     # airdrop | launchpool | idrop | campaign
  "reward_type": "token",                # token | nft | points
  "est_value_usd": None,                 # 能抓到就抓，否則 None
  "deadline": None,                      # "2025-12-01" 之類，抓不到就 None
  "requirements": [
      "DeFi activity",
      "Hold specific NFT"
  ],
  "links": {
      "details": "https://airdrops.io/monad-airdrop",
      "official": "https://monad.xyz",
      "twitter": "https://twitter.com/monad_xyz"
  }
}


這樣你的 aggregate.py 就可以不管來源，只管：

status 是否 active / upcoming

token 是否在 tokens.yml watch list

requirements 是否匹配你可以做到的條件

四、改版 fetch_sources.py：真的把網站接進來

下面是骨架，CSS selector / DOM 結構要你自己視實際網頁調整，我這裡寫的是模式，不假裝知道精確 selector。

4.1 主入口：呼叫多個子收集器
# scripts/fetch_sources.py
import yaml
import json
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TOKENS = ROOT / "config" / "tokens.yml"
CONFIG_SOURCES = ROOT / "config" / "sources.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


def load_tokens():
    with open(CONFIG_TOKENS, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["tokens"]


def load_sources():
    with open(CONFIG_SOURCES, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]


# -------- Airdrops.io --------
def fetch_airdrops_io(src_cfg):
    if not src_cfg.get("enabled"):
        return []

    events = []
    urls = src_cfg["urls"]

    for status, url in urls.items():
        if status not in ("active", "upcoming", "ended"):
            continue

        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # TODO：下面這段要依實際 DOM 結構修改
        cards = soup.select(".airdrops-list .airdrop-item")
        for card in cards:
            title_el = card.select_one(".airdrop-title")
            proj_name = title_el.get_text(strip=True) if title_el else "Unknown"
            detail_url = title_el["href"] if title_el and title_el.has_attr("href") else url

            # 嘗試從標題或標籤推 token symbol（不一定有）
            token_symbol = None
            badge_el = card.select_one(".token-symbol")
            if badge_el:
                token_symbol = badge_el.get_text(strip=True)

            # 抓 reward / requirements 等文字簡單 parse 一下
            desc_el = card.select_one(".airdrop-desc")
            desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

            events.append({
                "token": token_symbol,
                "project": proj_name,
                "campaign_name": proj_name,
                "source": "airdrops_io",
                "status": status,    # active / upcoming / ended
                "type": "airdrop",
                "reward_type": "token",
                "est_value_usd": None,     # 可在細節頁再抓
                "deadline": None,          # 可視有無日期
                "requirements": [desc_text],   # 簡單先塞整段文字
                "links": {
                    "details": detail_url,
                },
            })

    return events


# -------- CoinMarketCap Airdrops --------
def fetch_cmc_airdrops(src_cfg):
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg["urls"]["main"]
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    # TODO：依照 CMC Airdrop 頁面的表格/卡片結構調整 selector
    rows = soup.select("table tbody tr") or soup.select(".cmc-table-row")
    for row in rows:
        proj_el = row.select_one(".cmc-link")
        proj_name = proj_el.get_text(strip=True) if proj_el else "Unknown"
        detail_url = proj_el["href"] if proj_el and proj_el.has_attr("href") else url

        status_el = row.select_one(".airdrop-status")
        status_text = status_el.get_text(strip=True).lower() if status_el else "unknown"
        if "upcoming" in status_text:
            status = "upcoming"
        elif "ended" in status_text or "closed" in status_text:
            status = "ended"
        else:
            status = "active"

        token_symbol = None
        token_el = row.select_one(".airdrop-token-symbol")
        if token_el:
            token_symbol = token_el.get_text(strip=True)

        events.append({
            "token": token_symbol,
            "project": proj_name,
            "campaign_name": proj_name,
            "source": "cmc_airdrops",
            "status": status,
            "type": "airdrop",
            "reward_type": "token",
            "est_value_usd": None,  # CMC 可能有顯示估值，可再抓
            "deadline": None,
            "requirements": [],
            "links": {
                "details": detail_url,
            },
        })

    return events


# -------- Airdrop Checklist --------
def fetch_airdrop_checklist(src_cfg):
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg["urls"]["main"]
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    # TODO：依照實際 DOM 結構調整
    cards = soup.select(".project-card")
    for card in cards:
        name_el = card.select_one(".project-title")
        proj_name = name_el.get_text(strip=True) if name_el else "Unknown"
        detail_url = name_el["href"] if name_el and name_el.has_attr("href") else url

        # Airdrop Checklist 通常是「預期可能空投」，status 我們標成 "potential"
        desc_el = card.select_one(".project-desc")
        desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

        events.append({
            "token": None,     # 很多是 L1 / L2 / dApp，未必有 token symbol
            "project": proj_name,
            "campaign_name": proj_name,
            "source": "airdrop_checklist",
            "status": "potential",   # 自訂
            "type": "airdrop",
            "reward_type": "unknown",
            "est_value_usd": None,
            "deadline": None,
            "requirements": [desc_text],
            "links": {
                "details": detail_url,
            },
        })

    return events


# -------- 其他列表類站點：AltcoinTrading / AirdropsAlert / ICOMarks --------
def fetch_generic_list_site(src_name, src_cfg, css_card, css_title):
    """給 AltcoinTrading / AirdropsAlert / ICOMarks 共用的簡單版 helper。"""
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg["urls"]["main"]
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    cards = soup.select(css_card)
    for card in cards:
        title_el = card.select_one(css_title)
        proj_name = title_el.get_text(strip=True) if title_el else "Unknown"
        detail_url = title_el["href"] if title_el and title_el.has_attr("href") else url

        desc_el = card.find("p")
        desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

        events.append({
            "token": None,
            "project": proj_name,
            "campaign_name": proj_name,
            "source": src_name,
            "status": "active",        # 很多站只列 active，細分可以再看
            "type": "airdrop",
            "reward_type": "token",
            "est_value_usd": None,
            "deadline": None,
            "requirements": [desc_text],
            "links": {
                "details": detail_url,
            },
        })

    return events


def run():
    sources = load_sources()
    all_events = []

    # Airdrops.io
    if "airdrops_io" in sources:
        all_events.extend(fetch_airdrops_io(sources["airdrops_io"]))

    # CoinMarketCap Airdrops
    if "cmc_airdrops" in sources:
        all_events.extend(fetch_cmc_airdrops(sources["cmc_airdrops"]))

    # Airdrop Checklist
    if "airdrop_checklist" in sources:
        all_events.extend(fetch_airdrop_checklist(sources["airdrop_checklist"]))

    # AltcoinTrading / AirdropsAlert / ICOMarks (先視需要開啟)
    if "altcointrading_airdrops" in sources:
        all_events.extend(
            fetch_generic_list_site(
                "altcointrading_airdrops",
                sources["altcointrading_airdrops"],
                css_card=".airdrop-item",    # TODO: 實際調整
                css_title="a"
            )
        )

    if "airdropsalert" in sources:
        all_events.extend(
            fetch_generic_list_site(
                "airdropsalert",
                sources["airdropsalert"],
                css_card=".airdrop-card",
                css_title="a"
            )
        )

    if "icomarks_airdrops" in sources:
        all_events.extend(
            fetch_generic_list_site(
                "icomarks_airdrops",
                sources["icomarks_airdrops"],
                css_card=".airdrop-item",
                css_title="a"
            )
        )

    # 寫出統一 events JSON
    with open(OUTPUT_DIR / "events_sources.json", "w", encoding="utf-8") as f:
        json.dump(all_events, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    run()


註：CSS selector 全部標成 TODO 風格，避免我亂猜 DOM。你實作時用瀏覽器 DevTools 看一下 class 名稱，再改掉就可以。

五、把 EarnDrop / Bankless Claimables「間接加入」

這兩個我們不抓資料，只幫你「把每個 wallet 的快捷檢查入口放在 report 裡」，讓你每天打開 latest_report.md 時可以快速點。

在 aggregate.py 裡加一段，讀 sources.yml：

# aggregate.py 的下半段（寫 report 的地方）

from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
CONFIG_SOURCES = ROOT / "config" / "sources.yml"

def load_sources_cfg():
    with open(CONFIG_SOURCES, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)["sources"]

def write_human_report(alerts, wallets):
    sources_cfg = load_sources_cfg()
    lines = ["# Airdrop / Launchpool Daily Report\n"]

    # 1) 高優先級 alerts
    if not alerts:
        lines.append("目前沒有高優先級 alert。\n")
    else:
        for a in alerts:
            lines.append(f"## [{a['priority'].upper()}] {a['project']} - {a['type']}")
            lines.append(f"- Token: {a['token']}")
            if a.get("exchange"):
                lines.append(f"- Exchange: {a['exchange']} ({a.get('pair')})")
            if a.get("wallet_name"):
                lines.append(f"- Wallet: {a['wallet_name']} ({a['wallet_address']})")
            lines.append(f"- Source: {a['source']}")
            lines.append(f"- Notes: {a['notes']}")
            lines.append("")

    # 2) EarnDrop / Bankless Claimables 快捷入口
    lines.append("## Wallet-based Tools\n")

    if sources_cfg.get("earndrop", {}).get("enabled"):
        lines.append("### EarnDrop")
        lines.append("請用以下地址在 EarnDrop 介面檢查空投資格：")
        for w in wallets:
            lines.append(f"- {w['name']}: {w['address']}")
        lines.append(f"入口：{sources_cfg['earndrop']['urls']['main']}\n")

    if sources_cfg.get("bankless_claimables", {}).get("enabled"):
        lines.append("### Bankless Claimables")
        lines.append("請用以下地址在 Bankless Claimables 介面檢查未領取空投：")
        for w in wallets:
            lines.append(f"- {w['name']}: {w['address']}")
        lines.append(f"入口：{sources_cfg['bankless_claimables']['urls']['main']}\n")

    (OUTPUT_DIR / "latest_report.md").write_text("\n".join(lines), encoding="utf-8")


這樣：

你每天看報告時，最上面是我們從各追蹤站抓到的「新空投 / 活動」

下方會列出：

EarnDrop：顯示你的錢包地址列表＋官方入口 URL

Bankless Claimables：同上

你只要：

點 link 開網站

貼上對應地址或 connect wallet

手動 claim / follow 步驟

這樣從系統角度來說，這些專業工具「已經被加入」你的 pipeline，只是我們刻意不自動打 API 或模擬操作，完全遵守「工具原本的交互模式」。

六、實作順序建議（避免一次改太多）

如果你要開始動手，我會建議順序：

先把 config/sources.yml 建好，只開：

airdrops_io

cmc_airdrops

airdrop_checklist

earndrop / bankless_claimables

實作 fetch_sources.py 最小版本：

Airdrops.io：先抓 active 頁面，能 parse 到「專案名稱 + 詳情網址」就算成功

CMC Airdrops：同上

Airdrop Checklist：先抓專案名稱 + 詳情網址

更新 aggregate.py：

把這些 events 丟進原本的 rule engine

把 EarnDrop / Bankless Claimables 的入口加進 latest_report.md

等整條 pipeline 能穩定跑幾次後，再考慮：

加 AltcoinTrading / AirdropsAlert / ICOMarks

強化 DOM selector、抓 reward / deadline / est_value

調整 rules：例如只有 status in ["active", "upcoming"] 且 token 在 watchlist 才打 high priority

如果你願意，可以把你實際用的 sources.yml 草稿貼上來，我可以幫你檢查欄位設計與「要先啟用哪幾個」的優先權。

你說：
給我project structure.md跟readme.md
ChatGPT 說：
已思考 13s

下面是兩個檔案的完整內容，你可以直接貼到 repo 內使用。

# project_structure.md

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

2. 目錄與檔案職責說明
2.1 config/ – 設定與策略

集中管理所有可調整設定，盡量避免把 magic number / hard-code 寫在程式內。

config/tokens.yml

定義追蹤的幣種與專案，例如 MON、BGB，以及未來關注的 L1 / L2 / DeFi 專案。

範例：

tokens:
  - symbol: MON
    coingecko_id: "monad"
    coinmarketcap_id: 12345
    watch:
      launchpool: true
      listings: true
      blog: true

  - symbol: BGB
    coinmarketcap_id: 5195
    watch:
      launchpool: true
      listings: false
      blog: false


用途：

scripts/fetch_sources.py 可利用 coingecko_id / coinmarketcap_id 查詢市場資訊。

scripts/aggregate.py 可利用 watch 標誌決定哪些 event 需要提高優先級。

config/wallets.yml

定義需要檢查的自有錢包（多鏈、多地址皆可）。

範例：

wallets:
  - name: main_eth
    chain: ethereum
    address: "0x1111..."

  - name: arb_farming
    chain: arbitrum
    address: "0x2222..."


用途：

scripts/check_wallets.py 會針對每個地址呼叫對應鏈的區塊瀏覽器 API（目前示範 Ethereum / Etherscan）。

output/wallets_report.json 會輸出這些地址的活動指標（例如交易次數）。

latest_report.md 會列出這些地址供使用者在 EarnDrop / Bankless Claimables 等網站手動查詢。

config/rules.yml

定義「什麼樣的情況需要提醒」的規則與優先級（Rule Engine）。

範例：

rules:
  - id: new_launchpool_for_watched_token
    type: listing
    priority: high
    match:
      category: "launchpool"
      token_in_watchlist: true

  - id: potential_retrospective_airdrop
    type: wallet_activity
    priority: medium
    match:
      has_defi_activity: true
      chain_in: ["ethereum", "arbitrum", "optimism", "solana"]
      tx_count_min: 20


用途：

scripts/aggregate.py 透過這些規則，將 events_sources.json 與 wallets_report.json 匹配，產生 alerts.json 與對應優先級。

將策略從程式碼抽離，方便日後調整判斷標準（例如提高 tx 門檻、改變關注鏈別…）。

config/sources.yml

定義外部資訊來源（空投追蹤站、列表站、錢包工具），並標記其類型。

範例：

sources:
  airdrops_io:
    enabled: true
    mode: "list"
    urls:
      active: "https://airdrops.io/latest"
      upcoming: "https://airdrops.io/upcoming"
      ended: "https://airdrops.io/ended"

  airdrop_checklist:
    enabled: true
    mode: "list"
    urls:
      main: "https://airdropchecklist.com/"

  cmc_airdrops:
    enabled: true
    mode: "list"
    urls:
      main: "https://coinmarketcap.com/airdrop/"

  altcointrading_airdrops:
    enabled: false
    mode: "list"
    urls:
      main: "https://www.altcointrading.net/airdrops/"

  airdropsalert:
    enabled: false
    mode: "list"
    urls:
      main: "https://airdropsalert.com/"

  icomarks_airdrops:
    enabled: false
    mode: "list"
    urls:
      main: "https://icomarks.com/airdrops"

  earndrop:
    enabled: true
    mode: "wallet_tool"
    urls:
      main: "https://earndrop.io/"

  bankless_claimables:
    enabled: true
    mode: "wallet_tool"
    urls:
      main: "https://claimables.bankless.com"


用途與設計：

mode = "list"：
表示此來源提供「可爬取的空投／活動列表」，由 fetch_sources.py 調用對應的收集函式。

mode = "wallet_tool"：
表示是與錢包互動的網站（EarnDrop / Bankless Claimables），不做爬蟲或自動操作，僅在 latest_report.md 中提供官方入口鏈結與需檢查的地址。

2.2 scripts/ – Pipeline 核心邏輯

這個資料夾放的是整條情資管線的 Python 腳本。它們透過 GitHub Actions 依序執行。

scripts/fetch_sources.py

職責：

讀取 config/sources.yml 與 config/tokens.yml。

根據啟用的來源，抓取空投 / 活動清單，例如：

Airdrops.io

CoinMarketCap Airdrops

Airdrop Checklist

以及未來的 AltcoinTrading / AirdropsAlert / ICOMarks …

將不同網站的資料轉成統一 event 格式，輸出為：

output/events_sources.json

scripts/check_wallets.py

職責：

讀取 config/wallets.yml。

呼叫對應鏈的公開 API（目前示範 Ethereum / Etherscan）：

取得交易次數等活動指標。

產生錢包活動報告：

output/wallets_report.json


未來可擴充：

多鏈支援（Arbitrum / Optimism / Solana 等），接對應區塊瀏覽器 API。

資料維度（例如 DeFi 合約互動、NFT 持有等）。

scripts/aggregate.py

職責：

讀取：

output/events_sources.json

output/wallets_report.json

config/rules.yml

config/sources.yml

根據規則引擎將 event 與錢包活動匹配，產生 alert：

判斷優先級（high / medium / low）

標記 alert 類型（新 Launchpool、新空投、潛在 retroactive 空投 profile …）

輸出：

output/alerts.json – 給機器讀取，後續用於建立 GitHub Issues / 通知

output/latest_report.md – 給人閱讀的每日報告

報告會包含：

高優先級的空投 / 活動清單

你的錢包活動摘要

EarnDrop / Bankless Claimables 等錢包工具入口與需檢查的地址列表

scripts/notify_github.py

職責：

讀取 output/alerts.json。

使用 GITHUB_TOKEN 連線至當前 repo。

根據每一條 alert 建立對應的 GitHub Issue：

title 範例：[MON] Monad - New listing / campaign

body 包含：

類型、優先級、來源

若為交易所活動：交易所名稱與交易對

若為錢包 profile：對應的錢包名稱與地址

notes：事件摘要

labels 預設為：airdrop、launchpool、wallet-profile 等

搭配 GitHub Projects 自動化規則，可將新 Issue 自動加入「Airdrop & Launchpool」看板，作為後續手動操作的任務卡片。

scripts/notify_discord.py（選用）

職責：

讀取 output/alerts.json。

從中挑出高優先級 alert（例如前 3 筆）。

若有設定 DISCORD_WEBHOOK_URL，則發送簡短摘要訊息到指定 Discord channel。

此模組為選用，未設定 webhook 也不影響主流程。

2.3 output/ – Pipeline 輸出

此目錄由程式自動產出與覆寫，不建議手動修改。

events_sources.json
從各空投追蹤站與列表站抓回的原始 event 集合（已做基本 normalize）。

wallets_report.json
各錢包在不同鏈上的活動指標（例如交易次數）。

alerts.json
經規則引擎篩選後的 alert，供 notify_github.py / notify_discord.py 使用。

latest_report.md
每次 pipeline 跑完對人類友好的摘要報告，包含：

高優先級事件清單

錢包活動摘要

EarnDrop / Bankless Claimables 等工具入口與需檢查的地址

2.4 .github/workflows/ – CI / 定時任務
.github/workflows/pipeline.yml

職責：

定義 Airdrop Intel Pipeline 的執行時機與步驟。

主要特性：

觸發條件：

schedule：例如每小時一次（cron: "0 * * * *"）

workflow_dispatch：可於 GitHub 網頁介面手動觸發

典型步驟：

checkout repo

安裝 Python 與依賴套件（對應 requirements.txt）

依序執行：

scripts/fetch_sources.py

scripts/check_wallets.py

scripts/aggregate.py

scripts/notify_github.py

scripts/notify_discord.py（若有 webhook）

透過 GitHub Secrets 注入敏感資訊，例如：

CMC_API_KEY

ETHERSCAN_API_KEY

DISCORD_WEBHOOK_URL

GITHUB_TOKEN（由 GitHub 自動提供，不需手動設定）

2.5 其他檔案
requirements.txt

列出 Python 依賴套件，例如：

requests
PyYAML
beautifulsoup4
PyGithub

README.md

專案說明與使用教學，包含功能簡介、安裝步驟、設定檔樣板與安全注意事項。

project_structure.md

即本文件，用於說明架構設計與各元件責任。

3. 資料流與控制流程

以下描述從資料來源 → 分析 → 通知的完整流程。

flowchart TD

    A[GitHub Actions<br/>pipeline.yml] --> B[fetch_sources.py<br/>抓取空投/活動列表]
    B -->|events_sources.json| C[aggregate.py]

    A --> D[check_wallets.py<br/>查詢錢包活動]
    D -->|wallets_report.json| C

    C -->|alerts.json<br/>latest_report.md| E[notify_github.py<br/>建立 Issues]
    C -->|alerts.json| F[notify_discord.py<br/>發送通知 (選用)]

    E --> G[GitHub Issues<br/>+ Projects 看板]
    F --> H[Discord Channel]



功能邊界：

本專案只做：

資訊蒐集 / 監控

錢包資格預檢（read-only API）

任務管理 & 通知（Issues / 看板 / Discord）

不做：

自動下單 / 買幣

自動質押 / Launchpool 參與

自動簽名 / 授權 / 轉帳

所有實際操作均由使用者在交易所或錢包介面手動完成。

4. 後續擴充方向（簡要）

新增更多「列表來源」：

例如專門追蹤 L2 / NFT / DeFi 的空投站

新增更多「鏈」與 API：

Arbitrum / Optimism / Base / Solana / Sui 等

增加規則：

針對特定專案自訂條件（如 MON 第二輪空投、特定 DeFi 互動…）

加上快照紀錄：

保存歷史 alerts，做長期策略回顧（哪些提醒實際有收益）

本結構刻意模組化，讓你可以針對來源、規則、通知方式各自演進，而不影響整體流水線。


---

```markdown
# README.md

# Airdrop Intel Pipeline

Airdrop Intel Pipeline 是一個以 GitHub Actions 為核心的「空投 / Launchpool 情報管線」，協助使用者：

1. 監控多個空投追蹤網站與列表來源  
2. 透過鏈上 API 檢查自有錢包的活動 profile  
3. 將「值得關注的機會」自動整理為 GitHub Issues / Projects 看板任務  
4. 選用：發送簡短通知至 Discord  

> 本專案的功能邊界刻意限制在：**資訊蒐集、資格預檢、任務管理與通知**。  
> 不會自動買幣、不會自動簽名、不會自動轉帳，所有實際操作都由使用者手動完成。

---

## Features 功能摘要

- 多來源空投 / 活動蒐集：
  - Airdrops.io
  - CoinMarketCap Airdrops
  - Airdrop Checklist
  - 以及可選的 AltcoinTrading / AirdropsAlert / ICOMarks 等
- 錢包資格預檢：
  - 透過鏈上 API（示範 Ethereum / Etherscan），分析自有地址交易活動
  - 為「潛在 retroactive 空投 profile」提供基本指標
- 規則引擎（Rules Engine）：
  - 用 `config/rules.yml` 定義「什麼情況需要提醒」、「優先級」
- 任務管理整合：
  - 將 alert 自動轉成 GitHub Issues
  - 透過 GitHub Projects 看板管理「To Review / Researching / Decide / Done」
- 報告與通知：
  - 產生人類可讀的 `latest_report.md`
  - 選擇性地透過 Discord Webhook 發送高優先級 alert 摘要
- EarnDrop / Bankless Claimables 整合：
  - 在報告中提供官方入口與需檢查地址列表，方便使用者登入這些工具做更精細的錢包稽核

---

## Architecture 架構概覽

目錄結構（簡略版）：

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
├─ .github/workflows/
│  └─ pipeline.yml
├─ requirements.txt
├─ README.md
└─ project_structure.md


資料流：

fetch_sources.py
從各空投網站（Airdrops.io、CMC Airdrops、Airdrop Checklist…）抓活動列表 → events_sources.json。

check_wallets.py
透過鏈上 API 查詢錢包活動 → wallets_report.json。

aggregate.py
根據 rules.yml 將 1 & 2 匹配，產出 alerts.json + latest_report.md。

notify_github.py
將 alerts.json 轉為 GitHub Issues（可搭配 Project 看板）。

notify_discord.py（選用）
透過 Webhook 把高優先級 alert 發送到 Discord。

Getting Started 快速開始
1. 前置需求

GitHub 帳號與一個空 repo（或 fork 本專案）

Python 3.10+（本地開發）

GitHub Actions 已啟用（預設開啟）

2. Clone 專案
git clone <your-repo-url> airdrop-intel-pipeline
cd airdrop-intel-pipeline

3. 安裝依賴（本地測試）
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

4. 設定 config/ 檔案
4.1 config/tokens.yml

定義你想追蹤的幣種與專案：

tokens:
  - symbol: MON
    coingecko_id: "monad"
    coinmarketcap_id: 12345
    watch:
      launchpool: true
      listings: true
      blog: true

  - symbol: BGB
    coinmarketcap_id: 5195
    watch:
      launchpool: true
      listings: false
      blog: false

4.2 config/wallets.yml

列出你要檢查的地址（可多鏈）：

wallets:
  - name: main_eth
    chain: ethereum
    address: "0x1111..."

  - name: arb_farming
    chain: arbitrum
    address: "0x2222..."

4.3 config/rules.yml

定義提醒條件與優先級：

rules:
  - id: new_launchpool_for_watched_token
    type: listing
    priority: high
    match:
      category: "launchpool"
      token_in_watchlist: true

  - id: potential_retrospective_airdrop
    type: wallet_activity
    priority: medium
    match:
      has_defi_activity: true
      chain_in: ["ethereum", "arbitrum", "optimism", "solana"]
      tx_count_min: 20

4.4 config/sources.yml

設定要啟用的空投追蹤網站與工具：

sources:
  airdrops_io:
    enabled: true
    mode: "list"
    urls:
      active: "https://airdrops.io/latest"
      upcoming: "https://airdrops.io/upcoming"
      ended: "https://airdrops.io/ended"

  airdrop_checklist:
    enabled: true
    mode: "list"
    urls:
      main: "https://airdropchecklist.com/"

  cmc_airdrops:
    enabled: true
    mode: "list"
    urls:
      main: "https://coinmarketcap.com/airdrop/"

  altcointrading_airdrops:
    enabled: false
    mode: "list"
    urls:
      main: "https://www.altcointrading.net/airdrops/"

  airdropsalert:
    enabled: false
    mode: "list"
    urls:
      main: "https://airdropsalert.com/"

  icomarks_airdrops:
    enabled: false
    mode: "list"
    urls:
      main: "https://icomarks.com/airdrops"

  earndrop:
    enabled: true
    mode: "wallet_tool"
    urls:
      main: "https://earndrop.io/"

  bankless_claimables:
    enabled: true
    mode: "wallet_tool"
    urls:
      main: "https://claimables.bankless.com"

5. 設定 GitHub Secrets

在 GitHub repo 頁面：

Settings → Secrets and variables → Actions → New repository secret

可以視需要設定以下變數：

CMC_API_KEY
用於 CoinMarketCap Pro API（若你要從 API 抓上市資訊）。

ETHERSCAN_API_KEY
用於 Ethereum 鏈上查詢（交易次數等）。

DISCORD_WEBHOOK_URL（選用）
若你要啟用 Discord 通知。

GITHUB_TOKEN
由 GitHub Actions 自動提供，一般不需自行設定，程式端可直接使用。

6. 啟用 pipeline

檢查 .github/workflows/pipeline.yml 是否存在，內容類似：

name: Airdrop Intel Pipeline

on:
  schedule:
    - cron: "0 * * * *"
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pipeline
        env:
          CMC_API_KEY: ${{ secrets.CMC_API_KEY }}
          ETHERSCAN_API_KEY: ${{ secrets.ETHERSCAN_API_KEY }}
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        run: |
          python scripts/fetch_sources.py
          python scripts/check_wallets.py
          python scripts/aggregate.py
          python scripts/notify_github.py
          python scripts/notify_discord.py


推送修改到 GitHub 後：

你可以在 Actions 分頁看到 pipeline 依照排程自動執行。

也可以點選 workflow，按下「Run workflow」手動執行。

Usage 使用方式

每輪執行後，檢查 output/latest_report.md：

看有哪些新的空投 / 活動被標示為 high / medium priority。

看自己的錢包 activity 摘要。

使用報告中的 EarnDrop / Bankless Claimables 入口與地址列表，手動在官方網站上進一步檢查。

到 GitHub Issues / Projects 看板：

查看 pipeline 自動建立的 Issues。

以看板方式管理：

To Review：剛建立的 alert

Researching：已開始查官方資訊

Decide：等待做出操作決策（是否參與、是否買幣）

Done / Missed：已處理或錯過

所有實際操作（買幣、鎖倉、簽名、Claim）均在交易所 / 錢包介面手動完成，本專案不參與資金操作。

Security & Limitations 安全與限制

本專案只呼叫公開 API（例如 Etherscan、空投列表網站），不會要求你的私鑰。

任何錢包相關進一步操作（EarnDrop / Bankless Claimables 等）都由你在瀏覽器中登入並簽名，本專案只提供入口與地址列表。

不建議將交易所 API Key 或錢包私鑰存放於此 repo 或 GitHub Secrets。

若你要整合更多來源，請注意各網站的服務條款、robots.txt 與 Rate Limit。

Roadmap 後續可能方向

支援更多鏈與區塊瀏覽器 API（Arbitrum / Optimism / Base / Solana …）。

為特定專案（例如 MON）新增專屬規則（第二輪空投、特定互動條件等）。

增加歷史資料持久化，用來回顧哪些 alert 轉化成實際收益。

加入簡單的 scoring / ranking 模型，將「預期價值」也考慮進優先排序。

如需了解更細節的架構與每個檔案的責任，請參考同 repo 內的 project_structure.md。
