"""
Dash dashboard for Israeli election polls.
Public:  /
Admin:   /admin  (password protected — event management)
"""

import json
import os
import sqlite3

import pandas as pd
import plotly.graph_objects as go
from dash import (
    ALL, Dash, Input, Output, State, callback_context, dcc, html, no_update,
)
import dash_bootstrap_components as dbc
from apscheduler.schedulers.background import BackgroundScheduler

from scraper import DB_PATH, init_db, run_scrape

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "rozamedia2026")
SITE_PASSWORD = os.environ.get("SITE_PASSWORD", "Rosa2026!!")
_DATA = os.environ.get("DATA_DIR", ".")
EVENTS_DB_PATH = f"{_DATA}/events.db"   # separate from polls.db — never deleted on schema reset

BLOCS = [
    # סדר מימין לשמאל בכנסת — בגרף: ימין קיצוני בקצה הימני
    {"name": "ערבים",            "parties": ["hadash_taal", "balad", "raam", "reshima_meshutefet"],                   "color": "#065F46"},
    {"name": "מרכז-שמאל",        "parties": ["demokratim"],                                                            "color": "#D93025"},
    {"name": "חרדים",            "parties": ["yahadut_tora", "shas"],                                                  "color": "#1B4332"},
    {"name": "ימין סוציאלי",     "parties": ["likud"],                                                                 "color": "#3D1040"},
    {"name": "ימין ניאו-ליברלי", "parties": ["beyahad", "israel_beiteinu", "kahol_lavan", "yashar", "miluimnikim"],   "color": "#1E3A8A"},
    {"name": "ימין קיצוני",      "parties": ["zionut_datit", "otzma_yehudit"],                                        "color": "#7F1D1D"},
]

DEFAULT_PARTIES = [
    "likud", "yesh_atid", "zionut_datit", "shas",
    "yahadut_tora", "israel_beiteinu", "demokratim", "beyahad",
]

PARTY_HE = {
    "likud":              "הליכוד",
    "yahadut_tora":       "יהדות התורה",
    "shas":               'ש"ס',
    "kahol_lavan":        "כחול לבן",
    "yesh_atid":          "יש עתיד",
    "hadash_taal":        'חדש תע"ל',
    "israel_beiteinu":    "ישראל ביתנו",
    "demokratim":         "הדמוקרטים",
    "zionut_datit":       "הציונות הדתית",
    "raam":               'רע"מ',
    "balad":              'בל"ד',
    "otzma_yehudit":      "עוצמה יהודית",
    "beyahad":            "ביחד",
    "yashar":             "ישר!",
    "miluimnikim":        "מילואימניקים",
    "reshima_meshutefet": "רשימה ערבית",
}

PARTY_COLORS = {
    "likud":              "#3D1040",
    "yahadut_tora":       "#7B3F8C",
    "shas":               "#8B4513",
    "kahol_lavan":        "#4682B4",
    "yesh_atid":          "#D93025",
    "hadash_taal":        "#2E8B57",
    "israel_beiteinu":    "#1565C0",
    "demokratim":         "#C2185B",
    "zionut_datit":       "#8B0000",
    "raam":               "#2E7D32",
    "balad":              "#1B5E20",
    "otzma_yehudit":      "#B71C1C",
    "beyahad":            "#E65100",
    "yashar":             "#6A1B9A",
    "miluimnikim":        "#607D8B",
    "reshima_meshutefet": "#004D40",
}

# ── Mock feed (replace with real Telegram Bot API when token is available) ────
# Each item: time, date, type ("poll"/"news"/"alert"), source, title, content, views
MOCK_FEED = [
    {"time": "16:45", "date": "31/05", "type": "poll",
     "source": "מעריב",
     "title": "סקר חדש 📊",
     "content": "ליכוד 23 · ביחד 22 · הדמוקרטים 10 · ציונות דתית 9 · יהדות התורה 7",
     "views": "1.4K"},
    {"time": "14:12", "date": "31/05", "type": "news",
     "source": "ערוץ 13",
     "title": "נפתחו שיחות בין ביחד לדמוקרטים",
     "content": "לפי הדיווח, ראשי שתי הרשימות נפגשו הלילה לבחינת פלטפורמה משותפת",
     "views": "3.2K"},
    {"time": "11:30", "date": "31/05", "type": "poll",
     "source": "ישראל היום",
     "title": "סקר חדש 📊",
     "content": "ליכוד 25 · ביחד 22 · ציונות דתית 8 · יהדות התורה 7",
     "views": "987"},
    {"time": "09:00", "date": "31/05", "type": "alert",
     "source": "רוזה ניוז",
     "title": "⚡ ניתוח שבועי",
     "content": "הדמוקרטים ממשיכים לעלות — 10 מנדטים בממוצע שלושת השבועות האחרונים",
     "views": "2.1K"},
    {"time": "22:15", "date": "30/05", "type": "poll",
     "source": "מכון הארץ",
     "title": "סקר חדש 📊",
     "content": "ביחד 24 · ליכוד 23 · הדמוקרטים 9 · ש\"ס 8",
     "views": "1.8K"},
    {"time": "18:40", "date": "30/05", "type": "news",
     "source": "וואלה",
     "title": "שר הביטחון: 'לוח הזמנים לבחירות ברור'",
     "content": "בראיון לוואלה חדשות הסביר: 'אנחנו עומדים בתאריך שנקבע'",
     "views": "4.5K"},
]


EVENT_COLORS = {
    "ביטחוני": "#8B0000",
    "כלכלי":   "#2E7D32",
    "פוליטי":  "#3D1040",
    "חברתי":   "#D93025",
    "אחר":     "#607D8B",
}


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    return conn


def load_polls(outlets=None):
    conn = get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM polls WHERE date IS NOT NULL ORDER BY date", conn
    )
    conn.close()
    if outlets:
        df = df[df["media_outlet"].isin(outlets)]
    return df


def get_events_conn():
    conn = sqlite3.connect(EVENTS_DB_PATH)
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
    return conn


def load_events():
    conn = get_events_conn()
    df = pd.read_sql_query("SELECT * FROM events ORDER BY date", conn)
    conn.close()
    return df


def get_outlets():
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT media_outlet FROM polls "
        "WHERE media_outlet != '' ORDER BY media_outlet"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_event_db(date, title, description, category):
    conn = get_events_conn()
    conn.execute(
        "INSERT INTO events (date, title, description, category) VALUES (?,?,?,?)",
        (date, title, description, category),
    )
    conn.commit()
    conn.close()


