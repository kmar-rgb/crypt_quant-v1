from __future__ import annotations

import pandas as pd

from .config import MOVING_AVERAGES


def add_moving_averages(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("date").copy()
    for window in MOVING_AVERAGES:
        result[f"ma_{window}"] = result["close"].rolling(window).mean()
    result["volume_ma_20"] = result["volume"].rolling(20).mean()
    result["volume_ma_50"] = result["volume"].rolling(50).mean()
    result["high_52w"] = result["high"].rolling(252).max()
    result["low_52w"] = result["low"].rolling(252).min()
    return result


def add_relative_strength(frame: pd.DataFrame, benchmark: pd.DataFrame) -> pd.DataFrame:
    result = frame.sort_values("date").copy()
    benchmark = benchmark[["date", "close"]].rename(columns={"close": "benchmark_close"})
    merged = result.merge(benchmark, on="date", how="left")
    merged["benchmark_close"] = merged["benchmark_close"].ffill()
    merged["rs_line"] = merged["close"] / merged["benchmark_close"]
    merged["rs_ma_20"] = merged["rs_line"].rolling(20).mean()
    merged["rs_ma_50"] = merged["rs_line"].rolling(50).mean()
    merged["rs_20d_change"] = merged["rs_line"].pct_change(20) * 100
    merged["rs_50d_change"] = merged["rs_line"].pct_change(50) * 100
    return merged


def to_weekly(frame: pd.DataFrame) -> pd.DataFrame:
    weekly = frame.sort_values("date").set_index("date").resample("W-FRI").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    weekly = weekly.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return add_moving_averages(weekly)
