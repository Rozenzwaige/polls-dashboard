"""
מריץ סקריפ מקומי ושולח נתונים חדשים לשרת.
מיועד לרוץ דרך Windows Task Scheduler — לא מה-cloud.

השרת חוסם Fly.io ו-GitHub Actions (IP של AWS/cloud).
המחשב הפרטי עובד בלי בעיה.
"""

import os
import sys
import logging
from pathlib import Path

# Make sure we run from the script's directory
HERE = Path(__file__).parent
os.chdir(HERE)

# Set DATA_DIR so scraper saves locally
os.environ.setdefault("DATA_DIR", str(HERE))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(HERE / "sync.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

# ── Import sync logic from github_action_sync ────────────────────────────────
import json
import requests
import pandas as pd
from github_action_sync import fetch, normalize, SYNC_ENDPOINT, HE_TO_EN, PARTY_COLUMNS

SYNC_KEY = os.environ.get("SYNC_KEY", "A9FIyut_uLs21JbH6MzZ3LvtthlKMGJp3FnEC0X7x3s")


def main():
    log.info("=== Starting local poll sync ===")

    try:
        raw = fetch()
    except Exception as e:
        log.error("Fetch failed: %s", e)
        sys.exit(1)

    df = normalize(raw)
    log.info("Scraped %d rows", len(df))

    rows = json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))

    try:
        resp = requests.post(
            SYNC_ENDPOINT,
            json=rows,
            headers={"X-Sync-Key": SYNC_KEY, "Content-Type": "application/json"},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        log.info("Server: %s new rows added (out of %s sent)", result.get("added"), result.get("received"))
    except Exception as e:
        log.error("Push to server failed: %s", e)
        sys.exit(1)

    log.info("=== Done ===")


if __name__ == "__main__":
    main()
