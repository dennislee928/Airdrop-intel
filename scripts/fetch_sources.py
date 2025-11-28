"""
空投情報收集器
從多個空投追蹤網站收集空投活動資訊
"""
import yaml
import json
import os
import logging
import time
from pathlib import Path
from typing import List, Dict, Optional

import requests
from bs4 import BeautifulSoup

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_TOKENS = ROOT / "config" / "tokens.yml"
CONFIG_SOURCES = ROOT / "config" / "sources.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# 重試設定
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


def load_tokens() -> List[Dict]:
    """載入追蹤的幣種配置"""
    try:
        with open(CONFIG_TOKENS, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("tokens", [])
    except Exception as e:
        logger.error(f"載入 tokens.yml 失敗: {e}")
        return []


def load_sources() -> Dict:
    """載入來源配置"""
    try:
        with open(CONFIG_SOURCES, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("sources", {})
    except Exception as e:
        logger.error(f"載入 sources.yml 失敗: {e}")
        return {}


def fetch_with_retry(url: str, timeout: int = 20, headers: Optional[Dict] = None) -> Optional[requests.Response]:
    """帶重試機制的 HTTP GET 請求"""
    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=timeout, headers=headers or {})
            resp.raise_for_status()
            return resp
        except requests.exceptions.RequestException as e:
            logger.warning(f"請求失敗 (嘗試 {attempt + 1}/{MAX_RETRIES}): {url} - {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"請求最終失敗: {url}")
                return None
    return None


def fetch_airdrops_io(src_cfg: Dict) -> List[Dict]:
    """抓取 Airdrops.io 的空投列表"""
    if not src_cfg.get("enabled"):
        return []

    events = []
    urls = src_cfg.get("urls", {})

    for status, url in urls.items():
        if status not in ("active", "upcoming", "ended"):
            continue

        logger.info(f"抓取 Airdrops.io - {status}: {url}")
        resp = fetch_with_retry(url)
        if not resp:
            continue

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            # TODO: 根據實際 DOM 結構調整 CSS selector
            cards = soup.select(".airdrops-list .airdrop-item") or soup.select(".airdrop-item")
            
            for card in cards:
                try:
                    title_el = card.select_one(".airdrop-title") or card.select_one("h2") or card.select_one("h3")
                    proj_name = title_el.get_text(strip=True) if title_el else "Unknown"
                    
                    detail_url = url
                    if title_el and title_el.has_attr("href"):
                        detail_url = title_el["href"]
                        if not detail_url.startswith("http"):
                            detail_url = f"https://airdrops.io{detail_url}"

                    # 嘗試從標題或標籤推 token symbol
                    token_symbol = None
                    badge_el = card.select_one(".token-symbol") or card.select_one(".symbol")
                    if badge_el:
                        token_symbol = badge_el.get_text(strip=True)

                    # 抓描述文字
                    desc_el = card.select_one(".airdrop-desc") or card.select_one("p")
                    desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

                    events.append({
                        "token": token_symbol,
                        "project": proj_name,
                        "campaign_name": proj_name,
                        "source": "airdrops_io",
                        "status": status,
                        "type": "airdrop",
                        "reward_type": "token",
                        "est_value_usd": None,
                        "deadline": None,
                        "requirements": [desc_text] if desc_text else [],
                        "links": {
                            "details": detail_url,
                        },
                    })
                except Exception as e:
                    logger.warning(f"解析 Airdrops.io 卡片失敗: {e}")
                    continue

        except Exception as e:
            logger.error(f"解析 Airdrops.io HTML 失敗 ({status}): {e}")
            continue

    logger.info(f"Airdrops.io 收集到 {len(events)} 個事件")
    return events


def fetch_cmc_airdrops(src_cfg: Dict) -> List[Dict]:
    """抓取 CoinMarketCap Airdrops"""
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        return []

    logger.info(f"抓取 CoinMarketCap Airdrops: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        # TODO: 根據實際 CMC 頁面結構調整 selector
        rows = soup.select("table tbody tr") or soup.select(".cmc-table-row") or soup.select(".airdrop-row")
        
        for row in rows:
            try:
                proj_el = row.select_one(".cmc-link") or row.select_one("a")
                proj_name = proj_el.get_text(strip=True) if proj_el else "Unknown"
                
                detail_url = url
                if proj_el and proj_el.has_attr("href"):
                    detail_url = proj_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"https://coinmarketcap.com{detail_url}"

                status_el = row.select_one(".airdrop-status") or row.select_one(".status")
                status_text = status_el.get_text(strip=True).lower() if status_el else "unknown"
                
                if "upcoming" in status_text:
                    status = "upcoming"
                elif "ended" in status_text or "closed" in status_text:
                    status = "ended"
                else:
                    status = "active"

                token_symbol = None
                token_el = row.select_one(".airdrop-token-symbol") or row.select_one(".symbol")
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
                    "est_value_usd": None,
                    "deadline": None,
                    "requirements": [],
                    "links": {
                        "details": detail_url,
                    },
                })
            except Exception as e:
                logger.warning(f"解析 CMC Airdrops 行失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 CoinMarketCap Airdrops HTML 失敗: {e}")

    logger.info(f"CoinMarketCap Airdrops 收集到 {len(events)} 個事件")
    return events


def fetch_airdrop_checklist(src_cfg: Dict) -> List[Dict]:
    """抓取 Airdrop Checklist"""
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        return []

    logger.info(f"抓取 Airdrop Checklist: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        # TODO: 根據實際 DOM 結構調整
        cards = soup.select(".project-card") or soup.select(".card") or soup.select(".airdrop-card")
        
        for card in cards:
            try:
                name_el = card.select_one(".project-title") or card.select_one("h2") or card.select_one("h3")
                proj_name = name_el.get_text(strip=True) if name_el else "Unknown"
                
                detail_url = url
                if name_el and name_el.has_attr("href"):
                    detail_url = name_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"{url.rstrip('/')}{detail_url}"

                desc_el = card.select_one(".project-desc") or card.select_one("p")
                desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

                events.append({
                    "token": None,
                    "project": proj_name,
                    "campaign_name": proj_name,
                    "source": "airdrop_checklist",
                    "status": "potential",
                    "type": "airdrop",
                    "reward_type": "unknown",
                    "est_value_usd": None,
                    "deadline": None,
                    "requirements": [desc_text] if desc_text else [],
                    "links": {
                        "details": detail_url,
                    },
                })
            except Exception as e:
                logger.warning(f"解析 Airdrop Checklist 卡片失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 Airdrop Checklist HTML 失敗: {e}")

    logger.info(f"Airdrop Checklist 收集到 {len(events)} 個事件")
    return events


def fetch_generic_list_site(src_name: str, src_cfg: Dict, css_card: str, css_title: str) -> List[Dict]:
    """通用函式處理 AltcoinTrading / AirdropsAlert / ICOMarks"""
    if not src_cfg.get("enabled"):
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        return []

    logger.info(f"抓取 {src_name}: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select(css_card)
        
        for card in cards:
            try:
                title_el = card.select_one(css_title)
                proj_name = title_el.get_text(strip=True) if title_el else "Unknown"
                
                detail_url = url
                if title_el and title_el.has_attr("href"):
                    detail_url = title_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"{url.rstrip('/')}{detail_url}"

                desc_el = card.find("p")
                desc_text = desc_el.get_text(" ", strip=True) if desc_el else ""

                events.append({
                    "token": None,
                    "project": proj_name,
                    "campaign_name": proj_name,
                    "source": src_name,
                    "status": "active",
                    "type": "airdrop",
                    "reward_type": "token",
                    "est_value_usd": None,
                    "deadline": None,
                    "requirements": [desc_text] if desc_text else [],
                    "links": {
                        "details": detail_url,
                    },
                })
            except Exception as e:
                logger.warning(f"解析 {src_name} 卡片失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 {src_name} HTML 失敗: {e}")

    logger.info(f"{src_name} 收集到 {len(events)} 個事件")
    return events


def run():
    """主執行函式"""
    logger.info("開始收集空投情報...")
    sources = load_sources()
    all_events = []

    # Airdrops.io
    if "airdrops_io" in sources:
        try:
            all_events.extend(fetch_airdrops_io(sources["airdrops_io"]))
        except Exception as e:
            logger.error(f"抓取 Airdrops.io 失敗: {e}")

    # CoinMarketCap Airdrops
    if "cmc_airdrops" in sources:
        try:
            all_events.extend(fetch_cmc_airdrops(sources["cmc_airdrops"]))
        except Exception as e:
            logger.error(f"抓取 CoinMarketCap Airdrops 失敗: {e}")

    # Airdrop Checklist
    if "airdrop_checklist" in sources:
        try:
            all_events.extend(fetch_airdrop_checklist(sources["airdrop_checklist"]))
        except Exception as e:
            logger.error(f"抓取 Airdrop Checklist 失敗: {e}")

    # AltcoinTrading / AirdropsAlert / ICOMarks
    generic_sources = {
        "altcointrading_airdrops": (".airdrop-item", "a"),
        "airdropsalert": (".airdrop-card", "a"),
        "icomarks_airdrops": (".airdrop-item", "a"),
    }

    for src_name, (css_card, css_title) in generic_sources.items():
        if src_name in sources:
            try:
                all_events.extend(
                    fetch_generic_list_site(
                        src_name,
                        sources[src_name],
                        css_card,
                        css_title
                    )
                )
            except Exception as e:
                logger.error(f"抓取 {src_name} 失敗: {e}")

    # 寫出統一 events JSON
    output_file = OUTPUT_DIR / "events_sources.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(all_events, f, ensure_ascii=False, indent=2)
        logger.info(f"成功寫入 {len(all_events)} 個事件到 {output_file}")
    except Exception as e:
        logger.error(f"寫入 events_sources.json 失敗: {e}")


if __name__ == "__main__":
    run()