def delete_event_db(event_id):
    conn = get_events_conn()
    conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(run_scrape, "interval", minutes=30, id="scrape")
scheduler.start()
run_scrape()


# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="רוזה ניוז | בחירות 2026",
    suppress_callback_exceptions=True,
)

app.index_string = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
{%metas%}
<title>{%title%}</title>
<link rel="icon" type="image/png" href="/assets/rose.png">
{%css%}
<link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;700;900&display=swap" rel="stylesheet">
<style>
  :root {
    --purple:   #3D1040;
    --coral:    #D93025;
    --lime:     #CCDD00;
    --white:    #FFFFFF;
    --bg:       #F7F5F2;
    --border:   #E0D8E8;
    --muted:    #6B6B6B;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: "Heebo", Arial, sans-serif;
    background: var(--bg);
    color: #1A1A1A;
    direction: rtl;
  }

  /* ── Header ── */
  .site-header {
    background: #E8D5F5;
    padding: 0 28px;
    height: 58px;           /* FIXED — never grows */
    display: flex;
    align-items: center;
    gap: 18px;
    border-bottom: 3px solid var(--lime);
    overflow: visible;      /* allow logo to bleed out */
    position: relative;
    z-index: 10;
  }
  .header-rose { height: 38px; width: auto; flex-shrink: 0; }
  .header-logo-white {
    /* Layout size stays small — transform makes it visually large */
    height: 28px;
    width: auto;
    filter: invert(1) brightness(0.15);
    flex-shrink: 0;
    /* Scale up visually without affecting layout / header height */
    transform: scale(3.2);
    transform-origin: right center;
    /* Push other elements away so scaled logo doesn't overlap */
    margin-left: 120px;
  }
  .header-status {
    margin-right: auto;
    color: rgba(61,16,64,0.4);
    font-size: 0.68rem;
    direction: ltr;
    white-space: nowrap;
  }

  /* ── Main ── */
  .main { padding: 18px 28px; }
  .feed-panel { min-height: 560px; max-height: 560px; }

  /* ── Chart wrapper ── */
  .chart-wrapper {
    position: relative;
    background: var(--white);
    border: none;
    border-radius: 6px 6px 0 0;
    overflow: visible;
  }
  /* Chart overlays — inside chart box */
  .ct-overlay-left {
    position: absolute;
    top: 10px;
    left: 14px;
    z-index: 20;
    display: flex;
    gap: 2px;
    background: rgba(247,245,242,0.95);
    border-radius: 4px;
    padding: 2px 4px;
    border: 1px solid var(--border);
  }
  .ct-overlay-right {
    position: absolute;
    top: 10px;
    right: 14px;
    z-index: 20;
    display: flex;
    gap: 2px;
    background: rgba(247,245,242,0.95);
    border-radius: 4px;
    padding: 2px 4px;
    border: 1px solid var(--border);
  }
  .ct-group { display: flex; gap: 2px; }
  .ct-btn {
    padding: 3px 10px;
    font-family: inherit;
    font-size: 0.72rem;
    font-weight: 700;
    border: none;
    border-radius: 3px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.12s;
    white-space: nowrap;
  }
  .ct-btn.active {
    background: var(--purple);
    color: var(--lime);
  }

  /* ── Outlet pills (right column) ── */
  .outlet-col {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding-top: 2px;
  }
  .o-pill {
    display: block;
    width: 100%;
    padding: 4px 5px;
    font-family: inherit;
    font-size: 0.68rem;
    font-weight: 700;
    text-align: center;
    border: 1.5px solid var(--border);
    border-radius: 14px;
    background: var(--white);
    color: var(--muted);
    cursor: pointer;
    transition: all 0.13s;
    white-space: normal;
    line-height: 1.2;
  }
  .o-pill.active {
    background: var(--purple);
    color: var(--lime);
    border-color: var(--purple);
  }
  .o-pill-all {
    border-color: var(--lime);
    color: var(--purple);
    font-weight: 900;
  }
  .o-pill-all.active {
    background: var(--lime);
    color: var(--purple);
    border-color: var(--lime);
  }

  /* ── Party pills (below chart) ── */
  .party-pills-row {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
    padding: 10px 12px;
    background: var(--white);
    border: none;
    border-radius: 0 0 6px 6px;
  }
  .p-pill {
    padding: 3px 11px;
    font-family: inherit;
    font-size: 0.75rem;
    font-weight: 700;
    border-radius: 14px;
    border: 1.5px solid currentColor;
    background: transparent;
    cursor: pointer;
    transition: all 0.12s;
    opacity: 0.38;
  }
  .p-pill.active { opacity: 1; }

  .status-row {
    text-align: left;
    padding: 5px 0 0;
    color: var(--muted);
    font-size: 0.68rem;
  }

  /* ── Events box ── */
  .events-box {
    background: var(--white);
    border: none;
    border-radius: 6px;
    padding: 10px 14px;
    margin-top: 6px;
  }
  .events-box-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--purple);
    text-transform: uppercase;
    margin-bottom: 8px;
  }
  .events-pills-wrap {
    display: flex;
    flex-wrap: wrap;
    gap: 5px;
  }
  .ev-pill {
    padding: 3px 10px;
    font-family: inherit;
    font-size: 0.73rem;
    font-weight: 600;
    border-radius: 12px;
    border: 1.5px solid var(--border);
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.13s;
    white-space: nowrap;
  }
  .ev-pill.active {
    border-color: var(--purple);
    background: var(--purple);
    color: var(--lime);
  }

  /* ── Admin ── */
  .admin-wrap {
    max-width: 540px;
    margin: 36px auto;
    padding: 28px 32px;
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 6px;
  }
  .admin-title {
    font-size: 1.1rem;
    font-weight: 900;
    color: var(--purple);
    border-bottom: 2px solid var(--lime);
    padding-bottom: 8px;
    margin-bottom: 18px;
  }
  label {
    font-size: 0.77rem;
    font-weight: 700;
    color: var(--purple);
    display: block;
    margin: 10px 0 4px;
  }
  input[type=text], input[type=password], textarea {
    width: 100%;
    padding: 7px 10px;
    border: 1px solid var(--border);
    border-radius: 4px;
    font-family: inherit;
    font-size: 0.85rem;
    direction: rtl;
    background: var(--bg);
    outline: none;
    transition: border 0.15s;
  }
  input:focus, textarea:focus { border-color: var(--purple); background: #fff; }
  textarea { height: 56px; resize: none; }
  .btn-primary {
    margin-top: 12px;
    width: 100%;
    padding: 9px;
    background: var(--coral);
    color: #fff;
    border: none;
    border-radius: 4px;
    font-family: inherit;
    font-size: 0.88rem;
    font-weight: 700;
    cursor: pointer;
    transition: background 0.13s;
  }
  .btn-primary:hover { background: #8B0000; }
  .event-admin-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    margin-top: 5px;
    background: var(--bg);
    border-radius: 4px;
    border-right: 3px solid var(--coral);
    font-size: 0.8rem;
  }
  .del-btn {
    background: none; border: none;
    color: #ccc; cursor: pointer; font-size: 1.1rem;
  }
  .del-btn:hover { color: var(--coral); }

  /* ── Telegram feed panel ── */
  .feed-panel {
    background: var(--white);
    border-radius: 6px;
    height: 100%;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }
  .feed-header {
    background: var(--purple);
    color: var(--lime);
    padding: 10px 14px;
    font-size: 0.78rem;
    font-weight: 900;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
  }
  .feed-dot {
    width: 7px; height: 7px;
    background: var(--coral);
    border-radius: 50%;
    animation: blink 1.8s ease-in-out infinite;
  }
  @keyframes blink {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.2; }
  }
  .feed-body {
    flex: 1;
    overflow-y: auto;
    padding: 0;
  }
  .feed-body::-webkit-scrollbar { width: 3px; }
  .feed-body::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  .feed-item {
    padding: 10px 14px;
    border-bottom: 1px solid #F5F0FB;
    cursor: default;
    transition: background 0.12s;
  }
  .feed-item:hover { background: #FAF6FF; }
  .feed-item-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 4px;
  }
  .feed-source {
    font-size: 0.68rem;
    font-weight: 700;
    color: var(--purple);
    background: #E8D5F5;
    padding: 1px 7px;
    border-radius: 8px;
  }
  .feed-time {
    font-size: 0.62rem;
    color: var(--muted);
    direction: ltr;
  }
  .feed-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: #1A1A1A;
    margin-bottom: 3px;
    line-height: 1.3;
  }
  .feed-content {
    font-size: 0.73rem;
    color: var(--muted);
    line-height: 1.4;
  }
  .feed-views {
    font-size: 0.62rem;
    color: #BBBBBB;
    margin-top: 4px;
  }
  .feed-type-poll .feed-title { color: var(--purple); }
  .feed-type-alert .feed-title { color: var(--coral); }

  /* ── Date range strip ── */
  .date-range-strip {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    padding: 8px 14px;
    background: var(--white);
    border: none;
    border-bottom: 1.5px solid var(--border);
    margin-bottom: 0;
  }
  .dr-label { font-size: 0.7rem; color: var(--muted); font-weight: 700; margin-left: 6px; }
  .dr-btn {
    padding: 2px 10px;
    font-family: inherit;
    font-size: 0.7rem;
    font-weight: 700;
    border: 1.5px solid var(--border);
    border-radius: 10px;
    background: transparent;
    color: var(--muted);
    cursor: pointer;
    transition: all 0.12s;
  }
  .dr-btn.active { background: var(--purple); color: var(--lime); border-color: var(--purple); }

  /* ── Blocs bar ── */
  .blocs-section {
    background: var(--white);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
    margin-top: 10px;
  }
  .blocs-title {
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--purple);
    text-transform: uppercase;
    margin-bottom: 10px;
  }
  .blocs-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-top: 8px;
    font-size: 0.72rem;
  }
  .bloc-legend-item {
    display: flex;
    align-items: center;
    gap: 5px;
  }
  .bloc-dot {
    width: 10px; height: 10px; border-radius: 2px; flex-shrink: 0;
  }
