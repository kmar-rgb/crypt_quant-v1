from __future__ import annotations

import pandas as pd
import streamlit as st

from stock_research_agent.backtesting import backtest_cup_handle_breakouts, summarize_cup_handle_backtest
from stock_research_agent.config import DEFAULT_BENCHMARKS, ScanConfig, load_app_settings
from stock_research_agent.data_provider import CsvProvider, YahooFinanceProvider
from stock_research_agent.indicators import add_moving_averages, add_relative_strength, to_weekly
from stock_research_agent.sample_data import SAMPLE_DIR, SAMPLE_WATCHLIST, load_sample_scan
from stock_research_agent.scanner import scan_symbols
from stock_research_agent.storage import (
    add_to_watchlist,
    init_db,
    load_alerts,
    load_latest_candidates,
    load_notes,
    load_prices,
    load_scan_log,
    load_score_history,
    load_watchlist,
    save_note,
)
from stock_research_agent.watchlist import load_symbols

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
except ImportError:
    go = None
    make_subplots = None


st.set_page_config(page_title="Swing Setup Research", page_icon="ST", layout="wide")
init_db()
SETTINGS = load_app_settings()


def sidebar_controls() -> dict:
    st.sidebar.title("Swing Research")
    page = st.sidebar.radio(
        "Page",
        ["Market Overview", "Stock Screener", "Stock Detail", "Watchlist", "Backtesting", "Alerts"],
    )
    provider_name = st.sidebar.selectbox("Data source", ["Sample CSV", "CSV folder", "Yahoo Finance"])
    market = st.sidebar.selectbox("Market", list(SETTINGS.markets))
    benchmark = st.sidebar.text_input("Benchmark", DEFAULT_BENCHMARKS.get(market, SETTINGS.benchmark))
    watchlist_path = st.sidebar.text_input(
        "Watchlist CSV",
        str(SAMPLE_WATCHLIST if provider_name == "Sample CSV" else "data/watchlist.csv"),
    )
    csv_folder = st.sidebar.text_input("CSV data folder", str(SAMPLE_DIR if provider_name == "Sample CSV" else "data/raw"))
    min_score = st.sidebar.slider("Minimum score", 0, 100, SETTINGS.min_score)

    st.sidebar.divider()
    load_sample = st.sidebar.button("Load sample data")
    run_scan = st.sidebar.button("Run scan", type="primary")

    return {
        "page": page,
        "provider_name": provider_name,
        "market": market,
        "benchmark": benchmark,
        "watchlist_path": watchlist_path,
        "csv_folder": csv_folder,
        "min_score": min_score,
        "load_sample": load_sample,
        "run_scan": run_scan,
    }


def get_provider(settings: dict):
    if settings["provider_name"] in {"Sample CSV", "CSV folder"}:
        return CsvProvider(settings["csv_folder"])
    return YahooFinanceProvider()


def run_scan_from_sidebar(settings: dict) -> None:
    if settings["load_sample"]:
        with st.spinner("Creating sample data and running sample scan..."):
            candidates, alert_count = load_sample_scan()
        st.success(f"Sample scan complete: {len(candidates)} stocks, {alert_count} alerts.")

    if settings["run_scan"]:
        try:
            symbols = load_symbols(settings["watchlist_path"])
            provider = get_provider(settings)
            config = ScanConfig(
                market=settings["market"],
                benchmark=settings["benchmark"],
                near_pivot_pct=SETTINGS.near_pivot_pct,
                breakout_volume_ratio=SETTINGS.breakout_volume_ratio,
            )
            with st.spinner("Scanning watchlist..."):
                candidates, alerts = scan_symbols(symbols, provider, config)
            st.success(f"Scan complete: {len(candidates)} stocks, {len(alerts)} alerts.")
        except Exception as exc:
            st.error(str(exc))


