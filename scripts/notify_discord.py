"""
Discord Webhook 通知器
發送高優先級 alerts 到 Discord channel
"""
import json
import os
import logging
from pathlib import Path
from typing import List, Dict

import requests

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def load_alerts() -> List[Dict]:
    """載入 alerts"""
    p = OUTPUT_DIR / "alerts.json"
    if not p.exists():
        logger.warning(f"alerts.json 不存在: {p}")
        return []
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"載入 alerts.json 失敗: {e}")
        return []


def format_discord_message(alerts: List[Dict]) -> str:
    """格式化 Discord 訊息"""
    if not alerts:
        return "**Airdrop / Launchpool Alerts (High Priority)**\n目前沒有高優先級 alerts。"

    lines = ["**Airdrop / Launchpool Alerts (High Priority)**\n"]
    
    for i, a in enumerate(alerts, 1):
        project = a.get("project", "Unknown")
        alert_type = a.get("type", "Unknown")
        priority = a.get("priority", "medium").upper()
        notes = a.get("notes", "N/A")
        
        # 截斷過長的 notes
        if len(notes) > 200:
            notes = notes[:200] + "..."
        
        line = f"**{i}. [{priority}] {project}**\n"
        line += f"   Type: {alert_type}\n"
        line += f"   {notes}\n"
        
        if a.get("links", {}).get("details"):
            line += f"   🔗 {a.get('links', {}).get('details')}\n"
        
        lines.append(line)
    
    return "\n".join(lines)


def send_discord_webhook(webhook_url: str, content: str) -> bool:
    """發送 Discord Webhook"""
    try:
        payload = {"content": content}
        resp = requests.post(webhook_url, json=payload, timeout=10)
        resp.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"發送 Discord Webhook 失敗: {e}")
        return False


def run():
    """主執行函式"""
    if not WEBHOOK_URL:
        logger.info("未設定 DISCORD_WEBHOOK_URL，跳過 Discord 通知")
        return

    alerts = load_alerts()
    if not alerts:
        logger.info("沒有 alerts 需要發送")
        return

    # 篩選高優先級 alerts（最多 3 筆）
    high_priority = [a for a in alerts if a.get("priority", "medium") == "high"][:3]
    
    if not high_priority:
        logger.info("沒有高優先級 alerts 需要發送")
        return

    logger.info(f"準備發送 {len(high_priority)} 個高優先級 alerts 到 Discord")

    # 格式化訊息
    message = format_discord_message(high_priority)

    # 發送 Webhook
    if send_discord_webhook(WEBHOOK_URL, message):
        logger.info("成功發送 Discord 通知")
    else:
        logger.error("發送 Discord 通知失敗")


if __name__ == "__main__":
    run()

