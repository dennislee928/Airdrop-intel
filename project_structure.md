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