def candidate_frame(min_score: int) -> pd.DataFrame:
    frame = load_latest_candidates()
    if frame.empty:
        return frame
    frame = frame.copy()
    defaults = {
        "classification": "",
        "market_condition_score": 0,
        "risk_reward_score": 0,
        "suggested_stop_loss": None,
        "risk_reward_estimate": None,
        "current_price": None,
    }
    for column, default in defaults.items():
        if column not in frame:
            frame[column] = default
    return frame[frame["score"] >= min_score].sort_values("score", ascending=False)


def market_overview(candidates: pd.DataFrame, benchmark: str) -> None:
    st.title("Market Overview")
    st.caption("Research and tracking only. No orders are placed from this dashboard.")

    benchmark_prices = add_moving_averages(load_prices(benchmark)) if benchmark else pd.DataFrame()
    index_trend = "No benchmark data"
    if not benchmark_prices.empty:
        last = benchmark_prices.iloc[-1]
        index_trend = "Uptrend" if last["close"] > last["ma_50"] > last["ma_200"] else "Mixed / Downtrend"

    above_50, above_200 = percent_above_mas(candidates)
    breakout_candidates = int((candidates["classification"] == "Breakout Candidate").sum()) if not candidates.empty else 0
    confirmed = int((candidates["classification"] == "Breakout Confirmed").sum()) if not candidates.empty else 0
    market_score = candidates["market_condition_score"].mean() if not candidates.empty else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Major index trend", index_trend)
    col2.metric("Above 50-day", f"{above_50:.0f}%")
    col3.metric("Above 200-day", f"{above_200:.0f}%")
    col4.metric("Breakout candidates", breakout_candidates)
    col5.metric("Confirmed breakouts", confirmed)

    st.metric("Market condition score", f"{market_score:.1f}/10")
    if not candidates.empty:
        st.subheader("Sector setup quality")
        st.bar_chart(candidates.groupby("sector")["score"].mean().sort_values(ascending=False))
        st.subheader("Latest scan log")
        st.dataframe(load_scan_log(), use_container_width=True, hide_index=True)


def stock_screener(candidates: pd.DataFrame) -> None:
    st.title("Stock Screener")
    if candidates.empty:
        empty_state()
        return

    markets = st.multiselect("Market", sorted(candidates["market"].dropna().unique()), default=sorted(candidates["market"].dropna().unique()))
    sectors = st.multiselect("Sector", sorted(candidates["sector"].dropna().unique()), default=sorted(candidates["sector"].dropna().unique()))
    stages = st.multiselect("Stage", sorted(candidates["stage"].dropna().unique()), default=sorted(candidates["stage"].dropna().unique()))
    classifications = st.multiselect(
        "Setup classification",
        sorted(candidates["classification"].dropna().unique()),
        default=sorted(candidates["classification"].dropna().unique()),
    )
    score_range = st.slider("Score", 0, 100, (int(candidates["score"].min()), 100))
    rs_min = st.slider("Minimum relative strength change", -50.0, 50.0, -50.0)
    volume_min = st.slider("Minimum volume ratio", 0.0, 3.0, 0.0)
    breakout_distance = st.slider("Breakout distance", -20.0, 20.0, (-10.0, 10.0))

    filtered = candidates[
        candidates["market"].isin(markets)
        & candidates["sector"].isin(sectors)
        & candidates["stage"].isin(stages)
        & candidates["classification"].isin(classifications)
        & candidates["score"].between(score_range[0], score_range[1])
        & candidates["rs_50d_change"].fillna(-999).ge(rs_min)
        & candidates["volume_ratio"].fillna(0).ge(volume_min)
        & candidates["distance_to_pivot_pct"].fillna(0).between(breakout_distance[0], breakout_distance[1])
    ]

    columns = [
        "ticker",
        "market",
        "sector",
        "classification",
        "score",
        "stage",
        "cup_handle_status",
        "current_price",
        "pivot",
        "distance_to_pivot_pct",
        "volume_ratio",
        "rs_50d_change",
        "risk_reward_estimate",
    ]
    st.dataframe(filtered[columns], use_container_width=True, hide_index=True)

    ticker = st.selectbox("Add to watchlist", filtered["ticker"].tolist() if not filtered.empty else [])
    if ticker and st.button("Save to watchlist"):
        add_to_watchlist(ticker)
        st.success(f"{ticker} added to watchlist.")


