from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd

from .config import DB_PATH, ensure_data_dir
from .models import Alert, Symbol


SCHEMA = """
CREATE TABLE IF NOT EXISTS symbols (
    ticker TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    sector TEXT NOT NULL,
    name TEXT
);

CREATE TABLE IF NOT EXISTS prices_daily (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume REAL NOT NULL,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_time TEXT NOT NULL,
    market TEXT NOT NULL,
    benchmark TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scan_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    market TEXT NOT NULL,
    sector TEXT NOT NULL,
    score REAL NOT NULL,
    stage TEXT NOT NULL,
    stage_confidence REAL NOT NULL,
    cup_handle_status TEXT NOT NULL,
    pivot REAL,
    distance_to_pivot_pct REAL,
    volume_ratio REAL,
    rs_50d_change REAL,
    base_depth_pct REAL,
    classification TEXT,
    market_condition_score REAL,
    risk_reward_score REAL,
    suggested_stop_loss REAL,
    risk_reward_estimate REAL,
    current_price REAL,
    notes TEXT,
    FOREIGN KEY(scan_id) REFERENCES scan_runs(id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    scan_date TEXT NOT NULL,
    alert_type TEXT NOT NULL,
    message TEXT NOT NULL,
    priority INTEGER NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS watchlist_notes (
    ticker TEXT PRIMARY KEY,
    note TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchlist (
    ticker TEXT PRIMARY KEY,
    date_added TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS score_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scan_id INTEGER NOT NULL,
    ticker TEXT NOT NULL,
    scan_time TEXT NOT NULL,
    score REAL NOT NULL,
    classification TEXT,
    stage TEXT,
    market_condition_score REAL
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_time TEXT NOT NULL,
    name TEXT NOT NULL,
    parameters TEXT NOT NULL,
    summary TEXT NOT NULL
);
"""


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    ensure_data_dir()
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(db_path: Path = DB_PATH) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)
        _migrate_scan_candidates(connection)


def _migrate_scan_candidates(connection: sqlite3.Connection) -> None:
    existing = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(scan_candidates)").fetchall()
    }
    migrations = {
        "classification": "TEXT",
        "market_condition_score": "REAL",
        "risk_reward_score": "REAL",
        "suggested_stop_loss": "REAL",
        "risk_reward_estimate": "REAL",
        "current_price": "REAL",
    }
    for column, column_type in migrations.items():
        if column not in existing:
            connection.execute(f"ALTER TABLE scan_candidates ADD COLUMN {column} {column_type}")


def upsert_symbols(symbols: Iterable[Symbol], db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO symbols (ticker, market, sector, name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                market=excluded.market,
                sector=excluded.sector,
                name=excluded.name
            """,
            [(item.ticker, item.market, item.sector, item.name) for item in symbols],
        )


def save_prices(ticker: str, frame: pd.DataFrame, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    rows = [
        (
            ticker,
            row.date.strftime("%Y-%m-%d"),
            float(row.open),
            float(row.high),
            float(row.low),
            float(row.close),
            float(row.volume),
        )
        for row in frame.itertuples(index=False)
    ]
    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO prices_daily (ticker, date, open, high, low, close, volume)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker, date) DO UPDATE SET
                open=excluded.open,
                high=excluded.high,
                low=excluded.low,
                close=excluded.close,
                volume=excluded.volume
            """,
            rows,
        )


def load_prices(ticker: str, db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        frame = pd.read_sql_query(
            "SELECT date, open, high, low, close, volume FROM prices_daily WHERE ticker = ? ORDER BY date",
            connection,
            params=(ticker,),
        )
    if not frame.empty:
        frame["date"] = pd.to_datetime(frame["date"])
    return frame


def create_scan_run(market: str, benchmark: str, db_path: Path = DB_PATH) -> int:
    init_db(db_path)
    with connect(db_path) as connection:
        cursor = connection.execute(
            "INSERT INTO scan_runs (scan_time, market, benchmark) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(timespec="seconds"), market, benchmark),
        )
        return int(cursor.lastrowid)


def save_candidates(scan_id: int, candidates: list[dict], db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    if not candidates:
        return
    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO scan_candidates (
                scan_id, ticker, market, sector, score, stage, stage_confidence,
                cup_handle_status, pivot, distance_to_pivot_pct, volume_ratio,
                rs_50d_change, base_depth_pct, classification, market_condition_score,
                risk_reward_score, suggested_stop_loss, risk_reward_estimate, current_price, notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    row["ticker"],
                    row["market"],
                    row["sector"],
                    row["score"],
                    row["stage"],
                    row["stage_confidence"],
                    row["cup_handle_status"],
                    row.get("pivot"),
                    row.get("distance_to_pivot_pct"),
                    row.get("volume_ratio"),
                    row.get("rs_50d_change"),
                    row.get("base_depth_pct"),
                    row.get("classification"),
                    row.get("market_condition_score"),
                    row.get("risk_reward_score"),
                    row.get("suggested_stop_loss"),
                    row.get("risk_reward_estimate"),
                    row.get("current_price") or row.get("last_close"),
                    row.get("notes", ""),
                )
                for row in candidates
            ],
        )
        scan_time = connection.execute("SELECT scan_time FROM scan_runs WHERE id = ?", (scan_id,)).fetchone()
        timestamp = scan_time["scan_time"] if scan_time else datetime.utcnow().isoformat(timespec="seconds")
        connection.executemany(
            """
            INSERT INTO score_history (scan_id, ticker, scan_time, score, classification, stage, market_condition_score)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    scan_id,
                    row["ticker"],
                    timestamp,
                    row["score"],
                    row.get("classification"),
                    row.get("stage"),
                    row.get("market_condition_score"),
                )
                for row in candidates
            ],
        )


def save_alerts(scan_id: int, alerts: list[Alert], db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    if not alerts:
        return
    with connect(db_path) as connection:
        connection.executemany(
            """
            INSERT INTO alerts (scan_id, ticker, scan_date, alert_type, message, priority)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (scan_id, alert.ticker, alert.scan_date.isoformat(), alert.alert_type, alert.message, alert.priority)
                for alert in alerts
            ],
        )