</style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""


# ── Layouts ───────────────────────────────────────────────────────────────────
def public_layout():
    return html.Div([
        dcc.Interval(id="interval", interval=300_000, n_intervals=0),  # 5 min — don't reset view constantly
        dcc.Store(id="chart-type", data="trend"),
        dcc.Store(id="selected-parties", data=DEFAULT_PARTIES),
        dcc.Store(id="selected-outlets", data=[]),
        dcc.Store(id="selected-events", data=[]),
        dcc.Store(id="date-range", data="all"),
        dcc.Store(id="view-mode", data="parties"),
        dcc.Store(id="selected-blocs", data=[b["name"] for b in BLOCS]),

        html.Header([
            html.Img(src="/assets/rose.png", className="header-rose"),
            html.Img(src="/assets/logo-white.png", className="header-logo-white",
                     style={"display": "block"}),
            html.Div(id="header-status", className="header-status"),
        ], className="site-header"),

        html.Div([
            dbc.Row([
                # FAR RIGHT: Telegram feed
                dbc.Col(
                    html.Div([
                        html.Div([
                            html.Div(className="feed-dot"),
                            html.Span("רוזה ניוז • עדכונים"),
                        ], className="feed-header"),
                        html.Div([
                            *[
                                html.Div([
                                    html.Div([
                                        html.Span(item["source"], className="feed-source"),
                                        html.Span(f'{item["date"]} {item["time"]}',
                                                  className="feed-time"),
                                    ], className="feed-item-meta"),
                                    html.Div(item["title"], className="feed-title"),
                                    html.Div(item["content"], className="feed-content")
                                    if item["content"] else None,
                                    html.Div(f'👁 {item["views"]}', className="feed-views"),
                                ], className=f'feed-item feed-type-{item["type"]}')
                                for item in MOCK_FEED
                            ],
                        ], className="feed-body"),
                    ], className="feed-panel"),
                    width=3,
                ),

                # MIDDLE: chart + party pills
                dbc.Col([
                    # Date range strip — TOP, above chart
                    html.Div([
                        html.Span("תקופה:", className="dr-label"),
                        html.Button("שבועיים",  id="dr-2weeks", className="dr-btn",        n_clicks=0),
                        html.Button("חודש",     id="dr-month",  className="dr-btn",        n_clicks=0),
                        html.Button("3 חודשים", id="dr-3month", className="dr-btn",        n_clicks=0),
                        html.Button("חצי שנה",  id="dr-6month", className="dr-btn",        n_clicks=0),
                        html.Button("שנה",      id="dr-year",   className="dr-btn",        n_clicks=0),
                        html.Button("הכל",      id="dr-all",    className="dr-btn active", n_clicks=0),
                    ], className="date-range-strip"),

                    html.Div([
                        # מגמות/ממוצע — top LEFT
                        html.Div([
                            html.Button("מגמות", id="btn-trend",
                                        className="ct-btn active", n_clicks=0),
                            html.Button("ממוצע", id="btn-bar",
                                        className="ct-btn", n_clicks=0),
                        ], className="ct-overlay-left"),
                        # מפלגות/גושים — top RIGHT
                        html.Div([
                            html.Button("מפלגות", id="btn-parties",
                                        className="ct-btn active", n_clicks=0),
                            html.Button("גושים", id="btn-blocs",
                                        className="ct-btn", n_clicks=0),
                        ], className="ct-overlay-right"),
                        dcc.Graph(id="main-chart",
                                  config={"displayModeBar": False},
                                  style={"height": "490px"}),
                    ], className="chart-wrapper"),

                    html.Div(id="party-pills-container", className="party-pills-row"),
                    html.Div(id="status-row", className="status-row"),
                    html.Div(id="events-box-container"),
                ], width=7),

                # FAR LEFT: outlet pills
                dbc.Col(
                    html.Div(id="outlet-pills-container", className="outlet-col"),
                    width=2,
                ),
            ]),
        ], className="main"),
    ])


