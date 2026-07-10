from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MarketStage(str, Enum):
    STAGE_1 = "Stage 1"
    EARLY_STAGE_2 = "Early Stage 2"
    CONFIRMED_STAGE_2 = "Confirmed Stage 2"
    EXTENDED_STAGE_2 = "Extended Stage 2"
    STAGE_3 = "Stage 3"
    STAGE_4 = "Stage 4"
    INSUFFICIENT_DATA = "Insufficient data"


class Rating(str, Enum):
    BUY = "BUY"
    WATCH = "WATCH"
    AVOID = "AVOID"


class DataQualityStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    MISSING_HISTORY = "missing_history"
    MISSING_QUOTE = "missing_quote"
    INSUFFICIENT_DATA = "insufficient_data"


class CryptoAsset(BaseModel):
    cmc_id: int = Field(gt=0)
    symbol: str
    name: str
    slug: str | None = None
    category: str | None = None
    market_cap_rank: int | None = None
    circulating_supply: float | None = None
    max_supply: float | None = None
    tags: list[str] = Field(default_factory=list)
    metadata_updated_at: datetime | None = None


class MarketQuote(BaseModel):
    cmc_id: int = Field(gt=0)
    currency: str = "USD"
    price: float | None = None
    market_cap: float | None = None
    volume_24h: float | None = None
    volume_to_market_cap: float | None = None
    percent_change_24h: float | None = None
    percent_change_7d: float | None = None
    percent_change_30d: float | None = None
    percent_change_90d: float | None = None
    last_updated: datetime | None = None
    source_updated_at: datetime | None = None


class ScoreBreakdown(BaseModel):
    stage_trend: float = Field(ge=0, le=1)
    breakout_structure: float = Field(ge=0, le=1)
    volume_liquidity: float = Field(ge=0, le=1)
    momentum_relative_strength: float = Field(ge=0, le=1)
    risk_entry_quality: float = Field(ge=0, le=1)

    @property
    def raw_total(self) -> float:
        return (
            self.stage_trend
            + self.breakout_structure
            + self.volume_liquidity
            + self.momentum_relative_strength
            + self.risk_entry_quality
        )


class ScreenerRow(BaseModel):
    cmc_id: int
    rank: int | None = None
    name: str
    symbol: str
    price: float | None = None
    percent_change_24h: float | None = None
    percent_change_7d: float | None = None
    percent_change_30d: float | None = None
    percent_change_90d: float | None = None
    market_cap: float | None = None
    volume_24h: float | None = None
    volume_to_market_cap: float | None = None
    stage: MarketStage = MarketStage.INSUFFICIENT_DATA
    stage_confidence: float = 0.0
    raw_score: float = 0.0
    display_score: float = 0.0
    rating: Rating = Rating.AVOID
    relative_strength_score: float | None = None
    cup_handle_confidence: float | None = None
    breakout_status: str | None = None
    data_quality_status: DataQualityStatus = DataQualityStatus.INSUFFICIENT_DATA
    last_updated: datetime | None = None
    missing_data: list[str] = Field(default_factory=list)


class CmcStatus(BaseModel):
    timestamp: datetime | None = None
    error_code: int | None = None
    error_message: str | None = None
    elapsed: int | None = None
    credit_count: int | None = None


class CmcEnvelope(BaseModel):
    data: Any
    status: CmcStatus


class HealthCheck(BaseModel):
    status: str
    app_env: str
    database_configured: bool
    coinmarketcap_configured: bool
    timestamp: datetime


class IngestResult(BaseModel):
    assets_seen: int
    quotes_saved: int
    currency: str
    warnings: list[str] = Field(default_factory=list)
