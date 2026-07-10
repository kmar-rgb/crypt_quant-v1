from __future__ import annotations

import json
import sqlite3
import sys
from html import escape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from stock_research_agent.config import DB_PATH, PROJECT_ROOT
from stock_research_agent.sample_data import load_sample_scan
from stock_research_agent.storage import init_db, load_alerts, load_latest_candidates, load_scan_log


OUTPUT_DIR = PROJECT_ROOT / "dashboard_site"
OUTPUT_FILE = OUTPUT_DIR / "index.html"


def main() -> None:
    init_db()
    candidates = load_latest_candidates()
    if candidates.empty:
        load_sample_scan()
        candidates = load_latest_candidates()

    alerts = load_alerts(200)
    scans = load_scan_log()
    watchlist = _load_watchlist()

    payload = {
        "candidates": candidates.fillna("").to_dict(orient="records"),
        "alerts": alerts.fillna("").to_dict(orient="records"),
        "scans": scans.fillna("").to_dict(orient="records"),
        "watchlist": watchlist,
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_FILE.write_text(render_html(payload), encoding="utf-8")
    print(OUTPUT_FILE)


def _load_watchlist() -> list[dict]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT ticker, date_added, active
            FROM watchlist
            WHERE active = 1
            ORDER BY date_added DESC
            """
        ).fetchall()
    return [dict(row) for row in rows]


def render_html(payload: dict) -> str:
    data = json.dumps(payload)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Swing Trading Research Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fb;
      --panel: #ffffff;
      --ink: #172033;
      --muted: #657086;
      --line: #d9dfeb;
      --blue: #1d4ed8;
      --green: #15803d;
      --red: #b91c1c;
      --amber: #b45309;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }}
    header {{
      position: sticky;
      top: 0;
      z-index: 2;
      background: rgba(247, 248, 251, 0.94);
      border-bottom: 1px solid var(--line);
      backdrop-filter: blur(12px);
    }}
    .wrap {{ max-width: 1320px; margin: 0 auto; padding: 18px 24px; }}
    h1 {{ margin: 0; font-size: 26px; letter-spacing: 0; }}
    h2 {{ margin: 28px 0 12px; font-size: 18px; }}
    p {{ color: var(--muted); }}
    nav {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }}
    nav a {{
      color: var(--ink);
      text-decoration: none;
      border: 1px solid var(--line);
      padding: 8px 11px;
      background: var(--panel);
      border-radius: 6px;
      font-size: 14px;
    }}
    .grid {{ display: grid; grid-template-columns: repeat(5, minmax(150px, 1fr)); gap: 12px; }}
    .metric, section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
    }}
    .metric span {{ display: block; color: var(--muted); font-size: 13px; }}
    .metric strong {{ display: block; margin-top: 8px; font-size: 24px; }}
    .toolbar {{ display: grid; grid-template-columns: repeat(6, minmax(130px, 1fr)); gap: 10px; margin: 12px 0; }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #fff;
      color: var(--ink);
      font-size: 14px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); cursor: pointer; user-select: none; font-weight: 650; }}
    tr:hover td {{ background: #f1f5fb; }}
    .pill {{ display: inline-block; padding: 4px 8px; border-radius: 999px; background: #e8eefc; color: var(--blue); font-weight: 650; }}
    .confirmed {{ background: #e8f7ee; color: var(--green); }}
    .failed {{ background: #fdecec; color: var(--red); }}
    .extended {{ background: #fff3db; color: var(--amber); }}
    .two {{ display: grid; grid-template-columns: 1.35fr 0.65fr; gap: 14px; }}
    .chart {{ height: 260px; border: 1px solid var(--line); border-radius: 8px; background: linear-gradient(#fff, #f8fafc); padding: 10px; }}
    .bar {{ height: 10px; background: #e2e8f0; border-radius: 999px; overflow: hidden; }}
    .bar i {{ display: block; height: 100%; background: var(--blue); }}
    @media (max-width: 980px) {{
      .grid, .toolbar, .two {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <header>
    <div class="wrap">
      <h1>Swing Trading Research Dashboard</h1>
      <p>Private local preview. Research and tracking only.</p>
      <nav>
        <a href="#overview">Market Overview</a>
        <a href="#screener">Stock Screener</a>
        <a href="#detail">Stock Detail</a>
        <a href="#watchlist">Watchlist</a>
        <a href="#backtesting">Backtesting</a>
        <a href="#alerts">Alerts</a>
      </nav>
    </div>
  </header>
  <main class="wrap">
    <section id="overview">
      <h2>Market Overview</h2>
      <div class="grid" id="metrics"></div>
    </section>

    <section id="screener">
      <h2>Stock Screener</h2>
      <div class="toolbar">
        <input id="search" placeholder="Search ticker">
        <select id="market"></select>
        <select id="sector"></select>
        <select id="stage"></select>
        <select id="classification"></select>
        <input id="minScore" type="number" min="0" max="100" value="0" placeholder="Min score">
      </div>
      <table id="candidateTable"></table>
    </section>

    <section id="detail">
      <h2>Stock Detail</h2>
      <div class="two">
        <div>
          <select id="detailTicker"></select>
          <div class="chart" id="scoreChart"></div>
        </div>
        <div id="detailPanel"></div>
      </div>
    </section>

    <section id="watchlist">
      <h2>Watchlist</h2>
      <table id="watchlistTable"></table>
    </section>

    <section id="backtesting">
      <h2>Backtesting Summary</h2>
      <p>This static preview reads scan state only. Run the Streamlit app for live parameterized backtests.</p>
      <div id="backtestPanel"></div>
    </section>

    <section id="alerts">
      <h2>Alerts</h2>
      <table id="alertsTable"></table>
    </section>
  </main>

  <script>
    const payload = {data};
    let sortKey = "score";
    let sortDir = -1;

    function asNumber(value) {{
      const n = Number(value);
      return Number.isFinite(n) ? n : 0;
    }}
    function uniq(rows, key) {{
      return ["All", ...Array.from(new Set(rows.map(row => row[key]).filter(Boolean))).sort()];
    }}
    function pill(text) {{
      const lower = String(text || "").toLowerCase();
      let cls = "pill";
      if (lower.includes("confirmed")) cls += " confirmed";
      if (lower.includes("failed")) cls += " failed";
      if (lower.includes("extended")) cls += " extended";
      return `<span class="${{cls}}">${{escapeHtml(text || "-")}}</span>`;
    }}
    function escapeHtml(value) {{
      return String(value).replace(/[&<>"']/g, char => ({{"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","'":"&#39;"}}[char]));
    }}
    function format(value, digits = 1) {{
      const n = Number(value);
      return Number.isFinite(n) ? n.toFixed(digits) : "-";
    }}
    function fillSelect(id, values) {{
      const el = document.getElementById(id);
      el.innerHTML = values.map(value => `<option>${{escapeHtml(value)}}</option>`).join("");
    }}
    function metric(label, value) {{
      return `<div class="metric"><span>${{label}}</span><strong>${{value}}</strong></div>`;
    }}
    function renderMetrics() {{
      const rows = payload.candidates;
      const total = rows.length || 1;
      const confirmed = rows.filter(row => row.classification === "Breakout Confirmed").length;
      const candidates = rows.filter(row => row.classification === "Breakout Candidate").length;
      const marketScore = rows.reduce((sum, row) => sum + asNumber(row.market_condition_score), 0) / total;
      const avgScore = rows.reduce((sum, row) => sum + asNumber(row.score), 0) / total;
      document.getElementById("metrics").innerHTML = [
        metric("Major index trend", marketScore >= 8 ? "Uptrend" : marketScore >= 5 ? "Mixed" : "Weak"),
        metric("Breakout candidates", candidates),
        metric("Confirmed breakouts", confirmed),
        metric("Market condition", `${{format(marketScore)}}/10`),
        metric("Average setup score", format(avgScore))
      ].join("");
    }}
    function currentRows() {{
      const search = document.getElementById("search").value.toLowerCase();
      const market = document.getElementById("market").value;
      const sector = document.getElementById("sector").value;
      const stage = document.getElementById("stage").value;
      const classification = document.getElementById("classification").value;
      const minScore = asNumber(document.getElementById("minScore").value);
      return payload.candidates.filter(row =>
        String(row.ticker).toLowerCase().includes(search) &&
        (market === "All" || row.market === market) &&
        (sector === "All" || row.sector === sector) &&
        (stage === "All" || row.stage === stage) &&
        (classification === "All" || row.classification === classification) &&
        asNumber(row.score) >= minScore
      ).sort((a, b) => {{
        const av = sortKey === "ticker" ? String(a[sortKey]) : asNumber(a[sortKey]);
        const bv = sortKey === "ticker" ? String(b[sortKey]) : asNumber(b[sortKey]);
        return av > bv ? sortDir : av < bv ? -sortDir : 0;
      }});
    }}
    function renderTable() {{
      const columns = [
        ["ticker", "Ticker"],
        ["classification", "Classification"],
        ["score", "Score"],
        ["stage", "Stage"],
        ["current_price", "Price"],
        ["pivot", "Pivot"],
        ["distance_to_pivot_pct", "Pivot distance"],
        ["volume_ratio", "Volume"],
        ["rs_50d_change", "RS 50d"]
      ];
      const rows = currentRows();
      document.getElementById("candidateTable").innerHTML = `
        <thead><tr>${{columns.map(([key, label]) => `<th data-key="${{key}}">${{label}}</th>`).join("")}}</tr></thead>
        <tbody>${{rows.map(row => `<tr>${{columns.map(([key]) => {{
          if (key === "classification") return `<td>${{pill(row[key])}}</td>`;
          if (["score","current_price","pivot","distance_to_pivot_pct","volume_ratio","rs_50d_change"].includes(key)) return `<td>${{format(row[key])}}</td>`;
          return `<td>${{escapeHtml(row[key] || "-")}}</td>`;
        }}).join("")}}</tr>`).join("")}}</tbody>
      `;
      document.querySelectorAll("#candidateTable th").forEach(th => {{
        th.onclick = () => {{
          const key = th.dataset.key;
          sortDir = sortKey === key ? -sortDir : -1;
          sortKey = key;
          renderTable();
        }};
      }});
    }}
    function renderDetail() {{
      const ticker = document.getElementById("detailTicker").value;
      const row = payload.candidates.find(item => item.ticker === ticker) || payload.candidates[0];
      if (!row) return;
      document.getElementById("detailPanel").innerHTML = `
        <div class="metric"><span>Classification</span><strong>${{pill(row.classification)}}</strong></div>
        <p><b>Stage:</b> ${{escapeHtml(row.stage || "-")}}</p>
        <p><b>Cup and handle:</b> ${{escapeHtml(row.cup_handle_status || "-")}}</p>
        <p><b>Pivot:</b> ${{format(row.pivot)}} | <b>Stop:</b> ${{format(row.suggested_stop_loss)}} | <b>R/R:</b> ${{format(row.risk_reward_estimate)}}</p>
        <p>${{escapeHtml(row.notes || "")}}</p>
      `;
      const score = Math.max(0, Math.min(100, asNumber(row.score)));
      document.getElementById("scoreChart").innerHTML = `
        <p><b>${{escapeHtml(row.ticker)}}</b> setup score</p>
        <div class="bar"><i style="width:${{score}}%"></i></div>
        <p>${{format(score)}} / 100</p>
        <p>Daily/weekly candlestick charts are available in the Streamlit app once dependencies are installed.</p>
      `;
    }}
    function renderSimpleTable(id, rows, columns) {{
      document.getElementById(id).innerHTML = `
        <thead><tr>${{columns.map(col => `<th>${{col[1]}}</th>`).join("")}}</tr></thead>
        <tbody>${{rows.map(row => `<tr>${{columns.map(col => `<td>${{escapeHtml(row[col[0]] ?? "-")}}</td>`).join("")}}</tr>`).join("")}}</tbody>
      `;
    }}
    function init() {{
      fillSelect("market", uniq(payload.candidates, "market"));
      fillSelect("sector", uniq(payload.candidates, "sector"));
      fillSelect("stage", uniq(payload.candidates, "stage"));
      fillSelect("classification", uniq(payload.candidates, "classification"));
      fillSelect("detailTicker", payload.candidates.map(row => row.ticker));
      ["search", "market", "sector", "stage", "classification", "minScore"].forEach(id => {{
        document.getElementById(id).addEventListener("input", renderTable);
      }});
      document.getElementById("detailTicker").addEventListener("input", renderDetail);
      renderMetrics();
      renderTable();
      renderDetail();
      renderSimpleTable("alertsTable", payload.alerts, [["ticker","Ticker"],["scan_date","Date"],["alert_type","Type"],["message","Message"],["priority","Priority"]]);
      renderSimpleTable("watchlistTable", payload.watchlist, [["ticker","Ticker"],["date_added","Date added"],["active","Active"]]);
      document.getElementById("backtestPanel").innerHTML = `<p>Latest scan rows: ${{payload.candidates.length}}. Historical scans stored: ${{payload.scans.length}}.</p>`;
    }}
    init();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
