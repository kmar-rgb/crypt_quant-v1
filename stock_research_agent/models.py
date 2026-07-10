from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Symbol:
    ticker: str
    market: str = "US"
    sector: str = "Unknown"
    name: str = ""


@dataclass(frozen=True)
class StageResult:
    stage: str
    confidence: float
    base_depth_pct: float | None
    notes: str


@dataclass(frozen=True)
class CupHandleResult:
    status: str
    pivot: float | None
    depth_pct: float | None
    duration_days: int | None
    handle_depth_pct: float | None
    breakout_volume_ratio: float | None
    notes: str


@dataclass(frozen=True)
class CandidateScore:
    total: float
    stage: float
    cup_handle: float
    volume: float
    relative_strength: float
    trend: float
    notes: str


@dataclass(frozen=True)
class Alert:
    ticker: str
    scan_date: date
    alert_type: str
    message: str
    priority: int = 2
