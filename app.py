"""
Dash dashboard for Israeli election polls.
Runs scraper in background every 30 minutes.
"""

import sqlite3
import pandas as pd
import plotly.graph_objects as go
import dash
from dash import Dash, dcc, html, Input, Output, State, callback_context, no_update, ALL
import dash_bootstrap_components as dbc
from apscheduler.schedulers.background import BackgroundScheduler
from scraper import run_scrape, DB_PATH, init_db, PARTY_COLUMNS

# ── Hebrew party labels ───────────────────────────────────────────────────────
PARTY_HE = {
    "likud": "הליכוד",
    "yahadut_tora": "יהדות התורה",
    "shas": 'ש"ס',
    "kahol_lavan": "כחול לבן",
    "yesh_atid": "יש עתיד",
    "hadash_taal": 'חדש תע"ל',
    "israel_beiteinu": "ישראל ביתנו",
    "demokratim": "הדמוקרטים",
    "zionut_datit": "הציונות הדתית",
    "raam": 'רע"מ',
    "balad": 'בל"ד',
    "otzma_yehudit": "עוצמה יהודית",
    "beyahad": "ביחד (בנט ולפיד)",
    "yashar": "ישר!",
    "miluimnikim": "המילואימניקים",
    "reshima_meshutefet": "רשימה ערבית מאוחדת",
}

PARTY_COLORS = {
    "likud": "#1e3a8a",
    "yahadut_tora": "#1d4ed8",
    "shas": "#2563eb",
    "kahol_lavan": "#60a5fa",
    "yesh_atid": "#f97316",
    "hadash_taal": "#0d9488",
    "israel_beiteinu": "#0ea5e9",
    "demokratim": "#ec4899",
    "zionut_datit": "#dc2626",
    "raam": "#16a34a",
    "balad": "#15803d",
    "otzma_yehudit": "#b91c1c",
    "beyahad": "#9333ea",
    "yashar": "#c2410c",
    "miluimnikim": "#64748b",
    "reshima_meshutefet": "#166534",
}

EVENT_COLORS = {
    "ביטחוני": "#dc2626",
    "כלכלי": "#16a34a",
    "פוליטי": "#2563eb",
    "חברתי": "#f97316",
    "אחר": "#64748b",
}


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    return conn


def load_polls(outlets=None) -> pd.DataFrame:
    conn = get_conn()
    q = "SELECT * FROM polls WHERE date IS NOT NULL ORDER BY date"
    df = pd.read_sql_query(q, conn)
    conn.close()
    if outlets:
        df = df[df["media_outlet"].isin(outlets)]
    return df


def load_events() -> pd.DataFrame:
    conn = get_conn()
    df = pd.read_sql_query("SELECT * FROM events ORDER BY date", conn)
    conn.close()
    return df


def get_outlets() -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT DISTINCT media_outlet FROM polls WHERE media_outlet != '' ORDER BY media_outlet"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


def add_event(date, title, description, category):
    conn = get_conn()
    conn.execute(
        "INSERT INTO events (date, title, description, category) VALUES (?,?,?,?)",
        (date, title, description, category),
    )
    conn.commit()
    conn.close()


def delete_event(event_id):
    conn = get_conn()
    conn.execute("DELETE FROM events WHERE id=?", (event_id,))
    conn.commit()
    conn.close()


# ── Scheduler ─────────────────────────────────────────────────────────────────
scheduler = BackgroundScheduler()
scheduler.add_job(run_scrape, "interval", minutes=30, id="scrape")
scheduler.start()
run_scrape()  # fetch immediately on startup