def admin_layout():
    return html.Div([
        dcc.Store(id="admin-auth", data=False, storage_type="session"),

        html.Header([
            html.Img(src="/assets/rose.png", className="header-rose"),
            html.Span("ניהול אירועים", className="header-title"),
        ], className="site-header"),

        html.Div(
            html.Div([
                html.Div("בק אופיס — אירועים תקשורתיים", className="admin-title"),

                # Password gate
                html.Div(id="admin-gate", children=[
                    html.Label("סיסמה"),
                    dcc.Input(id="admin-password", type="password",
                              placeholder="הכנס סיסמה"),
                    html.Button("כניסה", id="admin-login-btn",
                                className="btn-primary", n_clicks=0),
                    html.Div(id="admin-login-error",
                             style={"color": "#D93025", "fontSize": "0.8rem",
                                    "marginTop": "8px"}),
                ]),

                # Event management panel (hidden until auth)
                html.Div(id="admin-panel", style={"display": "none"}, children=[
                    html.Label("תאריך"),
                    dcc.DatePickerSingle(id="admin-event-date",
                                         display_format="DD/MM/YYYY"),
                    html.Label("כותרת"),
                    dcc.Input(id="admin-event-title", type="text",
                              placeholder="למשל: חתימת הסכם לבנון"),
                    html.Label("קטגוריה"),
                    dcc.Dropdown(
                        id="admin-event-category",
                        options=[{"label": k, "value": k} for k in EVENT_COLORS],
                        value="פוליטי",
                        clearable=False,
                        style={"fontSize": "0.85rem"},
                    ),
                    html.Label("תיאור (אופציונלי)"),
                    dcc.Textarea(id="admin-event-desc", placeholder="אופציונלי"),
                    html.Button("הוסף אירוע", id="admin-add-btn",
                                className="btn-primary", n_clicks=0),
                    html.Div(id="admin-events-list", style={"marginTop": "14px"}),
                ]),
            ], className="admin-wrap"),
            style={"padding": "0 28px"},
        ),
    ])


app.layout = html.Div([
    dcc.Location(id="url"),
    dcc.Store(id="site-auth-store", data={"authenticated": False}),
    html.Div(id="page-content"),
])


# ── Routing & Auth ────────────────────────────────────────────────────────────
@app.callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
    Input("site-auth-store", "data"),
)
def render_page(pathname, auth_data):
    is_auth = auth_data.get("authenticated", False) if auth_data else False
    if pathname == "/admin":
        return admin_layout()
    if not is_auth:
        return login_modal()
    return public_layout()


def login_modal():
    """Full-screen login modal"""
    return html.Div([
        html.Div([
            html.Div([
                html.Img(src="/assets/rose.png", style={"height": "48px", "marginBottom": "16px"}),
                html.H1("רוזה ניוז — בחירות 2026", style={"fontSize": "1.25rem", "fontWeight": "900", "color": "#3D1040", "marginBottom": "6px"}),
                html.P("אנא הזן את הסיסמה כדי להמשיך", style={"color": "#888", "marginBottom": "28px"}),
                dcc.Input(
                    id="site-password-input",
                    type="password",
                    placeholder="סיסמה",
                    style={
                        "width": "100%",
                        "padding": "10px 14px",
                        "border": "1.5px solid #E0D8E8",
                        "borderRadius": "4px",
                        "direction": "ltr",
                        "textAlign": "center",
                        "fontSize": "0.95rem",
                        "marginBottom": "14px",
                        "boxSizing": "border-box",
                    },
                    autoFocus=True,
                ),
                html.Button(
                    "כניסה",
                    id="site-login-btn",
                    n_clicks=0,
                    style={
                        "width": "100%",
                        "padding": "11px",
                        "background": "#D93025",
                        "color": "white",
                        "border": "none",
                        "borderRadius": "4px",
                        "fontSize": "1rem",
                        "fontWeight": "700",
                        "cursor": "pointer",
                    },
                ),
                html.Div(
                    id="site-login-error",
                    style={"color": "#D93025", "fontSize": "0.82rem", "marginTop": "10px"},
                ),
            ], style={
                "background": "white",
                "borderRadius": "8px",
                "padding": "40px 48px",
                "width": "360px",
                "textAlign": "center",
                "boxShadow": "0 4px 32px rgba(61,16,64,.12)",
            }),
        ], style={
            "display": "flex",
            "alignItems": "center",
            "justifyContent": "center",
            "minHeight": "100vh",
            "background": "#E8D5F5",
            "direction": "rtl",
        }),
    ], style={"fontFamily": "'Heebo', Arial, sans-serif"})


@app.callback(
    Output("site-auth-store", "data"),
    Output("site-login-error", "children"),
    Input("site-login-btn", "n_clicks"),
    State("site-password-input", "value"),
    State("site-auth-store", "data"),
    prevent_initial_call=True,
)
def site_login(n_clicks, password, auth_data):
    if password == SITE_PASSWORD:
        return {"authenticated": True}, ""
    return {"authenticated": False}, "סיסמה שגויה — נסה שוב"