def stock_detail(candidates: pd.DataFrame, benchmark: str) -> None:
    st.title("Stock Detail")
    tickers = candidates["ticker"].tolist() if not candidates.empty else []
    ticker = st.selectbox("Ticker", tickers)
    if not ticker:
        empty_state()
        return

    row = candidates[candidates["ticker"] == ticker].iloc[0]
    daily = add_moving_averages(load_prices(ticker))
    benchmark_prices = load_prices(benchmark)
    if daily.empty:
        st.warning("No stored price data for this ticker.")
        return
    if not benchmark_prices.empty:
        daily = add_relative_strength(daily, benchmark_prices)
    weekly = to_weekly(daily)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Classification", row["classification"])
    col2.metric("Score", f"{row['score']:.1f}")
    col3.metric("Pivot", _fmt(row.get("pivot")))
    col4.metric("Stop", _fmt(row.get("suggested_stop_loss")))

    chart_price(daily.tail(260), f"{ticker} daily", row.get("pivot"), row.get("suggested_stop_loss"), show_rs=True)
    chart_price(weekly.tail(120), f"{ticker} weekly", row.get("pivot"), row.get("suggested_stop_loss"), show_rs=False)

    st.subheader("Setup notes")
    st.write(row.get("notes") or "No notes stored.")
    st.write(f"Risk/reward estimate: {_fmt(row.get('risk_reward_estimate'))}")

    note = st.text_area("Notes", value=current_note_for(ticker), height=120)
    if st.button("Save note"):
        save_note(ticker, note)
        st.success("Note saved.")


def watchlist_page() -> None:
    st.title("Watchlist")
    watchlist = load_watchlist()
    if watchlist.empty:
        st.info("No saved watchlist stocks yet.")
        return

    st.dataframe(watchlist, use_container_width=True, hide_index=True)
    ticker = st.selectbox("Score history", watchlist["ticker"].tolist())
    history = load_score_history(ticker)
    if not history.empty:
        st.line_chart(history.set_index("scan_time")["score"])
    alerts = load_alerts(200)
    watch_alerts = alerts[alerts["ticker"].isin(watchlist["ticker"])] if not alerts.empty else alerts
    if not watch_alerts.empty:
        st.subheader("Watchlist alerts")
        st.dataframe(watch_alerts, use_container_width=True, hide_index=True)


def backtesting_page(candidates: pd.DataFrame, benchmark: str) -> None:
    st.title("Backtesting")
    tickers = candidates["ticker"].tolist() if not candidates.empty else []
    ticker = st.selectbox("Ticker", tickers)
    min_score = st.slider("Minimum signal score", 50, 95, 70)
    hold_days = st.slider("Holding period", 5, 60, 20)
    stop_loss = st.slider("Stop loss percent", 3.0, 15.0, 8.0)

    if not ticker:
        empty_state()
        return
    if st.button("Run backtest", type="primary"):
        daily = load_prices(ticker)
        benchmark_prices = load_prices(benchmark)
        trades = backtest_cup_handle_breakouts(
            daily,
            benchmark_prices,
            min_score=min_score,
            hold_days=hold_days,
            stop_loss_pct=stop_loss,
        )
        summary = summarize_cup_handle_backtest(trades)
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        col1.metric("Trades", summary["trades"])
        col2.metric("Win rate", f"{summary['win_rate']:.1f}%")
        col3.metric("Average gain", f"{summary['average_gain']:.2f}%")
        col4.metric("Average loss", f"{summary['average_loss']:.2f}%")
        col5.metric("Max drawdown", f"{summary['maximum_drawdown']:.2f}%")
        col6.metric("Failed breakout rate", f"{summary['failed_breakout_rate']:.1f}%")
        st.metric("Average holding period", f"{summary['average_holding_period']:.1f} days")
        st.subheader("Trades")
        st.dataframe(trades, use_container_width=True, hide_index=True)
        st.subheader("Performance by score range")
        st.dataframe(summary["performance_by_score_range"], use_container_width=True, hide_index=True)
        st.subheader("Performance by market condition")
        st.dataframe(summary["performance_by_market_condition"], use_container_width=True, hide_index=True)