# ── App ───────────────────────────────────────────────────────────────────────
app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    title="סקרי בחירות — עמוד הבחירות",
    suppress_callback_exceptions=True,
)
app.index_string = """<!DOCTYPE html>
<html dir="rtl" lang="he">
<head>
{%metas%}
<title>{%title%}</title>
{%favicon%}
{%css%}
<style>
  :root {
    --red: #d32f2f;
    --black: #111111;
    --gray: #f4f4f4;
    --border: #e0e0e0;
  }
  * { box-sizing: border-box; }
  body {
    font-family: "Noto Sans Hebrew", "Arial Hebrew", Arial, sans-serif;
    background: #fff;
    color: var(--black);
    direction: rtl;
    margin: 0;
  }
  .site-header {
    border-bottom: 3px solid var(--black);
    padding: 18px 32px 12px;
    display: flex;
    align-items: baseline;
    gap: 16px;
  }
  .site-header h1 {
    font-size: 2rem;
    font-weight: 900;
    letter-spacing: -0.5px;
    margin: 0;
  }
  .site-header .sub {
    font-size: 0.9rem;
    color: #555;
    border-right: 2px solid var(--red);
    padding-right: 10px;
  }
  .main { padding: 24px 32px; }
  .card {
    border: 1px solid var(--border);
    border-radius: 4px;
    padding: 20px;
    margin-bottom: 24px;
    background: #fff;
  }
  .card h3 {
    font-size: 1rem;
    font-weight: 700;
    border-bottom: 2px solid var(--black);
    padding-bottom: 8px;
    margin-bottom: 16px;
  }
  .red-label { color: var(--red); font-weight: 700; }
  label { font-size: 0.85rem; font-weight: 600; display: block; margin-bottom: 4px; }
  .Select-control, .dash-input input, input[type=text], input[type=date], textarea, select {
    border: 1px solid var(--border) !important;
    border-radius: 3px !important;
    font-family: inherit !important;
    direction: rtl;
  }
  .btn-red {
    background: var(--red);
    color: #fff;
    border: none;
    padding: 8px 20px;
    font-family: inherit;
    font-weight: 700;
    cursor: pointer;
    border-radius: 3px;
  }
  .btn-red:hover { background: #b71c1c; }
  .events-list { margin-top: 12px; }
  .event-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 6px 0;
    border-bottom: 1px solid var(--border);
    font-size: 0.85rem;
  }
  .event-date { color: #777; margin-left: 12px; }
  .delete-btn {
    background: none;
    border: none;
    color: #999;
    cursor: pointer;
    font-size: 1rem;
  }
  .delete-btn:hover { color: var(--red); }
  .status-bar {
    font-size: 0.75rem;
    color: #999;
    text-align: left;
    margin-top: -16px;
    margin-bottom: 8px;
  }
</style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>"""