# ── Chart type toggle ──────────────────────────────────────────────────────────
@app.callback(
    Output("chart-type", "data"),
    Output("btn-trend", "className"),
    Output("btn-bar", "className"),
    Input("btn-trend", "n_clicks"),
    Input("btn-bar", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_chart_type(_, __):
    ctx = callback_context
    btn = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "btn-trend"
    if btn == "btn-trend":
        return "trend", "ct-btn active", "ct-btn"
    return "bar", "ct-btn", "ct-btn active"


# ── View mode toggle (parties / blocs) ────────────────────────────────────────
@app.callback(
    Output("view-mode", "data"),
    Output("btn-parties", "className"),
    Output("btn-blocs", "className"),
    Input("btn-parties", "n_clicks"),
    Input("btn-blocs", "n_clicks"),
    prevent_initial_call=True,
)
def toggle_view_mode(_, __):
    ctx = callback_context
    btn = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "btn-parties"
    if btn == "btn-parties":
        return "parties", "ct-btn active", "ct-btn"
    return "blocs", "ct-btn", "ct-btn active"


@app.callback(
    Output("selected-blocs", "data"),
    Input({"type": "bloc-pill", "bloc": ALL}, "n_clicks"),
    State("selected-blocs", "data"),
    prevent_initial_call=True,
)
def toggle_bloc(_, selected):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    bloc_name = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["bloc"]
    selected = list(selected or [])
    if bloc_name in selected:
        selected.remove(bloc_name)
    else:
        selected.append(bloc_name)
    return selected


# ── Outlet pills ───────────────────────────────────────────────────────────────
@app.callback(
    Output("outlet-pills-container", "children"),
    Input("interval", "n_intervals"),
    Input("selected-outlets", "data"),
)
def render_outlet_pills(_, selected):
    selected = selected or []
    outlets = get_outlets()
    all_active = len(selected) == 0

    pills = [html.Button(
        "הכל",
        id={"type": "outlet-pill", "outlet": "__all__"},
        className=f"o-pill o-pill-all {'active' if all_active else ''}",
        n_clicks=0,
    )]
    for o in outlets:
        pills.append(html.Button(
            o,
            id={"type": "outlet-pill", "outlet": o},
            className=f"o-pill {'active' if o in selected else ''}",
            n_clicks=0,
        ))
    return pills


@app.callback(
    Output("selected-outlets", "data"),
    Input({"type": "outlet-pill", "outlet": ALL}, "n_clicks"),
    State("selected-outlets", "data"),
    prevent_initial_call=True,
)
def toggle_outlet(_, selected):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    outlet = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["outlet"]
    selected = list(selected or [])
    if outlet == "__all__":
        return []
    if outlet in selected:
        selected.remove(outlet)
    else:
        selected.append(outlet)
    return selected


# ── Party / Bloc pills ────────────────────────────────────────────────────────
@app.callback(
    Output("party-pills-container", "children"),
    Input("selected-parties", "data"),
    Input("view-mode", "data"),
    Input("selected-blocs", "data"),
    Input("chart-type", "data"),
    Input("date-range", "data"),
    Input("selected-outlets", "data"),
)
def render_bottom_pills(sel_parties, view_mode, sel_blocs, chart_type, date_range, outlets):
    if view_mode == "blocs":
        sel_blocs = sel_blocs or [b["name"] for b in BLOCS]
        pills = []
        for bloc in BLOCS:
            active = bloc["name"] in sel_blocs
            color = bloc["color"]
            party_names = ", ".join(PARTY_HE.get(p, p) for p in bloc["parties"] if p in PARTY_HE)
            pills.append(html.Button(
                [html.Span(bloc["name"]),
                 html.Span(party_names,
                           style={"display": "block", "fontSize": "0.6rem",
                                  "fontWeight": "400", "opacity": "0.85",
                                  "lineHeight": "1.2", "marginTop": "2px"})],
                id={"type": "bloc-pill", "bloc": bloc["name"]},
                className=f"p-pill {'active' if active else ''}",
                n_clicks=0,
                style={
                    "color": "white" if active else color,
                    "backgroundColor": color if active else "transparent",
                    "borderColor": color,
                    "textAlign": "right",
                    "paddingBlock": "5px",
                },
            ))
        return pills

    # Party mode (default)
    sel_parties = sel_parties or []

    # Compute trend % for "bar" (ממוצע) mode
    trend_map = {}
    if chart_type == "bar":
        try:
            df_all = load_polls(outlets or None)
            df_all["date"] = pd.to_datetime(df_all["date"])
            df_ranged = apply_date_range(df_all, date_range)
            if not df_ranged.empty and len(df_ranged) >= 2:
                df_ranged = df_ranged.sort_values("date")
                mid = df_ranged["date"].iloc[len(df_ranged) // 2]
                first_half = df_ranged[df_ranged["date"] <= mid]
                second_half = df_ranged[df_ranged["date"] > mid]
                for key in PARTY_HE:
                    if key in df_ranged.columns:
                        v1 = first_half[key].dropna().mean()
                        v2 = second_half[key].dropna().mean()
                        if pd.notna(v1) and pd.notna(v2) and v1 > 0:
                            trend_map[key] = round(((v2 - v1) / v1) * 100, 1)
        except Exception:
            pass

    pills = []
    for key, name in PARTY_HE.items():
        color = PARTY_COLORS.get(key, "#888")
        active = key in sel_parties

        label_parts = [html.Span(name)]
        if chart_type == "bar" and key in trend_map:
            pct = trend_map[key]
            arrow = "▲" if pct > 0 else "▼"
            arrow_color = "#2E7D32" if pct > 0 else "#D93025"
            label_parts.append(html.Span(
                [html.Span(arrow, style={"color": arrow_color, "fontSize": "0.65rem"}),
                 html.Span(f" {abs(pct)}%", style={"color": "#555"})],
                style={"display": "block", "fontSize": "0.62rem",
                       "fontWeight": "400", "marginTop": "2px", "lineHeight": "1"},
            ))

        pills.append(html.Button(
            label_parts,
            id={"type": "party-pill", "party": key},
            className=f"p-pill {'active' if active else ''}",
            n_clicks=0,
            style={
                "color": "white" if active else color,
                "backgroundColor": color if active else "transparent",
                "borderColor": color,
                "paddingBlock": "4px" if chart_type == "bar" and key in trend_map else "",
            },
        ))
    return pills


@app.callback(
    Output("selected-parties", "data"),
    Input({"type": "party-pill", "party": ALL}, "n_clicks"),
    State("selected-parties", "data"),
    prevent_initial_call=True,
)
def toggle_party(_, selected):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    party = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["party"]
    selected = list(selected or [])
    if party in selected:
        selected.remove(party)
    else:
        selected.append(party)
    return selected


# ── Date range ────────────────────────────────────────────────────────────────
DR_BTNS = ["dr-2weeks", "dr-month", "dr-3month", "dr-6month", "dr-year", "dr-all"]
DR_VALS = {"dr-2weeks": "2weeks", "dr-month": "month", "dr-3month": "3month",
           "dr-6month": "6month", "dr-year": "year", "dr-all": "all"}
DR_DAYS = {"2weeks": 14, "month": 30, "3month": 90, "6month": 182, "year": 365, "all": 99999}
DR_LABELS = {"2weeks": "שבועיים", "month": "חודש אחרון", "3month": "3 חודשים",
             "6month": "חצי שנה", "year": "שנה", "all": "כל הסקרים"}


@app.callback(
    Output("date-range",  "data"),
    Output("dr-2weeks",   "className"),
    Output("dr-month",    "className"),
    Output("dr-3month",   "className"),
    Output("dr-6month",   "className"),
    Output("dr-year",     "className"),
    Output("dr-all",      "className"),
    [Input(b, "n_clicks") for b in DR_BTNS],
    prevent_initial_call=True,
)
def set_date_range(*_):
    ctx = callback_context
    btn = ctx.triggered[0]["prop_id"].split(".")[0] if ctx.triggered else "dr-all"
    val = DR_VALS.get(btn, "all")
    classes = ["dr-btn active" if b == btn else "dr-btn" for b in DR_BTNS]
    return (val, *classes)


def apply_date_range(df, date_range):
    if date_range == "all" or df.empty:
        return df
    import datetime
    days = DR_DAYS.get(date_range, 99999)
    cutoff = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    return df[df["date"] >= cutoff]


# ── Main chart ────────────────────────────────────────────────────────────────
@app.callback(
    Output("main-chart", "figure"),
    Output("header-status", "children"),
    Input("interval", "n_intervals"),
    Input("selected-outlets", "data"),
    Input("chart-type", "data"),
    Input("selected-parties", "data"),
    Input("selected-events", "data"),
    Input("date-range", "data"),
    Input("view-mode", "data"),
    Input("selected-blocs", "data"),
)
def update_chart(_, outlets, chart_type, parties, selected_event_ids,
                 date_range, view_mode, sel_blocs):
    df = load_polls(outlets or None)
    all_events = load_events()
    sel_ids = set(selected_event_ids or [])
    all_sel_events = all_events[all_events["id"].isin(sel_ids)] if not all_events.empty else all_events

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            annotations=[dict(text="טוען נתונים...", showarrow=False, font_size=18)],
            paper_bgcolor="#fff", plot_bgcolor="#fff",
        )
        return fig, ""

    status = f"עדכון: {df['fetched_at'].max()[:16]}  |  {len(df)} סקרים"
    df_ranged = apply_date_range(df, date_range)

    # Show markers only for short periods (≤ 3 months)
    show_markers = date_range in ("2weeks", "month", "3month")

    # Filter events to only those within the chart's date range
    events_df = all_sel_events
    if not events_df.empty and not df_ranged.empty:
        lo = df_ranged["date"].min()
        hi = df_ranged["date"].max()
        events_df = events_df[(events_df["date"] >= lo) & (events_df["date"] <= hi)]

    if view_mode == "blocs":
        sel_blocs = sel_blocs or [b["name"] for b in BLOCS]
        fig = build_trend_blocs(df_ranged, events_df, sel_blocs, show_markers) if chart_type == "trend" \
            else build_bar_blocs(df_ranged, sel_blocs)
    else:
        fig = build_trend(df_ranged, events_df, parties or [], show_markers) if chart_type == "trend" \
            else build_bar(df_ranged, parties or [])
    return fig, status


def _merge_beyahad(df):
    """Keep beyahad only where it actually appears — do NOT fill from yesh_atid."""
    return df.copy()


def _add_event_vlines(fig, events_df):
    for _, ev in events_df.iterrows():
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#666")
        ev_date = pd.to_datetime(ev["date"])
        fig.add_shape(type="line", x0=ev_date, x1=ev_date, y0=0, y1=1,
                      yref="paper", line=dict(color=color, width=1.5, dash="dash"))
        fig.add_annotation(x=ev_date, y=1, yref="paper", text=ev["title"],
                           showarrow=False, xanchor="left", yanchor="top",
                           font=dict(size=9, color=color, family="Heebo, Arial"),
                           bgcolor="rgba(255,255,255,0.75)", borderpad=2)


def build_trend(df, events_df, parties, show_markers=True):
    fig = go.Figure()
    df = _merge_beyahad(df)
    df["date"] = pd.to_datetime(df["date"])

    for party in parties:
        col = "_beyahad_merged" if party == "beyahad" else party
        if col not in df.columns and party not in df.columns:
            continue
        actual_col = col if col in df.columns else party

        # Group by date: mean mandates + collect outlet names
        grp = (df.sort_values("date")
               .groupby("date")
               .agg({actual_col: "mean",
                     "media_outlet": lambda x: " · ".join(sorted(x.dropna().unique()))})
               .rename(columns={actual_col: "mandates"})
               .dropna(subset=["mandates"])
               .reset_index())
        if grp.empty:
            continue
        color = PARTY_COLORS.get(party, "#888")
        label = PARTY_HE.get(party, party)
        fig.add_trace(go.Scatter(
            x=grp["date"],
            y=grp["mandates"],
            name=label,
            mode="lines+markers" if show_markers else "lines",
            line=dict(color=color, width=2.5, shape="spline", smoothing=0.85),
            marker=dict(size=7, opacity=0.9, color=color, line=dict(width=0)),
            opacity=1.0,
            customdata=grp[["media_outlet"]].values,
            hovertemplate=(
                f"<b>{label}</b>  %{{y:.1f}} מנדטים<br>"
                "%{x|%d/%m/%Y}<br>"
                "<span style='font-size:10px;color:#aaa'>%{customdata[0]}</span>"
                "<extra></extra>"
            ),
        ))

    _add_event_vlines(fig, events_df)
    _style_fig(fig)
    fig.update_layout(yaxis_title="מנדטים")
    return fig


def build_trend_blocs(df, events_df, selected_blocs, show_markers=True):
    fig = go.Figure()
    df = _merge_beyahad(df)
    df["date"] = pd.to_datetime(df["date"])
    for bloc in BLOCS:
        if bloc["name"] not in selected_blocs:
            continue
        cols = [p for p in bloc["parties"] if p in df.columns]
        if not cols:
            continue
        df["_bt"] = df[cols].sum(axis=1, min_count=1)
        grp = (df.sort_values("date")
               .groupby("date")
               .agg({"_bt": "mean",
                     "media_outlet": lambda x: " · ".join(sorted(x.dropna().unique()))})
               .dropna(subset=["_bt"])
               .reset_index())
        if grp.empty:
            continue
        fig.add_trace(go.Scatter(
            x=grp["date"], y=grp["_bt"],
            name=bloc["name"],
            mode="lines+markers" if show_markers else "lines",
            line=dict(color=bloc["color"], width=2.5, shape="spline", smoothing=0.85),
            marker=dict(size=7, opacity=0.9, color=bloc["color"], line=dict(width=0)),
            opacity=1.0,
            customdata=grp[["media_outlet"]].values,
            hovertemplate=(
                f"<b>{bloc['name']}</b>  %{{y:.1f}} מנדטים<br>"
                "%{x|%d/%m/%Y}<br>"
                "<span style='font-size:10px;color:#aaa'>%{customdata[0]}</span>"
                "<extra></extra>"
            ),
        ))
    _add_event_vlines(fig, events_df)
    _style_fig(fig)
    fig.update_layout(yaxis_title="מנדטים (גושים)")
    return fig


def build_bar_blocs(df, selected_blocs):
    df = _merge_beyahad(df)
    blocs_data = {}
    for bloc in BLOCS:
        if bloc["name"] not in selected_blocs:
            continue
        cols = [p for p in bloc["parties"] if p in df.columns]
        if not cols:
            continue
        blocs_data[bloc["name"]] = df[cols].sum(axis=1, min_count=1).mean()
    blocs_data = dict(sorted(blocs_data.items(), key=lambda x: -x[1]))
    color_map = {b["name"]: b["color"] for b in BLOCS}
    fig = go.Figure(go.Bar(
        x=list(blocs_data.keys()),
        y=list(blocs_data.values()),
        marker_color=[color_map.get(n, "#888") for n in blocs_data],
        marker_opacity=0.85,
        text=[f"{v:.1f}" for v in blocs_data.values()],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br><b>%{y:.1f} מנדטים</b><extra></extra>",
    ))
    _style_fig(fig)
    fig.update_layout(yaxis_title="מנדטים (ממוצע גושים)", bargap=0.35)
    return fig


def build_bar(df, parties):
    averages = {
        p: df[p].mean()
        for p in parties
        if p in df.columns and df[p].notna().any()
    }
    averages = dict(sorted(averages.items(), key=lambda x: -x[1]))
    fig = go.Figure(go.Bar(
        x=[PARTY_HE.get(p, p) for p in averages],
        y=list(averages.values()),
        marker_color=[PARTY_COLORS.get(p, "#888") for p in averages],
        marker_opacity=0.85,
        text=[f"{v:.1f}" for v in averages.values()],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br><b>%{y:.1f} מנדטים</b><extra></extra>",
    ))
    _style_fig(fig)
    fig.update_layout(yaxis_title="מנדטים (ממוצע)", bargap=0.35)
    return fig


def _style_fig(fig):
    fig.update_layout(
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        font=dict(family="Heebo, Arial", color="#1A1A1A", size=12),
        legend=dict(orientation="h", y=-0.18, x=0.5, xanchor="center",
                    font_size=11, bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=40, r=20, t=48, b=32),
        hovermode="closest",
        hoverdistance=40,
        hoverlabel=dict(bgcolor="#3D1040", font_color="#CCDD00",
                        font_family="Heebo, Arial", namelength=-1),
    )
    fig.update_xaxes(showgrid=False, zeroline=False,
                     tickfont=dict(size=10, color="#6B6B6B"))
    fig.update_yaxes(showgrid=True, gridcolor="#F0EBF5",
                     zeroline=False, tickfont=dict(size=10, color="#6B6B6B"))


# ── Events box ────────────────────────────────────────────────────────────────
@app.callback(
    Output("events-box-container", "style"),
    Input("chart-type", "data"),
)
def toggle_events_visibility(chart_type):
    if chart_type == "bar":
        return {"display": "none"}
    return {"display": "block"}


@app.callback(
    Output("events-box-container", "children"),
    Input("interval", "n_intervals"),
    Input("selected-events", "data"),
)
def render_events_box(_, selected_ids):
    events_df = load_events()
    sel = set(selected_ids or [])
    pills = []
    for _, ev in events_df.iterrows():
        eid = int(ev["id"])
        active = eid in sel
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#607D8B")
        style = {
            "borderColor": color,
            "color": "white" if active else color,
            "backgroundColor": color if active else "transparent",
        }
        pills.append(html.Button(
            ev["title"],
            id={"type": "ev-pill", "eid": eid},
            className=f"ev-pill {'active' if active else ''}",
            style=style,
            n_clicks=0,
        ))
    content = pills if pills else [
        html.Span("אין אירועים — הוסף דרך /admin",
                  style={"fontSize": "0.72rem", "color": "#bbb", "fontStyle": "italic"})
    ]
    return html.Div([
        html.Div("אירועים חדשותיים", className="events-box-title"),
        html.Div(content, className="events-pills-wrap"),
    ], className="events-box")


@app.callback(
    Output("selected-events", "data"),
    Input({"type": "ev-pill", "eid": ALL}, "n_clicks"),
    State("selected-events", "data"),
    prevent_initial_call=True,
)
def toggle_event(_, selected):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    eid = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["eid"]
    selected = list(selected or [])
    if eid in selected:
        selected.remove(eid)
    else:
        selected.append(eid)
    return selected


# ── Blocs bar ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("blocs-container", "children"),
    Input("interval", "n_intervals"),
    Input("selected-outlets", "data"),
    Input("date-range", "data"),
)
def update_blocs(_, outlets, date_range):
    df = load_polls(outlets or None)
    if df.empty:
        return html.Div()

    df = apply_date_range(df, date_range)
    if df.empty:
        return html.Div()

    # For beyahad: merge with yesh_atid historically
    if "beyahad" in df.columns and "yesh_atid" in df.columns:
        df = df.copy()
        df["beyahad"] = df["beyahad"].fillna(df["yesh_atid"])

    # Calculate average mandates per bloc
    bloc_totals = []
    for bloc in BLOCS:
        cols = [p for p in bloc["parties"] if p in df.columns]
        if not cols:
            bloc_totals.append(0)
            continue
        total = df[cols].sum(axis=1).mean()
        bloc_totals.append(round(total, 1))

    total_mandates = sum(bloc_totals)

    # Build horizontal stacked bar
    fig = go.Figure()
    for bloc, total in zip(BLOCS, bloc_totals):
        if total <= 0:
            continue
        fig.add_trace(go.Bar(
            x=[total],
            y=["כנסת"],
            name=bloc["name"],
            orientation="h",
            marker_color=bloc["color"],
            marker_opacity=0.88,
            text=f"{bloc['name']}<br>{total:.0f}",
            textposition="inside",
            insidetextanchor="middle",
            textfont=dict(color="white", size=10, family="Heebo, Arial"),
            hovertemplate=f"<b>{bloc['name']}</b><br>{total:.1f} מנדטים<extra></extra>",
        ))

    fig.update_layout(
        barmode="stack",
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FFFFFF",
        height=72,
        margin=dict(l=0, r=0, t=0, b=0),
        showlegend=False,
        font=dict(family="Heebo, Arial"),
        dragmode=False,
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False,
                   fixedrange=True, range=[0, 120]),
        yaxis=dict(showgrid=False, showticklabels=False, zeroline=False, fixedrange=True),
        hoverlabel=dict(bgcolor="#3D1040", font_color="#CCDD00", font_family="Heebo, Arial"),
    )

    # Legend — right to left order (ימין קיצוני first)
    legend_items = [
        html.Div([
            html.Div(className="bloc-dot", style={"backgroundColor": b["color"]}),
            html.Span(f"{b['name']} {t:.0f}"),
        ], className="bloc-legend-item")
        for b, t in zip(reversed(BLOCS), reversed(bloc_totals)) if t > 0
    ]

    return html.Div([
        html.Div("מפת הגושים", className="blocs-title"),
        dcc.Graph(figure=fig, config={"displayModeBar": False, "scrollZoom": False}),
        html.Div(legend_items, className="blocs-legend"),
    ], className="blocs-section")


