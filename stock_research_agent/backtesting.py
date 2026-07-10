from __future__ import annotations

import numpy as np
import pandas as pd

from .criteria_engine import evaluate_stock_criteria
from .indicators import add_moving_averages


def backtest_breakout_follow_through(
    daily: pd.DataFrame,
    pivot_lookback: int = 60,
    hold_days: int = 20,
    volume_ratio: float = 1.4,
) -> pd.DataFrame:
    frame = add_moving_averages(daily).reset_index(drop=True)
    trades: list[dict] = []

    for index in range(pivot_lookback, len(frame) - hold_days - 1):
        prior = frame.iloc[index - pivot_lookback : index]
        current = frame.iloc[index]
        pivot = float(prior["high"].max())
        average_volume = float(current.get("volume_ma_50", 0) or 0)
        has_volume = average_volume > 0 and float(current["volume"]) / average_volume >= volume_ratio
        trend_ok = current["close"] > current.get("ma_50", float("inf")) > current.get("ma_150", float("inf"))

        if float(current["close"]) > pivot and has_volume and trend_ok:
            entry = float(frame.iloc[index + 1]["open"])
            exit_price = float(frame.iloc[index + hold_days]["close"])
            trades.append(
                {
                    "signal_date": current["date"],
                    "entry_date": frame.iloc[index + 1]["date"],
                    "exit_date": frame.iloc[index + hold_days]["date"],
                    "pivot": pivot,
                    "entry": entry,
                    "exit": exit_price,
                    "return_pct": (exit_price - entry) / entry * 100,
                }
            )

    return pd.DataFrame(trades)


def summarize_trades(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {"trades": 0, "win_rate": 0, "average_return_pct": 0, "total_return_pct": 0}

    wins = trades[trades["return_pct"] > 0]
    return {
        "trades": int(len(trades)),
        "win_rate": round(len(wins) / len(trades) * 100, 1),
        "average_return_pct": round(float(trades["return_pct"].mean()), 2),
        "total_return_pct": round(float(trades["return_pct"].sum()), 2),
    }


def backtest_cup_handle_breakouts(
    daily: pd.DataFrame,
    benchmark_daily: pd.DataFrame | None = None,
    *,
    min_score: float = 70,
    hold_days: int = 20,
    stop_loss_pct: float = 8.0,
    breakout_volume_ratio: float = 1.4,
) -> pd.DataFrame:
    frame = add_moving_averages(daily).reset_index(drop=True)
    benchmark = add_moving_averages(benchmark_daily).reset_index(drop=True) if benchmark_daily is not None else None
    trades: list[dict] = []
    next_available_index = 150

    for index in range(150, len(frame) - hold_days - 1):
        if index < next_available_index:
            continue

        history = frame.iloc[: index + 1].copy()
        benchmark_history = benchmark.iloc[: index + 1].copy() if benchmark is not None and len(benchmark) > index else None
        result = evaluate_stock_criteria(history, benchmark_history, breakout_volume_ratio=breakout_volume_ratio)
        if result.breakout_status != "Confirmed breakout" or result.scores.total < min_score:
            continue

        entry_index = index + 1
        exit_index = min(index + hold_days, len(frame) - 1)
        entry = float(frame.iloc[entry_index]["open"])
        stop = entry * (1 - stop_loss_pct / 100)
        trade_slice = frame.iloc[entry_index : exit_index + 1]
        stopped = bool((trade_slice["low"] <= stop).any())
        if stopped:
            stop_row = trade_slice[trade_slice["low"] <= stop].iloc[0]
            exit_date = stop_row["date"]
            exit_price = stop
            actual_hold = int(trade_slice.index.get_loc(stop_row.name) + 1)
        else:
            exit_date = frame.iloc[exit_index]["date"]
            exit_price = float(frame.iloc[exit_index]["close"])
            actual_hold = hold_days

        return_pct = (exit_price - entry) / entry * 100
        failed_breakout = result.pivot is not None and bool((trade_slice["close"] < result.pivot).any())
        trades.append(
            {
                "signal_date": frame.iloc[index]["date"],
                "entry_date": frame.iloc[entry_index]["date"],
                "exit_date": exit_date,
                "entry": entry,
                "exit": exit_price,
                "return_pct": return_pct,
                "holding_days": actual_hold,
                "score": result.scores.total,
                "score_range": _score_range(result.scores.total),
                "market_condition_score": result.scores.market_condition,
                "market_condition": _market_condition_bucket(result.scores.market_condition),
                "failed_breakout": failed_breakout,
                "stopped": stopped,
                "pivot": result.pivot,
                "classification": result.classification,
            }
        )
        next_available_index = exit_index + 1

    return pd.DataFrame(trades)


def summarize_cup_handle_backtest(trades: pd.DataFrame) -> dict:
    if trades.empty:
        return {
            "trades": 0,
            "win_rate": 0,
            "average_gain": 0,
            "average_loss": 0,
            "maximum_drawdown": 0,
            "average_holding_period": 0,
            "failed_breakout_rate": 0,
            "performance_by_score_range": pd.DataFrame(),
            "performance_by_market_condition": pd.DataFrame(),
        }

    winners = trades[trades["return_pct"] > 0]
    losers = trades[trades["return_pct"] <= 0]
    equity = (1 + trades["return_pct"] / 100).cumprod()
    drawdown = (equity / equity.cummax() - 1) * 100
    by_score = _group_performance(trades, "score_range")
    by_market = _group_performance(trades, "market_condition")

    return {
        "trades": int(len(trades)),
        "win_rate": round(len(winners) / len(trades) * 100, 1),
        "average_gain": round(float(winners["return_pct"].mean()), 2) if not winners.empty else 0,
        "average_loss": round(float(losers["return_pct"].mean()), 2) if not losers.empty else 0,
        "maximum_drawdown": round(float(drawdown.min()), 2),
        "average_holding_period": round(float(trades["holding_days"].mean()), 1),
        "failed_breakout_rate": round(float(trades["failed_breakout"].mean()) * 100, 1),
        "performance_by_score_range": by_score,
        "performance_by_market_condition": by_market,
    }


def _group_performance(trades: pd.DataFrame, column: str) -> pd.DataFrame:
    grouped = trades.groupby(column, dropna=False)
    return grouped.agg(
        trades=("return_pct", "count"),
        win_rate=("return_pct", lambda values: round(float((values > 0).mean()) * 100, 1)),
        average_return=("return_pct", lambda values: round(float(np.mean(values)), 2)),
        failed_breakout_rate=("failed_breakout", lambda values: round(float(np.mean(values)) * 100, 1)),
    ).reset_index()


def _score_range(score: float) -> str:
    if score >= 85:
        return "85-100"
    if score >= 70:
        return "70-84"
    if score >= 55:
        return "55-69"
    return "0-54"


def _market_condition_bucket(score: float) -> str:
    if score >= 8:
        return "Strong"
    if score >= 5:
        return "Neutral"
    return "Weak"