app.layout = html.Div([
    # ── Header ────────────────────────────────────────────────────────────────
    html.Header([
        html.H1("מד הבחירות"),
        html.Span("ניתוח סקרים בזמן אמת", className="sub"),
    ], className="site-header"),

    html.Div([
        dcc.Interval(id="interval", interval=60_000, n_intervals=0),  # refresh every 60s
        html.Div(id="status-bar", className="status-bar"),

        dbc.Row([
            # ── Left column: controls ─────────────────────────────────────────
            dbc.Col([
                html.Div([
                    html.H3("סינון"),
                    html.Label("כלי תקשורת"),
                    dcc.Dropdown(
                        id="outlet-filter",
                        multi=True,
                        placeholder="כל כלי התקשורת",
                        style={"direction": "rtl"},
                    ),
                    html.Br(),
                    html.Label("סוג גרף"),
                    dcc.RadioItems(
                        id="chart-type",
                        options=[
                            {"label": " מגמות לאורך זמן", "value": "trend"},
                            {"label": " ממוצע (עמודות)", "value": "bar"},
                        ],
                        value="trend",
                        labelStyle={"display": "block", "marginBottom": "6px"},
                    ),
                    html.Br(),
                    html.Label("מפלגות להצגה"),
                    dcc.Checklist(
                        id="party-filter",
                        options=[{"label": f" {v}", "value": k} for k, v in PARTY_HE.items()],
                        value=["likud", "yesh_atid", "zionut_datit", "shas", "yahadut_tora",
                               "israel_beiteinu", "demokratim", "beyahad"],
                        labelStyle={"display": "block", "marginBottom": "4px", "fontSize": "0.82rem"},
                    ),
                ], className="card"),

                # ── Events panel ──────────────────────────────────────────────
                html.Div([
                    html.H3("אירועים תקשורתיים"),
                    html.Label("תאריך"),
                    dcc.DatePickerSingle(id="event-date", display_format="DD/MM/YYYY",
                                        style={"marginBottom": "8px"}),
                    html.Label("כותרת"),
                    dcc.Input(id="event-title", type="text", placeholder="למשל: חתימת הסכם לבנון",
                              style={"width": "100%", "marginBottom": "8px", "padding": "6px"}),
                    html.Label("קטגוריה"),
                    dcc.Dropdown(
                        id="event-category",
                        options=[{"label": k, "value": k} for k in EVENT_COLORS],
                        value="פוליטי",
                        clearable=False,
                        style={"marginBottom": "8px"},
                    ),
                    html.Label("תיאור (אופציונלי)"),
                    dcc.Textarea(id="event-desc", style={"width": "100%", "height": "60px",
                                                          "marginBottom": "8px", "padding": "6px"}),
                    html.Button("הוסף אירוע", id="add-event-btn", className="btn-red"),
                    html.Div(id="events-list", className="events-list"),
                ], className="card"),
            ], width=3),

            # ── Right column: charts ──────────────────────────────────────────
            dbc.Col([
                html.Div([
                    dcc.Graph(id="main-chart", config={"displayModeBar": False},
                              style={"height": "520px"}),
                ], className="card"),
            ], width=9),
        ]),
    ], className="main"),
])


# ── Callbacks ─────────────────────────────────────────────────────────────────
@app.callback(
    Output("outlet-filter", "options"),
    Input("interval", "n_intervals"),
)
def update_outlet_options(_):
    return [{"label": o, "value": o} for o in get_outlets()]


@app.callback(
    Output("main-chart", "figure"),
    Output("status-bar", "children"),
    Input("interval", "n_intervals"),
    Input("outlet-filter", "value"),
    Input("chart-type", "value"),
    Input("party-filter", "value"),
    Input("events-list", "children"),  # refresh when events change
)
def update_chart(_, outlets, chart_type, parties, _events):
    df = load_polls(outlets or None)
    events_df = load_events()

    if df.empty:
        fig = go.Figure()
        fig.update_layout(
            annotations=[dict(text="טוען נתונים...", showarrow=False, font_size=18)],
            paper_bgcolor="#fff", plot_bgcolor="#fff",
        )
        return fig, ""

    status = f"סה\"כ {len(df)} סקרים | עדכון אחרון: {df['fetched_at'].max()[:16]}"

    if chart_type == "trend":
        fig = build_trend(df, events_df, parties or [])
    else:
        fig = build_bar(df, parties or [])

    return fig, status


def build_trend(df, events_df, parties):
    fig = go.Figure()
    df["date"] = pd.to_datetime(df["date"])
    df_sorted = df.sort_values("date")

    for party in parties:
        if party not in df_sorted.columns:
            continue
        series = df_sorted.groupby("date")[party].mean().reset_index()
        fig.add_trace(go.Scatter(
            x=series["date"],
            y=series[party],
            name=PARTY_HE.get(party, party),
            mode="lines+markers",
            line=dict(color=PARTY_COLORS.get(party, "#666"), width=2),
            marker=dict(size=4),
        ))

    # Event lines
    for _, ev in events_df.iterrows():
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#666")
        fig.add_vline(
            x=ev["date"],
            line_dash="dash",
            line_color=color,
            line_width=1.5,
            annotation_text=ev["title"],
            annotation_position="top right",
            annotation_font_size=10,
            annotation_font_color=color,
        )

    _style_fig(fig, "מגמות מנדטים לאורך זמן")
    fig.update_layout(xaxis_title="תאריך", yaxis_title="מנדטים", legend_title="מפלגה")
    return fig


