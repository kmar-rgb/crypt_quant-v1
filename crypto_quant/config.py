from __future__ import annotations

import os
import tomllib
from pathlib import Path

from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "config" / "crypto_settings.toml"
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_SQLITE_PATH = DATA_DIR / "crypto_quant.sqlite"


class ScanSettings(BaseModel):
    frequency: str = "daily"
    max_coins: int = Field(default=500, ge=1)
    default_currency: str = "USD"
    display_currencies: list[str] = Field(default_factory=lambda: ["USD", "AUD"])
    timezone: str = "Australia/Sydney"


class DataSettings(BaseModel):
    min_history_days: int = Field(default=180, ge=1)
    cache_ttl_seconds: int = Field(default=300, ge=0)
    request_timeout_seconds: int = Field(default=20, ge=1)
    max_retries: int = Field(default=3, ge=0)


class FilterSettings(BaseModel):
    minimum_market_cap: float = Field(default=100_000_000, ge=0)
    minimum_24h_volume: float = Field(default=5_000_000, ge=0)
    minimum_volume_to_market_cap: float = Field(default=0.005, ge=0)
    minimum_active_markets: int = Field(default=5, ge=0)
    exclude_stablecoins: bool = True
    exclude_wrapped_tokens: bool = True
    exclude_leveraged_tokens: bool = True
    exclude_missing_data: bool = True
    maximum_daily_volatility_pct: float = Field(default=25.0, ge=0)


class ScoringSettings(BaseModel):
    buy_threshold: float = Field(default=4.0, ge=0, le=5)
    watch_threshold: float = Field(default=3.0, ge=0, le=5)
    minimum_risk_reward: float = Field(default=2.0, ge=0)
    max_extension_from_50d_pct: float = Field(default=15.0, ge=0)
    max_extension_from_200d_pct: float = Field(default=60.0, ge=0)
    stage_trend_weight: float = Field(default=1.0, ge=0)
    breakout_structure_weight: float = Field(default=1.0, ge=0)
    volume_liquidity_weight: float = Field(default=1.0, ge=0)
    momentum_relative_strength_weight: float = Field(default=1.0, ge=0)
    risk_entry_quality_weight: float = Field(default=1.0, ge=0)


class StageSettings(BaseModel):
    ma_short: int = 50
    ma_mid: int = 150
    ma_long: int = 200
    base_lookback_days: int = 150
    maximum_stage1_base_depth_pct: float = 35.0
    early_stage2_max_extension_from_pivot_pct: float = 10.0


class PatternSettings(BaseModel):
    cup_min_days: int = 35
    cup_max_days: int = 325
    cup_min_depth_pct: float = 12.0
    cup_max_depth_pct: float = 40.0
    handle_min_days: int = 5
    handle_max_days: int = 30
    handle_max_depth_pct: float = 15.0
    breakout_volume_ratio: float = 1.4


class AiSettings(BaseModel):
    provider: str = "mock"
    model: str = "mock-json"
    timeout_seconds: int = 45
    cache_responses: bool = True


class AlertSettings(BaseModel):
    enabled: bool = True
    dedupe_window_hours: int = 24


class AppSettings(BaseModel):
    scan: ScanSettings = Field(default_factory=ScanSettings)
    data: DataSettings = Field(default_factory=DataSettings)
    filters: FilterSettings = Field(default_factory=FilterSettings)
    scoring: ScoringSettings = Field(default_factory=ScoringSettings)
    stage: StageSettings = Field(default_factory=StageSettings)
    pattern: PatternSettings = Field(default_factory=PatternSettings)
    ai: AiSettings = Field(default_factory=AiSettings)
    alerts: AlertSettings = Field(default_factory=AlertSettings)


class RuntimeSettings(BaseModel):
    app_env: str = "local"
    database_url: str
    coinmarketcap_api_key: str | None = None
    ai_provider: str = "mock"
    ai_api_key: str | None = None
    app_secret_key: str | None = None


def ensure_data_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def load_app_settings(path: Path = CONFIG_PATH) -> AppSettings:
    if not path.exists():
        return AppSettings()
    with path.open("rb") as handle:
        raw = tomllib.load(handle)
    return AppSettings(**raw)


def load_runtime_settings() -> RuntimeSettings:
    ensure_data_dir()
    return RuntimeSettings(
        app_env=os.getenv("APP_ENV", "local"),
        database_url=os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"),
        coinmarketcap_api_key=os.getenv("COINMARKETCAP_API_KEY") or None,
        ai_provider=os.getenv("AI_PROVIDER", "mock"),
        ai_api_key=os.getenv("AI_API_KEY") or None,
        app_secret_key=os.getenv("APP_SECRET_KEY") or None,
    )


def public_settings(settings: AppSettings) -> dict:
    return {
        "scan": settings.scan.model_dump(),
        "filters": settings.filters.model_dump(),
        "scoring": settings.scoring.model_dump(),
        "stage": settings.stage.model_dump(),
        "pattern": settings.pattern.model_dump(),
        "alerts": settings.alerts.model_dump(),
        "ai_provider": settings.ai.provider,
    }
