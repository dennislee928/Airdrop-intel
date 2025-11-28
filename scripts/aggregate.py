"""
規則引擎與報告生成器
整合事件與錢包報告，根據規則產生 alerts 和人類可讀報告
"""
import yaml
import json
import logging
from pathlib import Path
from typing import List, Dict, Set

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
CONFIG_RULES = ROOT / "config" / "rules.yml"
CONFIG_SOURCES = ROOT / "config" / "sources.yml"
CONFIG_TOKENS = ROOT / "config" / "tokens.yml"


def load_json(path: str) -> List[Dict]:
    """載入 JSON 檔案"""
    p = OUTPUT_DIR / path
    if not p.exists():
        logger.warning(f"檔案不存在: {p}")
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"載入 {path} 失敗: {e}")
        return []


def load_rules() -> List[Dict]:
    """載入規則配置"""
    try:
        with open(CONFIG_RULES, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("rules", [])
    except Exception as e:
        logger.error(f"載入 rules.yml 失敗: {e}")
        return []


def load_sources_cfg() -> Dict:
    """載入來源配置"""
    try:
        with open(CONFIG_SOURCES, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("sources", {})
    except Exception as e:
        logger.error(f"載入 sources.yml 失敗: {e}")
        return {}


def load_tokens() -> List[Dict]:
    """載入追蹤幣種配置"""
    try:
        with open(CONFIG_TOKENS, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("tokens", [])
    except Exception as e:
        logger.error(f"載入 tokens.yml 失敗: {e}")
        return []


def is_token_in_watchlist(token_symbol: str, tokens: List[Dict]) -> bool:
    """檢查 token 是否在追蹤列表中"""
    if not token_symbol:
        return False
    return any(t.get("symbol", "").upper() == token_symbol.upper() for t in tokens)


def apply_rules(events: List[Dict], wallets: List[Dict], rules: List[Dict], tokens: List[Dict]) -> List[Dict]:
    """根據規則匹配事件和錢包，產生 alerts"""
    alerts = []
    seen_alerts: Set[str] = set()  # 用於去重

    # 1) 針對 events（上市、Launchpool 等）
    for ev in events:
        for rule in rules:
            if rule.get("type") != "listing":
                continue

            match_conditions = rule.get("match", {})
            
            # 檢查 category
            category = ev.get("category", "").lower()
            if "launchpool" in category or "earn" in category:
                # 檢查 token 是否在 watchlist
                token_in_watchlist = match_conditions.get("token_in_watchlist", False)
                if token_in_watchlist:
                    token_symbol = ev.get("token")
                    if not is_token_in_watchlist(token_symbol, tokens):
                        continue

                # 產生 alert key 用於去重
                alert_key = f"{ev.get('source')}_{ev.get('token')}_{ev.get('project')}"
                if alert_key in seen_alerts:
                    continue
                seen_alerts.add(alert_key)

                alerts.append({
                    "token": ev.get("token"),
                    "project": ev.get("project", ev.get("token", "Unknown")),
                    "type": "New listing / campaign",
                    "priority": rule.get("priority", "medium"),
                    "source": ev.get("source"),
                    "exchange": ev.get("exchange"),
                    "pair": ev.get("pair"),
                    "status": ev.get("status"),
                    "notes": f"Detected new listing/campaign on {ev.get('exchange', 'unknown exchange')} ({ev.get('pair', 'N/A')}). Status: {ev.get('status', 'unknown')}.",
                    "links": ev.get("links", {}),
                    "labels": ["airdrop", "launchpool"],
                })

    # 2) 針對 wallets（活動量 / 潛在空投 profile）
    for w in wallets:
        for rule in rules:
            if rule.get("type") != "wallet_activity":
                continue

            match_conditions = rule.get("match", {})
            chain_in = match_conditions.get("chain_in", [])
            tx_count_min = match_conditions.get("tx_count_min", 0)
            has_defi_activity = match_conditions.get("has_defi_activity", False)

            # 檢查鏈別
            if chain_in and w.get("chain") not in chain_in:
                continue

            # 檢查交易次數
            if w.get("tx_count", 0) < tx_count_min:
                continue

            # 檢查 DeFi 活動
            if has_defi_activity and not w.get("has_defi_activity", False):
                continue

            # 產生 alert key 用於去重
            alert_key = f"wallet_{w.get('name')}_{w.get('chain')}"
            if alert_key in seen_alerts:
                continue
            seen_alerts.add(alert_key)

            alerts.append({
                "token": "MULTI",
                "project": "Generic Airdrop Profile",
                "type": "Wallet potentially qualifies for retroactive airdrops",
                "priority": rule.get("priority", "medium"),
                "source": "wallets_report",
                "wallet_name": w.get("name"),
                "wallet_address": w.get("address"),
                "wallet_chain": w.get("chain"),
                "tx_count": w.get("tx_count", 0),
                "notes": f"Wallet {w.get('name')} on {w.get('chain')} has {w.get('tx_count', 0)} txs. May qualify for retroactive airdrops.",
                "labels": ["airdrop", "wallet-profile"],
            })

    logger.info(f"規則引擎產生 {len(alerts)} 個 alerts")
    return alerts


def write_human_report(alerts: List[Dict], wallets: List[Dict]):
    """產生人類可讀的報告"""
    sources_cfg = load_sources_cfg()
    lines = ["# Airdrop / Launchpool Daily Report\n"]

    # 1) 高優先級 alerts
    if not alerts:
        lines.append("目前沒有高優先級 alert。\n")
    else:
        # 按優先級排序
        priority_order = {"high": 0, "medium": 1, "low": 2}
        sorted_alerts = sorted(alerts, key=lambda x: priority_order.get(x.get("priority", "low"), 2))

        for a in sorted_alerts:
            priority = a.get("priority", "medium").upper()
            lines.append(f"## [{priority}] {a.get('project', 'Unknown')} - {a.get('type', 'Unknown')}")
            lines.append(f"- **Token:** {a.get('token', 'N/A')}")
            
            if a.get("exchange"):
                lines.append(f"- **Exchange:** {a.get('exchange')} ({a.get('pair', 'N/A')})")
            
            if a.get("wallet_name"):
                lines.append(f"- **Wallet:** {a.get('wallet_name')} ({a.get('wallet_address', 'N/A')})")
                lines.append(f"- **Chain:** {a.get('wallet_chain', 'N/A')}")
                lines.append(f"- **TX Count:** {a.get('tx_count', 0)}")
            
            if a.get("status"):
                lines.append(f"- **Status:** {a.get('status')}")
            
            lines.append(f"- **Source:** {a.get('source', 'N/A')}")
            lines.append(f"- **Notes:** {a.get('notes', 'N/A')}")
            
            if a.get("links"):
                links = a.get("links", {})
                if links.get("details"):
                    lines.append(f"- **Details:** {links.get('details')}")
                if links.get("official"):
                    lines.append(f"- **Official:** {links.get('official')}")
            
            lines.append("")

    # 2) 錢包活動摘要
    lines.append("## Wallet Activity Summary\n")
    if not wallets:
        lines.append("沒有配置任何錢包。\n")
    else:
        for w in wallets:
            lines.append(f"### {w.get('name', 'Unknown')} ({w.get('chain', 'unknown')})")
            lines.append(f"- **Address:** `{w.get('address', 'N/A')}`")
            lines.append(f"- **TX Count:** {w.get('tx_count', 0)}")
            lines.append(f"- **DeFi Activity:** {'Yes' if w.get('has_defi_activity', False) else 'No'}")
            if w.get("error"):
                lines.append(f"- **Error:** {w.get('error')}")
            lines.append("")

    # 3) EarnDrop / Bankless Claimables 快捷入口
    lines.append("## Wallet-based Tools\n")

    if sources_cfg.get("earndrop", {}).get("enabled"):
        lines.append("### EarnDrop")
        lines.append("請用以下地址在 EarnDrop 介面檢查空投資格：")
        if wallets:
            for w in wallets:
                lines.append(f"- **{w.get('name', 'Unknown')}:** `{w.get('address', 'N/A')}`")
        else:
            lines.append("- 沒有配置錢包")
        lines.append(f"**入口：** {sources_cfg.get('earndrop', {}).get('urls', {}).get('main', 'N/A')}\n")

    if sources_cfg.get("bankless_claimables", {}).get("enabled"):
        lines.append("### Bankless Claimables")
        lines.append("請用以下地址在 Bankless Claimables 介面檢查未領取空投：")
        if wallets:
            for w in wallets:
                lines.append(f"- **{w.get('name', 'Unknown')}:** `{w.get('address', 'N/A')}`")
        else:
            lines.append("- 沒有配置錢包")
        lines.append(f"**入口：** {sources_cfg.get('bankless_claimables', {}).get('urls', {}).get('main', 'N/A')}\n")

    # 寫出報告
    output_file = OUTPUT_DIR / "latest_report.md"
    try:
        content = "\n".join(lines)
        output_file.write_text(content, encoding="utf-8")
        logger.info(f"成功寫入報告到 {output_file}")
    except Exception as e:
        logger.error(f"寫入 latest_report.md 失敗: {e}")


def run():
    """主執行函式"""
    logger.info("開始整合事件與錢包報告...")

    events = load_json("events_sources.json")
    wallets = load_json("wallets_report.json")
    rules = load_rules()
    tokens = load_tokens()

    logger.info(f"載入 {len(events)} 個事件, {len(wallets)} 個錢包報告, {len(rules)} 條規則")

    alerts = apply_rules(events, wallets, rules, tokens)

    # 寫出 alerts.json
    output_file = OUTPUT_DIR / "alerts.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(alerts, f, ensure_ascii=False, indent=2)
        logger.info(f"成功寫入 {len(alerts)} 個 alerts 到 {output_file}")
    except Exception as e:
        logger.error(f"寫入 alerts.json 失敗: {e}")

    # 寫出人類可讀報告
    write_human_report(alerts, wallets)


if __name__ == "__main__":
    run()