def build_bar(df, parties):
    averages = {p: df[p].mean() for p in parties if p in df.columns}
    averages = dict(sorted(averages.items(), key=lambda x: -x[1]))

    fig = go.Figure(go.Bar(
        x=[PARTY_HE.get(p, p) for p in averages],
        y=list(averages.values()),
        marker_color=[PARTY_COLORS.get(p, "#666") for p in averages],
        text=[f"{v:.1f}" for v in averages.values()],
        textposition="outside",
    ))
    _style_fig(fig, "ממוצע מנדטים")
    fig.update_layout(
        xaxis_title="מפלגה",
        yaxis_title="מנדטים (ממוצע)",
        bargap=0.3,
    )
    return fig


def _style_fig(fig, title):
    fig.update_layout(
        title=dict(text=title, font_size=16, font_family="Arial", x=1, xanchor="right"),
        paper_bgcolor="#fff",
        plot_bgcolor="#fff",
        font_family="Arial",
        legend=dict(orientation="h", y=-0.25),
        margin=dict(l=40, r=40, t=60, b=80),
    )
    fig.update_xaxes(showgrid=False, zeroline=False)
    fig.update_yaxes(showgrid=True, gridcolor="#f0f0f0", zeroline=False)


# ── Events CRUD ───────────────────────────────────────────────────────────────
@app.callback(
    Output("events-list", "children"),
    Output("event-title", "value"),
    Output("event-desc", "value"),
    Input("add-event-btn", "n_clicks"),
    Input("interval", "n_intervals"),
    State("event-date", "date"),
    State("event-title", "value"),
    State("event-desc", "value"),
    State("event-category", "value"),
    prevent_initial_call=True,
)
def manage_events(n_clicks, _, date, title, desc, category):
    ctx = callback_context
    trigger = ctx.triggered[0]["prop_id"] if ctx.triggered else ""

    if "add-event-btn" in trigger and title and date:
        add_event(date, title, desc or "", category or "אחר")

    events_df = load_events()
    items = []
    for _, ev in events_df.iterrows():
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#666")
        items.append(html.Div([
            html.Span([
                html.Span(ev["date"][:10], className="event-date"),
                html.Span(ev["title"]),
            ]),
            html.Button("×", id={"type": "del-event", "index": ev["id"]},
                        className="delete-btn"),
        ], className="event-item", style={"borderRightColor": color, "borderRightWidth": "3px",
                                           "borderRightStyle": "solid", "paddingRight": "8px"}))

    clear_title = "" if "add-event-btn" in trigger else no_update
    clear_desc = "" if "add-event-btn" in trigger else no_update
    return items, clear_title, clear_desc


@app.callback(
    Output("events-list", "children", allow_duplicate=True),
    Input({"type": "del-event", "index": ALL}, "n_clicks"),
    prevent_initial_call=True,
)
def delete_event_cb(n_clicks_list):
    ctx = callback_context
    if not ctx.triggered:
        return no_update
    prop = ctx.triggered[0]["prop_id"]
    event_id = eval(prop.split(".")[0])["index"]
    delete_event(event_id)
    events_df = load_events()
    items = []
    for _, ev in events_df.iterrows():
        color = EVENT_COLORS.get(ev.get("category", "אחר"), "#666")
        items.append(html.Div([
            html.Span([
                html.Span(ev["date"][:10], className="event-date"),
                html.Span(ev["title"]),
            ]),
            html.Button("×", id={"type": "del-event", "index": ev["id"]}, className="delete-btn"),
        ], className="event-item", style={"borderRightColor": color, "borderRightWidth": "3px",
                                           "borderRightStyle": "solid", "paddingRight": "8px"}))
    return items


if __name__ == "__main__":
    app.run(debug=True, port=8050)