def load_latest_candidates(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        scan = connection.execute("SELECT id FROM scan_runs ORDER BY id DESC LIMIT 1").fetchone()
        if scan is None:
            return pd.DataFrame()
        return pd.read_sql_query(
            "SELECT * FROM scan_candidates WHERE scan_id = ? ORDER BY score DESC",
            connection,
            params=(scan["id"],),
        )


def load_symbols_table(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        return pd.read_sql_query("SELECT ticker, market, sector, name FROM symbols ORDER BY ticker", connection)


def add_to_watchlist(ticker: str, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlist (ticker, date_added, active)
            VALUES (?, datetime('now'), 1)
            ON CONFLICT(ticker) DO UPDATE SET active = 1
            """,
            (ticker.upper(),),
        )


def load_watchlist(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT
                w.ticker,
                w.date_added,
                COALESCE(c.classification, '') AS classification,
                COALESCE(c.score, 0) AS score,
                c.current_price,
                c.pivot,
                c.distance_to_pivot_pct,
                n.note,
                n.updated_at
            FROM watchlist w
            LEFT JOIN (
                SELECT sc.*
                FROM scan_candidates sc
                JOIN (SELECT MAX(scan_id) AS scan_id FROM scan_candidates) latest
                    ON latest.scan_id = sc.scan_id
            ) c ON c.ticker = w.ticker
            LEFT JOIN watchlist_notes n ON n.ticker = w.ticker
            WHERE w.active = 1
            ORDER BY w.date_added DESC
            """,
            connection,
        )


def save_note(ticker: str, note: str, db_path: Path = DB_PATH) -> None:
    init_db(db_path)
    with connect(db_path) as connection:
        connection.execute(
            """
            INSERT INTO watchlist_notes (ticker, note, updated_at)
            VALUES (?, ?, datetime('now'))
            ON CONFLICT(ticker) DO UPDATE SET note=excluded.note, updated_at=excluded.updated_at
            """,
            (ticker.upper(), note),
        )


def load_notes(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        return pd.read_sql_query("SELECT ticker, note, updated_at FROM watchlist_notes ORDER BY ticker", connection)


def load_alerts(limit: int = 100, db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT ticker, scan_date, alert_type, message, priority, acknowledged
            FROM alerts
            ORDER BY id DESC
            LIMIT ?
            """,
            connection,
            params=(limit,),
        )


def load_score_history(ticker: str | None = None, db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        if ticker:
            return pd.read_sql_query(
                """
                SELECT scan_time, ticker, score, classification, stage, market_condition_score
                FROM score_history
                WHERE ticker = ?
                ORDER BY scan_time
                """,
                connection,
                params=(ticker.upper(),),
            )
        return pd.read_sql_query(
            """
            SELECT scan_time, ticker, score, classification, stage, market_condition_score
            FROM score_history
            ORDER BY scan_time DESC
            """,
            connection,
        )


def load_scan_log(db_path: Path = DB_PATH) -> pd.DataFrame:
    init_db(db_path)
    with connect(db_path) as connection:
        return pd.read_sql_query(
            """
            SELECT r.id, r.scan_time, r.market, r.benchmark, COUNT(c.id) AS candidates
            FROM scan_runs r
            LEFT JOIN scan_candidates c ON c.scan_id = r.id
            GROUP BY r.id
            ORDER BY r.id DESC
            """,
            connection,
        )
