"""
GitHub Issues 通知器
將 alerts 轉換為 GitHub Issues，包含去重邏輯
"""
import json
import os
import logging
from pathlib import Path
from typing import List, Dict, Set

from github import Github
from github.GithubException import GithubException

# 設定日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"


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


def get_existing_issues(repo) -> Set[str]:
    """取得現有 Issues 的標題集合（用於去重）"""
    existing_titles = set()
    try:
        # 只檢查 open 的 issues
        issues = repo.get_issues(state="open")
        for issue in issues:
            existing_titles.add(issue.title)
        logger.info(f"找到 {len(existing_titles)} 個現有的 open issues")
    except Exception as e:
        logger.warning(f"取得現有 issues 失敗: {e}")
    return existing_titles


def create_issue_title(alert: Dict) -> str:
    """產生 Issue 標題"""
    token = alert.get("token", "UNKNOWN")
    project = alert.get("project", "Unknown")
    alert_type = alert.get("type", "Unknown")
    return f"[{token}] {project} - {alert_type}"


def create_issue_body(alert: Dict) -> str:
    """產生 Issue 內容"""
    body_lines = [
        f"**Type:** {alert.get('type', 'N/A')}",
        f"**Priority:** {alert.get('priority', 'medium')}",
        f"**Source:** {alert.get('source', 'N/A')}",
        "",
    ]

    if alert.get("exchange"):
        body_lines.insert(3, f"**Exchange:** {alert.get('exchange')} ({alert.get('pair', 'N/A')})")

    if alert.get("wallet_name"):
        body_lines.insert(3, f"**Wallet:** {alert.get('wallet_name')} ({alert.get('wallet_address', 'N/A')})")
        if alert.get("wallet_chain"):
            body_lines.insert(4, f"**Chain:** {alert.get('wallet_chain')}")
        if alert.get("tx_count") is not None:
            body_lines.insert(5, f"**TX Count:** {alert.get('tx_count')}")

    if alert.get("status"):
        body_lines.append(f"**Status:** {alert.get('status')}")

    body_lines.append("")
    body_lines.append("**Notes:**")
    body_lines.append(alert.get("notes", "N/A"))

    # 加入連結
    if alert.get("links"):
        links = alert.get("links", {})
        body_lines.append("")
        body_lines.append("**Links:**")
        if links.get("details"):
            body_lines.append(f"- Details: {links.get('details')}")
        if links.get("official"):
            body_lines.append(f"- Official: {links.get('official')}")
        if links.get("twitter"):
            body_lines.append(f"- Twitter: {links.get('twitter')}")

    return "\n".join(body_lines)


def run():
    """主執行函式"""
    alerts = load_alerts()
    if not alerts:
        logger.info("沒有 alerts 需要建立 issues")
        return

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.warning("未設定 GITHUB_TOKEN，跳過 GitHub Issues 建立")
        return

    repo_name = os.environ.get("GITHUB_REPOSITORY")
    if not repo_name:
        logger.warning("未設定 GITHUB_REPOSITORY，跳過 GitHub Issues 建立")
        return

    try:
        g = Github(token)
        repo = g.get_repo(repo_name)
        logger.info(f"連線到 repository: {repo_name}")

        # 取得現有 issues 標題（用於去重）
        existing_titles = get_existing_issues(repo)

        created_count = 0
        skipped_count = 0

        for alert in alerts:
            title = create_issue_title(alert)

            # 檢查是否已存在
            if title in existing_titles:
                logger.info(f"Issue 已存在，跳過: {title}")
                skipped_count += 1
                continue

            try:
                body = create_issue_body(alert)
                labels = alert.get("labels", ["airdrop"])

                # 建立 issue
                issue = repo.create_issue(
                    title=title,
                    body=body,
                    labels=labels
                )
                logger.info(f"成功建立 Issue #{issue.number}: {title}")
                created_count += 1

                # 加入現有標題集合，避免同一次執行中重複建立
                existing_titles.add(title)

            except GithubException as e:
                if e.status == 422:
                    # 可能是標籤不存在或其他驗證錯誤
                    logger.warning(f"建立 Issue 失敗 (422): {title} - {e.data}")
                    # 嘗試不帶標籤建立
                    try:
                        body = create_issue_body(alert)
                        issue = repo.create_issue(
                            title=title,
                            body=body
                        )
                        logger.info(f"成功建立 Issue #{issue.number} (無標籤): {title}")
                        created_count += 1
                        existing_titles.add(title)
                    except Exception as e2:
                        logger.error(f"建立 Issue 最終失敗: {title} - {e2}")
                else:
                    logger.error(f"建立 Issue 失敗: {title} - {e}")

            except Exception as e:
                logger.error(f"建立 Issue 時發生未預期錯誤: {title} - {e}")

        logger.info(f"Issue 建立完成: 成功 {created_count} 個, 跳過 {skipped_count} 個")

    except GithubException as e:
        logger.error(f"GitHub API 錯誤: {e}")
    except Exception as e:
        logger.error(f"執行失敗: {e}")


if __name__ == "__main__":
    run()

