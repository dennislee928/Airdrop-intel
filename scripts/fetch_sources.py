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
        logger.info("Airdrops.io 已停用，跳過")
        return []

    events = []
    urls = src_cfg.get("urls", {})

    for status, url in urls.items():
        if status not in ("active", "upcoming", "ended"):
            continue

        logger.info(f"抓取 Airdrops.io - {status}: {url}")
        resp = fetch_with_retry(url)
        if not resp:
            logger.warning(f"Airdrops.io ({status}) 請求失敗，跳過")
            continue

        try:
            soup = BeautifulSoup(resp.text, "html.parser")
            # 嘗試多種可能的 CSS selector
            cards = (
                soup.select(".airdrops-list .airdrop-item") or
                soup.select(".airdrop-item") or
                soup.select("article") or
                soup.select(".card") or
                soup.select("[class*='airdrop']")
            )

            logger.info(f"Airdrops.io ({status}) 找到 {len(cards)} 個可能的項目")

            for card in cards:
                try:
                    # 嘗試多種方式找標題
                    title_el = (
                        card.select_one(".airdrop-title") or
                        card.select_one("h2") or
                        card.select_one("h3") or
                        card.select_one("h4") or
                        card.select_one("a[href*='airdrop']") or
                        card.select_one("a")
                    )
                    proj_name = title_el.get_text(strip=True) if title_el else "Unknown"

                    if proj_name == "Unknown":
                        # 如果還是找不到，跳過這個項目
                        continue

                    detail_url = url
                    if title_el and title_el.has_attr("href"):
                        detail_url = title_el["href"]
                        if not detail_url.startswith("http"):
                            detail_url = f"https://airdrops.io{detail_url}"

                    # 嘗試從標題或標籤推 token symbol
                    token_symbol = None
                    badge_el = (
                        card.select_one(".token-symbol") or
                        card.select_one(".symbol") or
                        card.select_one("[class*='token']")
                    )
                    if badge_el:
                        token_symbol = badge_el.get_text(strip=True)

                    # 抓描述文字
                    desc_el = (
                        card.select_one(".airdrop-desc") or
                        card.select_one("p") or
                        card.select_one(".description")
                    )
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
                    logger.debug(f"解析 Airdrops.io 卡片失敗: {e}")
                    continue

        except Exception as e:
            logger.error(f"解析 Airdrops.io HTML 失敗 ({status}): {e}")
            continue

    logger.info(f"Airdrops.io 總共收集到 {len(events)} 個事件")
    return events


