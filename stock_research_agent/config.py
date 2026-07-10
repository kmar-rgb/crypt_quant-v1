from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "stock_research.sqlite"
SETTINGS_PATH = PROJECT_ROOT / "config" / "settings.toml"


MOVING_AVERAGES = (10, 20, 50, 150, 200)
DEFAULT_BENCHMARKS = {
    "US": "SPY",
    "NASDAQ": "QQQ",
    "AU": "VAS.AX",
    "ASX": "VAS.AX",
}


@dataclass(frozen=True)
class ScanConfig:
    market: str = "US"
    benchmark: str = "SPY"
    min_history_days: int = 260
    near_pivot_pct: float = 5.0
    breakout_volume_ratio: float = 1.4


@dataclass(frozen=True)
class AppSettings:
    markets: tuple[str, ...]
    tickers: tuple[str, ...]
    benchmark: str
    scan_frequency: str
    min_score: int
    near_pivot_pct: float
    breakout_volume_ratio: float
    max_extension_from_50d_pct: float


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_app_settings(path: Path = SETTINGS_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings(
            markets=("US", "NASDAQ", "ASX"),
            tickers=("AAPL", "MSFT", "NVDA", "AMZN", "META"),
            benchmark="SPY",
            scan_frequency="daily",
            min_score=50,
            near_pivot_pct=5.0,
            breakout_volume_ratio=1.4,
            max_extension_from_50d_pct=12.0,
        )

    with path.open("rb") as handle:
        raw = tomllib.load(handle)

    markets = tuple(raw.get("markets", {}).get("enabled", ["US", "NASDAQ", "ASX"]))
    tickers = tuple(raw.get("watchlist", {}).get("tickers", ["AAPL", "MSFT", "NVDA", "AMZN", "META"]))
    scoring = raw.get("scoring", {})
    return AppSettings(
        markets=markets,
        tickers=tickers,
        benchmark=raw.get("market", {}).get("benchmark", "SPY"),
        scan_frequency=raw.get("scan", {}).get("frequency", "daily"),
        min_score=int(scoring.get("min_score", 50)),
        near_pivot_pct=float(scoring.get("near_pivot_pct", 5.0)),
        breakout_volume_ratio=float(scoring.get("breakout_volume_ratio", 1.4)),
        max_extension_from_50d_pct=float(scoring.get("max_extension_from_50d_pct", 12.0)),
    )
