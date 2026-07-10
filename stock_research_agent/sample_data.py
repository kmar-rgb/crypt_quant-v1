from __future__ import annotations

from pathlib import Path

import pandas as pd

from .config import DATA_DIR
from .data_provider import CsvProvider
from .models import Symbol
from .scanner import scan_symbols
from .config import ScanConfig


SAMPLE_DIR = DATA_DIR / "sample"
SAMPLE_WATCHLIST = DATA_DIR / "sample_watchlist.csv"
SAMPLE_SYMBOLS = [
    Symbol("ALPHA", "US", "Technology", "Alpha Systems"),
    Symbol("BASE", "US", "Healthcare", "Base Medical"),
    Symbol("EXTEND", "US", "Consumer Discretionary", "Extend Retail"),
    Symbol("FAIL", "US", "Industrials", "Failover Works"),
    Symbol("WEAK", "US", "Financials", "Weak Bank"),
]


def create_sample_data(folder: Path = SAMPLE_DIR) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    frames = {
        "SPY": _frame_from_closes(_line(80, 120, 260), [1_000_000] * 260),
        "ALPHA": _breakout_frame(),
        "BASE": _base_frame(),
        "EXTEND": _extended_frame(),
        "FAIL": _failed_breakout_frame(),
        "WEAK": _weak_frame(),
    }
    for ticker, frame in frames.items():
        frame.to_csv(folder / f"{ticker}.csv", index=False)
    return folder


def load_sample_scan() -> tuple[pd.DataFrame, int]:
    folder = create_sample_data()
    provider = CsvProvider(folder)
    config = ScanConfig(market="US", benchmark="SPY")
    candidates, alerts = scan_symbols(SAMPLE_SYMBOLS, provider, config, persist=True)
    return candidates, len(alerts)


def _breakout_frame() -> pd.DataFrame:
    closes = (
        list(_line(45, 100, 80))
        + list(_line(100, 72, 45))
        + list(_line(72, 98, 75))
        + list(_line(97, 93, 10))
        + list(_line(93, 96, 49))
        + [102.2]
    )
    volumes = (
        [1_200_000] * 80
        + [950_000] * 30
        + [700_000] * 15
        + [1_000_000] * 75
        + [650_000] * 59
        + [1_850_000]
    )
    return _frame_from_closes(closes, volumes)


def _base_frame() -> pd.DataFrame:
    closes = list(_line(70, 88, 150)) + ([86, 85, 87, 86, 88, 87, 86, 87, 88, 86] * 11)
    volumes = [1_200_000] * 150 + [700_000] * 110
    return _frame_from_closes(closes, volumes)


def _extended_frame() -> pd.DataFrame:
    frame = _breakout_frame()
    frame.loc[frame.index[-1], ["open", "high", "low", "close", "volume"]] = [121, 123, 120, 122, 1_000_000]
    return frame


def _failed_breakout_frame() -> pd.DataFrame:
    frame = _breakout_frame()
    frame.loc[frame.index[-2], ["open", "high", "low", "close", "volume"]] = [101, 103, 100, 102.2, 1_850_000]
    frame.loc[frame.index[-1], ["open", "high", "low", "close", "volume"]] = [95, 96, 93, 94, 1_400_000]
    return frame


def _weak_frame() -> pd.DataFrame:
    return _frame_from_closes(_line(100, 55, 260), [1_000_000] * 260)


def _frame_from_closes(closes: list[float], volumes: list[float]) -> pd.DataFrame:
    dates = pd.bdate_range(end="2026-06-25", periods=len(closes))
    close = pd.Series(closes, dtype=float)
    return pd.DataFrame(
        {
            "date": dates,
            "open": close - 0.3,
            "high": close + 0.8,
            "low": close - 0.8,
            "close": close,
            "volume": volumes,
        }
    )


def _line(start: float, end: float, count: int) -> list[float]:
    if count == 1:
        return [end]
    step = (end - start) / (count - 1)
    return [start + step * index for index in range(count)]