# ── Hover highlight — dim others, highlight hovered ──────────────────────────
app.clientside_callback(
    """
    function(hoverData, figure) {
        if (!figure || !figure.data || figure.data.length === 0) {
            return window.dash_clientside.no_update;
        }
        var fig = JSON.parse(JSON.stringify(figure));
        var n = fig.data.length;

        if (hoverData && hoverData.points && hoverData.points.length > 0) {
            var cn = hoverData.points[0].curveNumber;
            for (var i = 0; i < n; i++) {
                if (fig.data[i].type === 'scatter') {
                    fig.data[i].opacity = (i === cn) ? 1.0 : 0.12;
                    if (i === cn) {
                        fig.data[i].line = Object.assign({}, fig.data[i].line, {width: 3.5});
                    } else {
                        fig.data[i].line = Object.assign({}, fig.data[i].line, {width: 2.5});
                    }
                }
            }
        } else {
            for (var i = 0; i < n; i++) {
                if (fig.data[i].type === 'scatter') {
                    fig.data[i].opacity = 1.0;
                    fig.data[i].line = Object.assign({}, fig.data[i].line, {width: 2.5});
                }
            }
        }
        return fig;
    }
    """,
    Output("main-chart", "figure", allow_duplicate=True),
    Input("main-chart", "hoverData"),
    State("main-chart", "figure"),
    prevent_initial_call=True,
)


