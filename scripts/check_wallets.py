"""
錢包活動檢查器
透過鏈上 API 查詢錢包活動指標（只讀，不操作資產）
"""
import yaml
import json
import os
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_WALLETS = ROOT / "config" / "wallets.yml"
OUTPUT_DIR = ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

ETHERSCAN_API_KEY = os.environ.get("ETHERSCAN_API_KEY")

# 重試設定
MAX_RETRIES = 3
RETRY_DELAY = 2  # 秒


def load_wallets() -> List[Dict]:
    """載入錢包配置"""
    try:
        with open(CONFIG_WALLETS, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            return data.get("wallets", [])
    except Exception as e:
        logger.error(f"載入 wallets.yml 失敗: {e}")
        return []


def get_eth_tx_count(address: str) -> int:
    """使用 Etherscan API 查詢以太坊地址的交易次數"""
    if not ETHERSCAN_API_KEY:
        logger.warning("未設定 ETHERSCAN_API_KEY，跳過以太坊查詢")
        return 0

    url = "https://api.etherscan.io/api"
    params = {
        "module": "proxy",
        "action": "eth_getTransactionCount",
        "address": address,
        "tag": "latest",
        "apikey": ETHERSCAN_API_KEY,
    }

    for attempt in range(MAX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") == "1" and data.get("result"):
                tx_count = int(data["result"], 16)
                logger.info(f"地址 {address} 交易次數: {tx_count}")
                return tx_count
            else:
                error_msg = data.get("message", "Unknown error")
                logger.warning(f"Etherscan API 回應錯誤: {error_msg}")
                return 0

        except requests.exceptions.RequestException as e:
            logger.warning(f"Etherscan API 請求失敗 (嘗試 {attempt + 1}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
            else:
                logger.error(f"無法取得地址 {address} 的交易次數")
                return 0
        except (ValueError, KeyError) as e:
            logger.error(f"解析 Etherscan API 回應失敗: {e}")
            return 0

    return 0


def get_arbitrum_tx_count(address: str) -> int:
    """使用 Arbiscan API 查詢 Arbitrum 地址的交易次數（預留擴充）"""
    # TODO: 實作 Arbiscan API 整合
    logger.info(f"Arbitrum 查詢尚未實作，地址: {address}")
    return 0


def get_optimism_tx_count(address: str) -> int:
    """使用 Optimistic Etherscan API 查詢 Optimism 地址的交易次數（預留擴充）"""
    # TODO: 實作 Optimistic Etherscan API 整合
    logger.info(f"Optimism 查詢尚未實作，地址: {address}")
    return 0


def analyze_wallet_activity(wallet: Dict) -> Dict:
    """分析錢包活動指標"""
    chain = wallet.get("chain", "").lower()
    addr = wallet.get("address", "")
    name = wallet.get("name", "unknown")

    if not addr:
        logger.warning(f"錢包 {name} 沒有地址")
        return {
            "name": name,
            "chain": chain,
            "address": addr,
            "tx_count": 0,
            "has_defi_activity": False,
            "error": "No address provided",
        }

    logger.info(f"分析錢包活動: {name} ({chain}) - {addr}")

    tx_count = 0
    if chain == "ethereum":
        tx_count = get_eth_tx_count(addr)
    elif chain == "arbitrum":
        tx_count = get_arbitrum_tx_count(addr)
    elif chain == "optimism":
        tx_count = get_optimism_tx_count(addr)
    else:
        logger.warning(f"不支援的鏈: {chain}，地址: {addr}")

    # 使用交易次數作為 DeFi 活動的粗略指標
    # 未來可以擴充：檢查特定合約互動、NFT 持有等
    has_defi_activity = tx_count >= 20

    result = {
        "name": name,
        "chain": chain,
        "address": addr,
        "tx_count": tx_count,
        "has_defi_activity": has_defi_activity,
    }

    logger.info(f"錢包 {name} 分析完成: {tx_count} 筆交易, DeFi 活動: {has_defi_activity}")
    return result


def run():
    """主執行函式"""
    logger.info("開始檢查錢包活動...")
    wallets = load_wallets()

    if not wallets:
        logger.warning("沒有配置任何錢包")
        reports = []
    else:
        reports = []
        for wallet in wallets:
            try:
                report = analyze_wallet_activity(wallet)
                reports.append(report)
            except Exception as e:
                logger.error(f"分析錢包 {wallet.get('name', 'unknown')} 失敗: {e}")
                reports.append({
                    "name": wallet.get("name", "unknown"),
                    "chain": wallet.get("chain", "unknown"),
                    "address": wallet.get("address", ""),
                    "tx_count": 0,
                    "has_defi_activity": False,
                    "error": str(e),
                })

    # 寫出報告
    output_file = OUTPUT_DIR / "wallets_report.json"
    try:
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(reports, f, ensure_ascii=False, indent=2)
        logger.info(f"成功寫入 {len(reports)} 個錢包報告到 {output_file}")
    except Exception as e:
        logger.error(f"寫入 wallets_report.json 失敗: {e}")


if __name__ == "__main__":
    run()

