from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

import pandas as pd


OHLCV_COLUMNS = ["date", "open", "high", "low", "close", "volume"]


class MarketDataProvider(ABC):
    @abstractmethod
    def fetch_daily(
        self,
        ticker: str,
        start: date | str | None = None,
        end: date | str | None = None,
    ) -> pd.DataFrame:
        """Return daily OHLCV rows with columns in OHLCV_COLUMNS."""


class YahooFinanceProvider(MarketDataProvider):
    def fetch_daily(
        self,
        ticker: str,
        start: date | str | None = None,
        end: date | str | None = None,
    ) -> pd.DataFrame:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed. Install requirements or use CsvProvider."
            ) from exc

        raw = yf.download(
            ticker,
            start=start,
            end=end,
            auto_adjust=False,
            progress=False,
            group_by="column",
        )
        if raw.empty:
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        raw = raw.reset_index()
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = [col[0] for col in raw.columns]

        frame = raw.rename(
            columns={
                "Date": "date",
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        return normalize_ohlcv(frame)


class CsvProvider(MarketDataProvider):
    def __init__(self, folder: str | Path):
        self.folder = Path(folder)

    def fetch_daily(
        self,
        ticker: str,
        start: date | str | None = None,
        end: date | str | None = None,
    ) -> pd.DataFrame:
        path = self.folder / f"{ticker}.csv"
        if not path.exists():
            return pd.DataFrame(columns=OHLCV_COLUMNS)

        frame = pd.read_csv(path)
        frame = normalize_ohlcv(frame)
        if start is not None:
            frame = frame[frame["date"] >= pd.to_datetime(start)]
        if end is not None:
            frame = frame[frame["date"] <= pd.to_datetime(end)]
        return frame.reset_index(drop=True)


def normalize_ohlcv(frame: pd.DataFrame) -> pd.DataFrame:
    lower_map = {column: str(column).strip().lower() for column in frame.columns}
    frame = frame.rename(columns=lower_map)
    missing = set(OHLCV_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"Missing OHLCV columns: {sorted(missing)}")

    result = frame[OHLCV_COLUMNS].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.tz_localize(None)
    for column in ["open", "high", "low", "close", "volume"]:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    result = result.dropna(subset=["date", "open", "high", "low", "close"])
    result["volume"] = result["volume"].fillna(0).astype(float)
    return result.sort_values("date").drop_duplicates("date").reset_index(drop=True)