# ── Admin auth ────────────────────────────────────────────────────────────────
@app.callback(
    Output("admin-auth", "data"),
    Output("admin-login-error", "children"),
    Output("admin-panel", "style"),
    Output("admin-gate", "style"),
    Output("admin-events-list", "children", allow_duplicate=True),
    Input("admin-login-btn", "n_clicks"),
    State("admin-password", "value"),
    State("admin-auth", "data"),
    prevent_initial_call=True,
)
def admin_login(_, password, already_auth):
    if already_auth or password == ADMIN_PASSWORD:
        return True, "", {"display": "block"}, {"display": "none"}, _render_event_list()
    return False, "סיסמה שגויה", {"display": "none"}, {"display": "block"}, no_update


# ── Admin events ──────────────────────────────────────────────────────────────
def _render_event_list():
    events_df = load_events()
    items = []
    for _, ev in events_df.iterrows():
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#666")
        items.append(html.Div([
            html.Div([
                html.Div(ev["title"], style={"fontWeight": "600"}),
                html.Div(
                    f"{str(ev['date'])[:10]}  ·  {ev.get('category', '')}",
                    style={"fontSize": "0.72rem", "color": "#888", "marginTop": "2px"},
                ),
            ]),
            html.Button("×",
                        id={"type": "admin-del", "index": int(ev["id"])},
                        className="del-btn"),
        ], className="event-admin-item",
           style={"borderRightColor": color}))
    return items


