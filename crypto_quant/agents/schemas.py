from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchAgentOutput(BaseModel):
    symbol: str
    project_name: str
    sector: str | None = None
    project_summary: str
    market_cap_classification: str | None = None
    key_catalysts: list[str] = Field(default_factory=list)
    key_risks: list[str] = Field(default_factory=list)
    tokenomics_observations: list[str] = Field(default_factory=list)
    fundamental_quality_score: float = Field(ge=0, le=100)
    research_confidence: float = Field(ge=0, le=100)
    missing_information: list[str] = Field(default_factory=list)
    final_research_view: str


class TechnicalAgentOutput(BaseModel):
    symbol: str
    current_stage: str
    stage_confidence: float = Field(ge=0, le=100)
    trend_quality: str
    pattern_detected: bool
    pattern_confidence: float = Field(ge=0, le=100)
    breakout_status: str | None = None
    pivot_or_resistance_level: float | None = None
    support_level: float | None = None
    suggested_invalidation_level: float | None = None
    entry_quality: str
    extension_risk: str
    volume_confirmation: str
    momentum_condition: str
    relative_strength_condition: str
    risk_to_reward_estimate: float | None = None
    technical_strengths: list[str] = Field(default_factory=list)
    technical_weaknesses: list[str] = Field(default_factory=list)
    required_confirmation: list[str] = Field(default_factory=list)
    technical_conclusion: str
    technical_confidence: float = Field(ge=0, le=100)


class HeadAnalystOutput(BaseModel):
    symbol: str
    quantitative_score_out_of_5: float = Field(ge=0, le=5)
    automated_rating: str
    final_analyst_rating: str
    overall_confidence: float = Field(ge=0, le=100)
    stage: str
    setup_summary: str
    bull_case: str
    bear_case: str
    key_catalyst: str | None = None
    key_risk: str | None = None
    required_confirmation: list[str] = Field(default_factory=list)
    potential_entry_zone: str | None = None
    invalidation_level: float | None = None
    risk_to_reward: float | None = None
    reasons_for_rating: list[str] = Field(default_factory=list)
    final_conclusion: str
