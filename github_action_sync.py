"""
Scrapes polls from themadad.com and pushes new rows to the live dashboard
via the /api/sync-polls endpoint.

Run by GitHub Actions — NOT from the Fly.io machine (its IP is blocked).
"""

import json
import os
import sys
import logging
from datetime import datetime
from io import StringIO

import requests
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────────────
MADAD_URL    = "https://themadad.com/allpolls/"
DASHBOARD    = os.environ.get("DASHBOARD_URL", "https://roza-polls.fly.dev")
SYNC_KEY     = os.environ.get("SYNC_KEY", "")
SYNC_ENDPOINT = f"{DASHBOARD}/api/sync-polls"

HE_TO_EN = {
    "מספר הסקר": "poll_number",
    "תאריך": "date",
    "משיבים": "respondents",
    "כלי תקשורת": "media_outlet",
    "עורך משאלים": "pollster",
    "הליכוד": "likud",
    "יהדות התורה": "yahadut_tora",
    'ש"ס': "shas",
    "ש״ס": "shas",
    "כחול לבן": "kahol_lavan",
    "יש עתיד": "yesh_atid",
    'חדש תע"ל': "hadash_taal",
    "חדש תע״ל": "hadash_taal",
    "ישראל ביתנו": "israel_beiteinu",
    "הדמוקרטים": "demokratim",
    "הציונות הדתית": "zionut_datit",
    'רע"מ': "raam",
    "רע״מ": "raam",
    'בל"ד': "balad",
    "בל״ד": "balad",
    "עוצמה יהודית": "otzma_yehudit",
    "ביחד (בנט ולפיד)": "beyahad",
    "ישר!": "yashar",
    "המילואימניקים": "miluimnikim",
    "‏רשימה ערבית מאוחדת": "reshima_meshutefet",
    "רשימה ערבית מאוחדת": "reshima_meshutefet",
}

PARTY_COLUMNS = [
    "likud", "yahadut_tora", "shas", "kahol_lavan", "yesh_atid",
    "hadash_taal", "israel_beiteinu", "demokratim", "zionut_datit",
    "raam", "balad", "otzma_yehudit", "beyahad", "yashar",
    "miluimnikim", "reshima_meshutefet",
]


def fetch() -> pd.DataFrame:
    log.info("Fetching %s", MADAD_URL)
    resp = requests.get(
        MADAD_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
            "Referer": "https://themadad.com/",
        },
        timeout=30,
    )
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    if not tables:
        raise ValueError("No tables on page")
    df = tables[0]
    log.info("Got %d rows", len(df))
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [c.strip().lstrip("‏‎‪‬") for c in df.columns]
    df = df.rename(columns=HE_TO_EN)
    df["poll_number"] = df["poll_number"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    df["respondents"] = pd.to_numeric(df["respondents"], errors="coerce")
    df["media_outlet"] = df.get("media_outlet", pd.Series(dtype=str)).astype(str).str.strip()
    df["pollster"] = df.get("pollster", pd.Series(dtype=str)).astype(str).str.strip()
    for col in PARTY_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = None
    df["fetched_at"] = datetime.utcnow().isoformat()
    return df


def push(df: pd.DataFrame) -> dict:
    if not SYNC_KEY:
        raise RuntimeError("SYNC_KEY env var is not set")
    # Convert NaN → None so JSON serializes correctly
    rows = json.loads(df.to_json(orient="records", date_format="iso", force_ascii=False))
    log.info("Sending %d rows to %s", len(rows), SYNC_ENDPOINT)
    resp = requests.post(
        SYNC_ENDPOINT,
        json=rows,
        headers={"X-Sync-Key": SYNC_KEY, "Content-Type": "application/json"},
        timeout=30,
    )
    resp.raise_for_status()
    result = resp.json()
    log.info("Server response: %s", result)
    return result


def main():
    try:
        raw = fetch()
    except Exception as e:
        log.error("Fetch failed: %s", e)
        sys.exit(1)

    df = normalize(raw)
    try:
        result = push(df)
    except Exception as e:
        log.error("Push failed: %s", e)
        sys.exit(1)

    added = result.get("added", 0)
    log.info("Done — %d new polls added", added)
    print(f"::notice title=Polls sync::Added {added} new rows ({result.get('received')} total sent)")


if __name__ == "__main__":
    main()