@app.callback(
    Output("admin-events-list", "children"),
    Output("admin-event-title", "value"),
    Output("admin-event-desc", "value"),
    Input("admin-add-btn", "n_clicks"),
    State("admin-auth", "data"),
    State("admin-event-date", "date"),
    State("admin-event-title", "value"),
    State("admin-event-desc", "value"),
    State("admin-event-category", "value"),
    prevent_initial_call=True,
)
def manage_admin_events(n_clicks, auth, date, title, desc, category):
    if not auth:
        return no_update, no_update, no_update
    if n_clicks and title and date:
        add_event_db(date, title, desc or "", category or "אחר")
        return _render_event_list(), "", ""
    return _render_event_list(), no_update, no_update


@app.callback(
    Output("admin-events-list", "children", allow_duplicate=True),
    Input({"type": "admin-del", "index": ALL}, "n_clicks"),
    State("admin-auth", "data"),
    prevent_initial_call=True,
)
def delete_admin_event(n_clicks_list, auth):
    if not auth:
        return no_update
    ctx = callback_context
    if not ctx.triggered or not any(n for n in (n_clicks_list or []) if n):
        return no_update
    event_id = json.loads(ctx.triggered[0]["prop_id"].split(".")[0])["index"]
    delete_event_db(event_id)
    return _render_event_list()


if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050)