def alerts_page() -> None:
    st.title("Alerts")
    alerts = load_alerts(300)
    if alerts.empty:
        st.info("No alerts yet.")
        return
    alert_types = st.multiselect("Alert type", sorted(alerts["alert_type"].unique()), default=sorted(alerts["alert_type"].unique()))
    filtered = alerts[alerts["alert_type"].isin(alert_types)]
    st.dataframe(filtered, use_container_width=True, hide_index=True)


def chart_price(frame: pd.DataFrame, title: str, pivot: float | None, stop: float | None, show_rs: bool) -> None:
    if go is None or make_subplots is None:
        st.line_chart(frame.set_index("date")["close"])
        return

    rows = 3 if show_rs and "rs_line" in frame else 2
    heights = [0.62, 0.2, 0.18] if rows == 3 else [0.72, 0.28]
    fig = make_subplots(rows=rows, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=heights)
    fig.add_trace(
        go.Candlestick(
            x=frame["date"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="Price",
        ),
        row=1,
        col=1,
    )
    for window, color in [(10, "#7c3aed"), (20, "#0891b2"), (50, "#16a34a"), (150, "#d97706"), (200, "#dc2626")]:
        column = f"ma_{window}"
        if column in frame:
            fig.add_trace(go.Scatter(x=frame["date"], y=frame[column], mode="lines", name=column, line=dict(color=color)), row=1, col=1)
    if pivot:
        fig.add_hline(y=pivot, line_dash="dash", line_color="#2563eb", annotation_text="Pivot", row=1, col=1)
    if stop:
        fig.add_hline(y=stop, line_dash="dot", line_color="#dc2626", annotation_text="Stop", row=1, col=1)
    fig.add_trace(go.Bar(x=frame["date"], y=frame["volume"], name="Volume", marker_color="#94a3b8"), row=2, col=1)
    if rows == 3:
        fig.add_trace(go.Scatter(x=frame["date"], y=frame["rs_line"], mode="lines", name="Relative strength", line=dict(color="#0f766e")), row=3, col=1)
    fig.update_layout(title=title, height=720, margin=dict(l=20, r=20, t=40, b=20), xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)


def percent_above_mas(candidates: pd.DataFrame) -> tuple[float, float]:
    if candidates.empty:
        return 0, 0
    above_50 = 0
    above_200 = 0
    total = 0
    for ticker in candidates["ticker"]:
        prices = add_moving_averages(load_prices(ticker))
        if prices.empty:
            continue
        latest = prices.iloc[-1]
        total += 1
        above_50 += int(latest["close"] > latest["ma_50"])
        above_200 += int(latest["close"] > latest["ma_200"])
    if total == 0:
        return 0, 0
    return above_50 / total * 100, above_200 / total * 100


def current_note_for(ticker: str) -> str:
    notes = load_notes()
    if notes.empty:
        return ""
    match = notes[notes["ticker"] == ticker]
    return "" if match.empty else str(match.iloc[0]["note"])


def empty_state() -> None:
    st.info("Load sample data or run a scan from the sidebar to populate this page.")


def _fmt(value: object) -> str:
    try:
        if pd.isna(value):
            return "-"
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return "-"


settings = sidebar_controls()
run_scan_from_sidebar(settings)
candidates = candidate_frame(settings["min_score"])

if settings["page"] == "Market Overview":
    market_overview(candidates, settings["benchmark"])
elif settings["page"] == "Stock Screener":
    stock_screener(candidates)
elif settings["page"] == "Stock Detail":
    stock_detail(candidates, settings["benchmark"])
elif settings["page"] == "Watchlist":
    watchlist_page()
elif settings["page"] == "Backtesting":
    backtesting_page(candidates, settings["benchmark"])
elif settings["page"] == "Alerts":
    alerts_page()
