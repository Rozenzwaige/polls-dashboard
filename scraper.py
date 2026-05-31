"""
Scrapes poll data from themadad.com and stores it in SQLite.
Run directly to do a one-time fetch; also called by the scheduler in app.py.
"""

import sqlite3
import requests
import pandas as pd
from datetime import datetime
from io import StringIO
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
log = logging.getLogger(__name__)

DB_PATH = "polls.db"
URL = "https://themadad.com/allpolls/"

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


def init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS polls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            poll_number TEXT UNIQUE,
            date TEXT,
            respondents INTEGER,
            media_outlet TEXT,
            pollster TEXT,
            likud REAL, yahadut_tora REAL, shas REAL, kahol_lavan REAL,
            yesh_atid REAL, hayamin_hehadash REAL, israel_beiteinu REAL,
            demokratim REAL, zionut_datit REAL, raam REAL, balad REAL,
            otzma_yehudit REAL, bennett_lapid REAL, yamina REAL,
            miluimnikim REAL, reshima_meshutefet REAL,
            fetched_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT
        )
    """)
    conn.commit()


def fetch_polls() -> pd.DataFrame:
    log.info("Fetching polls from %s", URL)
    session = requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8",
        "Referer": "https://themadad.com/",
    }
    resp = session.get(URL, headers=headers, timeout=30)
    resp.raise_for_status()
    tables = pd.read_html(StringIO(resp.text))
    if not tables:
        raise ValueError("No tables found on page")
    df = tables[0]
    log.info("Got %d rows", len(df))
    return df


def normalize(df: pd.DataFrame) -> pd.DataFrame:
    # Strip invisible chars from column names before renaming
    df.columns = [c.strip().lstrip("‏‎‪‬") for c in df.columns]
    df = df.rename(columns=HE_TO_EN)

    df["poll_number"] = df["poll_number"].astype(str).str.strip()
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce").dt.strftime("%Y-%m-%d")
    df["respondents"] = pd.to_numeric(df["respondents"], errors="coerce")
    df["media_outlet"] = df["media_outlet"].astype(str).str.strip()
    df["pollster"] = df["pollster"].astype(str).str.strip()

    for col in PARTY_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        else:
            df[col] = None

    df["fetched_at"] = datetime.utcnow().isoformat()
    return df


def upsert(df: pd.DataFrame, conn: sqlite3.Connection) -> int:
    new_rows = 0
    for _, row in df.iterrows():
        try:
            conn.execute(
                """
                INSERT OR IGNORE INTO polls
                (poll_number, date, respondents, media_outlet, pollster,
                 likud, yahadut_tora, shas, kahol_lavan, yesh_atid,
                 hayamin_hehadash, israel_beiteinu, demokratim, zionut_datit,
                 raam, balad, otzma_yehudit, bennett_lapid, yamina,
                 miluimnikim, reshima_meshutefet, fetched_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    row.get("poll_number"),
                    row.get("date"),
                    row.get("respondents"),
                    row.get("media_outlet"),
                    row.get("pollster"),
                    row.get("likud"),
                    row.get("yahadut_tora"),
                    row.get("shas"),
                    row.get("kahol_lavan"),
                    row.get("yesh_atid"),
                    row.get("hayamin_hehadash"),
                    row.get("israel_beiteinu"),
                    row.get("demokratim"),
                    row.get("zionut_datit"),
                    row.get("raam"),
                    row.get("balad"),
                    row.get("otzma_yehudit"),
                    row.get("bennett_lapid"),
                    row.get("yamina"),
                    row.get("miluimnikim"),
                    row.get("reshima_meshutefet"),
                    row.get("fetched_at"),
                ),
            )
            if conn.execute("SELECT changes()").fetchone()[0]:
                new_rows += 1
        except Exception as e:
            log.warning("Row skipped: %s", e)
    conn.commit()
    return new_rows


def run_scrape():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    try:
        df = fetch_polls()
        df = normalize(df)
        new = upsert(df, conn)
        log.info("Done — %d new polls added", new)
        return new
    finally:
        conn.close()


if __name__ == "__main__":
    run_scrape()
