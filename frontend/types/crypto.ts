export type Rating = "BUY" | "WATCH" | "AVOID";

export type ScreenerRow = {
  cmc_id: number;
  rank: number | null;
  name: string;
  symbol: string;
  price: number | null;
  percent_change_24h: number | null;
  percent_change_7d: number | null;
  percent_change_30d: number | null;
  percent_change_90d: number | null;
  market_cap: number | null;
  volume_24h: number | null;
  volume_to_market_cap: number | null;
  stage: string;
  stage_confidence: number;
  raw_score: number;
  display_score: number;
  rating: Rating;
  relative_strength_score: number | null;
  cup_handle_confidence: number | null;
  breakout_status: string | null;
  data_quality_status: string;
  last_updated: string | null;
  missing_data: string[];
};