def fetch_cmc_airdrops(src_cfg: Dict) -> List[Dict]:
    """抓取 CoinMarketCap Airdrops"""
    if not src_cfg.get("enabled"):
        logger.info("CoinMarketCap Airdrops 已停用，跳過")
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        logger.warning("CoinMarketCap Airdrops URL 未設定")
        return []

    logger.info(f"抓取 CoinMarketCap Airdrops: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        logger.warning("CoinMarketCap Airdrops 請求失敗")
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        # 嘗試多種可能的 CSS selector
        rows = (
            soup.select("table tbody tr") or
            soup.select(".cmc-table-row") or
            soup.select(".airdrop-row") or
            soup.select("tr[data-symbol]") or
            soup.select("article") or
            soup.select("[class*='airdrop']")
        )

        logger.info(f"CoinMarketCap Airdrops 找到 {len(rows)} 個可能的項目")

        for row in rows:
            try:
                # 嘗試多種方式找專案名稱
                proj_el = (
                    row.select_one(".cmc-link") or
                    row.select_one("a[href*='airdrop']") or
                    row.select_one("a[href*='cryptocurrency']") or
                    row.select_one("a") or
                    row.select_one("h2") or
                    row.select_one("h3")
                )
                proj_name = proj_el.get_text(strip=True) if proj_el else "Unknown"

                if proj_name == "Unknown":
                    continue

                detail_url = url
                if proj_el and proj_el.has_attr("href"):
                    detail_url = proj_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"https://coinmarketcap.com{detail_url}"

                status_el = (
                    row.select_one(".airdrop-status") or
                    row.select_one(".status") or
                    row.select_one("[class*='status']")
                )
                status_text = status_el.get_text(strip=True).lower() if status_el else "unknown"
                
                if "upcoming" in status_text:
                    status = "upcoming"
                elif "ended" in status_text or "closed" in status_text:
                    status = "ended"
                else:
                    status = "active"

                token_symbol = None
                token_el = (
                    row.select_one(".airdrop-token-symbol") or
                    row.select_one(".symbol") or
                    row.select_one("[data-symbol]")
                )
                if token_el:
                    token_symbol = token_el.get_text(strip=True) or token_el.get("data-symbol")

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
                logger.debug(f"解析 CMC Airdrops 行失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 CoinMarketCap Airdrops HTML 失敗: {e}")

    logger.info(f"CoinMarketCap Airdrops 總共收集到 {len(events)} 個事件")
    return events


def fetch_airdrop_checklist(src_cfg: Dict) -> List[Dict]:
    """抓取 Airdrop Checklist"""
    if not src_cfg.get("enabled"):
        logger.info("Airdrop Checklist 已停用，跳過")
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        logger.warning("Airdrop Checklist URL 未設定")
        return []

    logger.info(f"抓取 Airdrop Checklist: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        logger.warning("Airdrop Checklist 請求失敗")
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        # 嘗試多種可能的 CSS selector
        cards = (
            soup.select(".project-card") or
            soup.select(".card") or
            soup.select(".airdrop-card") or
            soup.select("article") or
            soup.select("[class*='project']") or
            soup.select("[class*='airdrop']")
        )

        logger.info(f"Airdrop Checklist 找到 {len(cards)} 個可能的項目")

        for card in cards:
            try:
                # 嘗試多種方式找標題
                name_el = (
                    card.select_one(".project-title") or
                    card.select_one("h2") or
                    card.select_one("h3") or
                    card.select_one("h4") or
                    card.select_one("a[href]") or
                    card.select_one("a")
                )
                proj_name = name_el.get_text(strip=True) if name_el else "Unknown"

                if proj_name == "Unknown":
                    continue

                detail_url = url
                if name_el and name_el.has_attr("href"):
                    detail_url = name_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"{url.rstrip('/')}{detail_url}"

                desc_el = (
                    card.select_one(".project-desc") or
                    card.select_one("p") or
                    card.select_one(".description")
                )
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
                logger.debug(f"解析 Airdrop Checklist 卡片失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 Airdrop Checklist HTML 失敗: {e}")

    logger.info(f"Airdrop Checklist 總共收集到 {len(events)} 個事件")
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
    logger.info("=" * 60)
    logger.info("開始收集空投情報...")
    logger.info("=" * 60)

    sources = load_sources()
    all_events = []
    source_stats = {}

    # Airdrops.io
    if "airdrops_io" in sources:
        try:
            events = fetch_airdrops_io(sources["airdrops_io"])
            all_events.extend(events)
            source_stats["airdrops_io"] = len(events)
        except Exception as e:
            logger.error(f"抓取 Airdrops.io 失敗: {e}")
            source_stats["airdrops_io"] = 0

    # CoinMarketCap Airdrops
    if "cmc_airdrops" in sources:
        try:
            events = fetch_cmc_airdrops(sources["cmc_airdrops"])
            all_events.extend(events)
            source_stats["cmc_airdrops"] = len(events)
        except Exception as e:
            logger.error(f"抓取 CoinMarketCap Airdrops 失敗: {e}")
            source_stats["cmc_airdrops"] = 0

    # Airdrop Checklist
    if "airdrop_checklist" in sources:
        try:
            events = fetch_airdrop_checklist(sources["airdrop_checklist"])
            all_events.extend(events)
            source_stats["airdrop_checklist"] = len(events)
        except Exception as e:
            logger.error(f"抓取 Airdrop Checklist 失敗: {e}")
            source_stats["airdrop_checklist"] = 0

    # AltcoinTrading / AirdropsAlert / ICOMarks
    generic_sources = {
        "altcointrading_airdrops": (".airdrop-item", "a"),
        "airdropsalert": (".airdrop-card", "a"),
        "icomarks_airdrops": (".airdrop-item", "a"),
    }

    for src_name, (css_card, css_title) in generic_sources.items():
        if src_name in sources:
            try:
                events = fetch_generic_list_site(
                    src_name,
                    sources[src_name],
                    css_card,
                    css_title
                )
                all_events.extend(events)
                source_stats[src_name] = len(events)
            except Exception as e:
                logger.error(f"抓取 {src_name} 失敗: {e}")
                source_stats[src_name] = 0

    # 輸出統計資訊
    logger.info("=" * 60)
    logger.info("收集統計:")
    for src_name, count in source_stats.items():
        logger.info(f"  {src_name}: {count} 個事件")
    logger.info(f"總計: {len(all_events)} 個事件")
    logger.info("=" * 60)

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

