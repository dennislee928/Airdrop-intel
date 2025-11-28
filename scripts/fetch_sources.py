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
# 請求間隔（避免被 rate limit）
REQUEST_DELAY = 1  # 秒，在請求之間等待


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
    # 預設 headers，模擬瀏覽器請求以避免被阻擋
    default_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    # 合併 headers
    final_headers = {**default_headers, **(headers or {})}

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, timeout=timeout, headers=final_headers)
            # 對於 404，直接返回 None，不需要重試
            if resp.status_code == 404:
                logger.warning(f"URL 不存在 (404): {url}")
                return None
            resp.raise_for_status()
            return resp
        except requests.exceptions.HTTPError as e:
            # 404 不需要重試
            if e.response and e.response.status_code == 404:
                logger.warning(f"URL 不存在 (404): {url}")
                return None
            logger.warning(f"HTTP 錯誤 (嘗試 {attempt + 1}/{MAX_RETRIES}): {url} - {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"請求最終失敗: {url}")
                return None
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
        # 在請求之間增加延遲，避免被 rate limit
        if events:  # 不是第一個請求
            time.sleep(REQUEST_DELAY)
        resp = fetch_with_retry(url)
        if not resp:
            logger.warning(f"Airdrops.io ({status}) 請求失敗，跳過")
            continue

        # 檢查是否是 404，如果是則跳過（URL 可能不存在）
        if hasattr(resp, 'status_code') and resp.status_code == 404:
            logger.warning(f"Airdrops.io ({status}) URL 不存在 (404)，跳過")
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
    """
    通用函式處理 AltcoinTrading / AirdropsAlert / ICOMarks

    Args:
        css_card: CSS selector 字串，可以是多個選擇器用逗號分隔
        css_title: CSS selector 字串，可以是多個選擇器用逗號分隔
    """
    if not src_cfg.get("enabled"):
        logger.info(f"{src_name} 已停用，跳過")
        return []

    url = src_cfg.get("urls", {}).get("main")
    if not url:
        logger.warning(f"{src_name} URL 未設定")
        return []

    logger.info(f"抓取 {src_name}: {url}")
    resp = fetch_with_retry(url)
    if not resp:
        logger.warning(f"{src_name} 請求失敗")
        return []

    events = []
    try:
        soup = BeautifulSoup(resp.text, "html.parser")

        # 如果 css_card 包含多個選擇器（用逗號分隔），分別嘗試
        card_selectors = [s.strip() for s in css_card.split(",")] if "," in css_card else [css_card]

        cards = []
        for selector in card_selectors:
            found = soup.select(selector)
            if found:
                cards.extend(found)
                logger.debug(f"{src_name} 使用 selector '{selector}' 找到 {len(found)} 個項目")
                break

        # 如果還是沒找到，嘗試通用選擇器
        if not cards:
            fallback_selectors = ["article", ".card", "[class*='airdrop']", "[class*='item']", "tr", "li", ".post", ".entry"]
            for selector in fallback_selectors:
                found = soup.select(selector)
                if found and len(found) > 0:
                    cards = found
                    logger.info(f"{src_name} 使用 fallback selector '{selector}' 找到 {len(found)} 個項目")
                    break

        logger.info(f"{src_name} 找到 {len(cards)} 個可能的項目")

        if len(cards) == 0:
            logger.warning(f"{src_name} 未找到任何項目，可能需要調整 CSS selector")
            # 嘗試找出可能的選擇器
            soup_debug = BeautifulSoup(resp.text, "html.parser")
            # 檢查常見的容器元素
            possible_containers = soup_debug.select("article, .card, .item, .post, .entry, [class*='airdrop'], [class*='list'], div[class], section[class]")
            if possible_containers:
                logger.info(f"{src_name} 找到 {len(possible_containers)} 個可能的容器元素，但 selector 不匹配")
                # 輸出前幾個容器的 class 供參考
                classes_found = []
                for container in possible_containers[:5]:
                    if container.get("class"):
                        classes_found.append(".".join(container.get("class", [])))
                if classes_found:
                    logger.info(f"{src_name} 發現的 class 範例: {', '.join(set(classes_found)[:5])}")
            else:
                logger.warning(f"{src_name} 頁面結構可能使用 JavaScript 動態載入，或結構完全不同")
                # 檢查是否有 script 標籤（可能使用 JS 載入）
                scripts = soup_debug.find_all("script")
                if len(scripts) > 5:
                    logger.info(f"{src_name} 頁面包含 {len(scripts)} 個 script 標籤，可能使用 JavaScript 動態載入內容")

        # 處理 css_title，可能是多個選擇器
        title_selectors = [s.strip() for s in css_title.split(",")] if "," in css_title else [css_title]

        for card in cards:
            try:
                # 嘗試多種方式找標題
                title_el = None
                for selector in title_selectors:
                    title_el = card.select_one(selector)
                    if title_el:
                        break

                # 如果還是沒找到，嘗試通用選擇器
                if not title_el:
                    title_el = (
                        card.select_one("a") or
                        card.select_one("h2") or
                        card.select_one("h3") or
                        card.select_one("h4") or
                        card.select_one(".title") or
                        card.select_one("[class*='title']") or
                        card.select_one("strong") or
                        card.select_one("b")
                    )
                proj_name = title_el.get_text(strip=True) if title_el else "Unknown"

                if proj_name == "Unknown" or not proj_name or len(proj_name) < 2:
                    # 跳過無效的項目
                    continue

                detail_url = url
                if title_el and title_el.has_attr("href"):
                    detail_url = title_el["href"]
                    if not detail_url.startswith("http"):
                        detail_url = f"{url.rstrip('/')}{detail_url}"

                desc_el = (
                    card.find("p") or
                    card.select_one(".description") or
                    card.select_one("[class*='desc']")
                )
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
                logger.debug(f"解析 {src_name} 卡片失敗: {e}")
                continue

    except Exception as e:
        logger.error(f"解析 {src_name} HTML 失敗: {e}")

    logger.info(f"{src_name} 總共收集到 {len(events)} 個事件")
    return events


def run():
    """主執行函式"""
    logger.info("=" * 60)
    logger.info("開始收集空投情報...")
    logger.info("=" * 60)

    sources = load_sources()
    all_events = []
    source_stats = {}

    # 記錄所有啟用的來源
    enabled_sources = [
        name for name, cfg in sources.items()
        if cfg.get("enabled") and cfg.get("mode") == "list"
    ]
    logger.info(f"啟用的列表來源: {', '.join(enabled_sources)}")

    # Airdrops.io
    if "airdrops_io" in sources:
        logger.info("--- 開始處理 Airdrops.io ---")
        try:
            events = fetch_airdrops_io(sources["airdrops_io"])
            all_events.extend(events)
            source_stats["airdrops_io"] = len(events)
            logger.info(f"Airdrops.io 完成: {len(events)} 個事件")
        except Exception as e:
            logger.error(f"抓取 Airdrops.io 失敗: {e}", exc_info=True)
            source_stats["airdrops_io"] = 0
    else:
        logger.info("Airdrops.io 未在配置中")

    # CoinMarketCap Airdrops
    if "cmc_airdrops" in sources:
        logger.info("--- 開始處理 CoinMarketCap Airdrops ---")
        try:
            events = fetch_cmc_airdrops(sources["cmc_airdrops"])
            all_events.extend(events)
            source_stats["cmc_airdrops"] = len(events)
            logger.info(f"CoinMarketCap Airdrops 完成: {len(events)} 個事件")
        except Exception as e:
            logger.error(f"抓取 CoinMarketCap Airdrops 失敗: {e}", exc_info=True)
            source_stats["cmc_airdrops"] = 0
    else:
        logger.info("CoinMarketCap Airdrops 未在配置中")

    # Airdrop Checklist
    if "airdrop_checklist" in sources:
        logger.info("--- 開始處理 Airdrop Checklist ---")
        # 在請求之間增加延遲
        if all_events:
            time.sleep(REQUEST_DELAY)
        try:
            events = fetch_airdrop_checklist(sources["airdrop_checklist"])
            all_events.extend(events)
            source_stats["airdrop_checklist"] = len(events)
            logger.info(f"Airdrop Checklist 完成: {len(events)} 個事件")
        except Exception as e:
            logger.error(f"抓取 Airdrop Checklist 失敗: {e}", exc_info=True)
            source_stats["airdrop_checklist"] = 0
    else:
        logger.info("Airdrop Checklist 未在配置中")

    # AltcoinTrading / AirdropsAlert / ICOMarks
    # 使用更通用的選擇器，並針對每個網站優化
    generic_sources = {
        "altcointrading_airdrops": (".airdrop-item", "a"),
        "airdropsalert": (
            # airdropsalert 可能需要更廣泛的選擇器
            # 嘗試多種可能的選擇器（優先順序從左到右）
            "article, .card, .item, .post, .entry, [class*='airdrop'], [class*='list'], div[class*='airdrop'], section[class*='airdrop']",
            "a, h2, h3, h4, .title, [class*='title'], strong, b"
        ),
        "icomarks_airdrops": (".airdrop-item", "a"),
    }

    for src_name, selector_tuple in generic_sources.items():
        if src_name in sources:
            logger.info(f"--- 開始處理 {src_name} ---")
            # 在請求之間增加延遲
            if all_events:  # 不是第一個來源
                time.sleep(REQUEST_DELAY)
            try:
                # 處理 selector_tuple，可能是 tuple 或單一字串
                if isinstance(selector_tuple, tuple):
                    css_card, css_title = selector_tuple
                else:
                    css_card = selector_tuple
                    css_title = "a"

                events = fetch_generic_list_site(
                    src_name,
                    sources[src_name],
                    css_card,
                    css_title
                )
                all_events.extend(events)
                source_stats[src_name] = len(events)
                logger.info(f"{src_name} 完成: {len(events)} 個事件")
            except Exception as e:
                logger.error(f"抓取 {src_name} 失敗: {e}", exc_info=True)
                source_stats[src_name] = 0
        else:
            logger.info(f"{src_name} 未在配置中")

    # 輸出統計資訊
    logger.info("=" * 60)
    logger.info("收集統計:")
    logger.info(f"  總計處理 {len(source_stats)} 個來源")
    for src_name, count in sorted(source_stats.items()):
        status = "✓" if count > 0 else "✗"
        logger.info(f"  {status} {src_name}: {count} 個事件")
    logger.info(f"總計: {len(all_events)} 個事件")

    # 檢查是否有來源沒有資料
    zero_sources = [name for name, count in source_stats.items() if count == 0]
    if zero_sources:
        logger.warning(f"以下來源未收集到資料: {', '.join(zero_sources)}")
        logger.warning("可能原因: CSS selector 不正確、網頁結構改變、或網站有反爬蟲機制")

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

