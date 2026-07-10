# Crypto Quant Research Dashboard Plan

This plan defines the target architecture and Phase 1 implementation boundaries for the cryptocurrency research dashboard. It is a quantitative research tool only. `BUY` is a research classification, not an instruction to purchase or trade.

Sources checked for CoinMarketCap integration design:

- CoinMarketCap API overview: https://coinmarketcap.com/api/documentation/
- CoinMarketCap endpoint overview: https://coinmarketcap.com/api/documentation/pro-api-reference/endpoint-overview
- CoinMarketCap authentication guide: https://coinmarketcap.com/api/documentation/guides/authentication
- CoinMarketCap standards and conventions: https://coinmarketcap.com/api/documentation/guides/standards-and-conventions
- CoinMarketCap rate-limit and troubleshooting guide: https://coinmarketcap.com/api/documentation/guides/errors-and-rate-limits
- CoinMarketCap best practices: https://coinmarketcap.com/api/documentation/guides/best-practices

## 1. Proposed System Architecture

Analytical job: ranking, monitoring, time-change tracking, and explainable signal validation for crypto swing-trading setups.

Artifact family: operational dashboard with a screener table, stage/rating distributions, chart detail pages, agent reports, alerts, exports, and validation views.

Primary route: FastAPI backend owns data ingestion, deterministic calculations, persistence, agents, alerts, and exports. Next.js frontend owns interactive views only. Background scans run server-side.

Fallback route: when CoinMarketCap historical data is unavailable on the active plan, the data-provider layer records missing fields and allows a future OHLCV provider to be plugged in without changing scoring or UI contracts.

Core services:

- `CoinMarketCapClient`: authenticated API access, pagination, retries, timeout, response validation, and secret-safe logging.
- `MarketDataIngestionService`: fetches current listings, quotes, metadata, and historical bars where available.
- `TechnicalIndicatorService`: calculates moving averages, slopes, RSI, MACD, ATR, momentum, volatility, relative volume, and distance metrics.
- `StageAnalysisService`: deterministic Stage 1 through Stage 4 classification.
- `PatternDetectionService`: cup-and-handle and breakout measurement.
- `LiquidityFilterService`: stablecoin, wrapped-token, market-cap, volume, history, and volatility filters.
- `ScoringService`: five-category score out of 5 plus explainability.
- `AgentOrchestrator`: runs Research, Technical Analysis, and Head Analyst agents from structured deterministic inputs.
- `AlertService`: creates deduplicated in-app alerts.
- `BacktestService`: reconstructs signals using only data available at each historical timestamp.

## 2. Recommended Folder Structure

```text
.
|-- crypto_quant/
|   |-- api.py
|   |-- cmc_client.py
|   |-- config.py
|   |-- database.py
|   |-- db_models.py
|   |-- models.py
|   |-- repositories.py
|   |-- services/
|   |   |-- ingestion.py
|   |   |-- scoring.py
|   |   |-- stage_rules.py
|   |-- agents/
|   |   |-- schemas.py
|   |   |-- prompts/
|   |-- migrations/
|   |   |-- 0001_crypto_foundation.sql
|-- frontend/
|   |-- app/
|   |-- components/
|   |-- lib/
|   |-- types/
|-- config/
|   |-- crypto_settings.toml
|-- data/
|   |-- crypto_quant.sqlite
|-- docs/
|   |-- crypto_quant_plan.md
|-- tests/
```

## 3. Database Schema

Production target: PostgreSQL. Local development target: SQLite.

Initial tables:

- `cryptocurrencies`: stable CMC ID, symbol, name, slug, category, tags, supply fields, market-cap rank, metadata timestamp.
- `market_quotes`: latest price, market cap, volume, volume-to-market-cap, percentage changes, circulating supply, last updated.
- `price_history`: OHLCV bars keyed by CMC ID and date.
- `market_snapshots`: global scan timestamp, counts, BTC regime, total market fields where available.
- `technical_indicators`: calculated indicators and distances.
- `stage_classifications`: stage, sub-stage, confidence, evidence JSON, timestamp.
- `pattern_detections`: cup-and-handle fields, breakout status, quality notes.
- `quantitative_scores`: raw and rounded scores, five category components, penalties, rating, explainability.
- `agent_runs`: agent name, prompt version, input hash, output JSON, confidence, usage, errors.
- `analyst_reports`: Head Analyst summary, rankings, disagreements, generated timestamp.
- `alerts`: type, condition key, current state hash, dedupe key, status, created timestamp.
- `watchlists` and `watchlist_notes`: user-managed tracking fields.
- `backtest_runs` and `backtest_results`: assumptions, metrics, and segmented performance.
- `application_settings`: centrally stored configurable thresholds.
- `audit_logs`: secret-safe operational events.

## 4. CoinMarketCap Endpoint Requirements

Use server-side requests only. The frontend never receives the API key.

Required Phase 1 endpoints:

- `/v1/cryptocurrency/map`: resolve stable CMC IDs and avoid symbol ambiguity.
- `/v1/cryptocurrency/listings/latest`: ranked, paginated universe scan by market cap.
- `/v2/cryptocurrency/info`: metadata, categories, tags, platform, URLs, and logos.
- `/v1/cryptocurrency/quotes/latest`: targeted latest quotes for watchlists or refreshes.
- `/v1/global-metrics/quotes/latest`: Bitcoin dominance and total market context.
- `/key/info`: optional health and usage diagnostics.

Required for Phase 2 and later, subject to plan access:

- `/v2/cryptocurrency/ohlcv/historical` or current documented OHLCV endpoint for candles.
- `/v3/cryptocurrency/quotes/historical` where quote-level history is preferred.
- `/v1/cryptocurrency/categories` and category endpoints for sector context if available on the active plan.
- Exchange market-pair endpoints for exchange coverage and market-count liquidity checks.

## 5. Data Limitations And Missing-Data Risks

CoinMarketCap can provide current prices, listings, quotes, metadata, exchange data, global metrics, and historical OHLCV, but access depends on the active plan. Historical depth, endpoint availability, rate limits, and category data may be restricted.

Metrics likely available from CoinMarketCap:

- Current price, market cap, rank, 24-hour volume, supply, percent changes, tags, categories, URLs, exchange pairs, total market metrics, BTC dominance, and OHLCV where the plan supports it.

Metrics that may require another provider or a higher plan:

- Full daily OHLCV history for every asset, bid/ask spreads, order-book depth, token unlock schedules, verified float data, active users, on-chain fundamentals, category-level benchmark history, and current news/catalyst feeds.

The system must store explicit `missing_data` and `data_quality_status` fields rather than fabricating unavailable values.

## 6. Stage-Classification Rules

Stage classification is deterministic and evidence-based:

- Stage 1 accumulation: sideways range, contained base depth, flattening long-term average, reduced volatility, repeated resistance tests, improving relative strength.
- Early Stage 2: close above base resistance or pivot, price above key moving averages, 150-day or 200-day average flattening/up, relative strength improving, not extended.
- Confirmed Stage 2: price above 50/150/200-day averages, moving-average alignment improving, higher highs/lows, breakout or constructive retest, positive volume confirmation.
- Extended Stage 2: Stage 2 trend but distance from pivot, 50-day, or 200-day exceeds configured extension limits.
- Stage 3 distribution: volatile highs, failed breakouts, weakening relative strength, flattening long average, lower highs.
- Stage 4 decline: price below falling long-term averages, lower highs/lows, weak relative strength, breakdown below support.

## 7. Exact Scoring Formula

Total raw score is the sum of five one-point categories:

```text
raw_score = stage_trend
          + breakout_structure
          + volume_liquidity
          + momentum_relative_strength
          + risk_entry_quality
```

Each component is clamped from `0.0` to `1.0`. The stored display score is rounded to one decimal place. The raw unrounded score is retained.

Default score weights are equal. If settings change weights, each category is normalized so the maximum remains `5.0`.

Critical rejection rules can cap the final rating even when score is high:

- liquidity failure
- insufficient data
- Stage 3 or Stage 4
- failed breakout
- excessive extension
- poor risk-to-reward
- critical risk flag

## 8. Exact Rating Rules

Default thresholds:

- `BUY`: raw score >= 4.0, Early or Confirmed Stage 2, liquidity filters pass, no critical risk flags, not excessively extended, risk-to-reward >= configured minimum.
- `WATCH`: raw score >= 3.0 and < 4.0, late Stage 1 or Early Stage 2, or a promising setup requiring confirmation.
- `AVOID`: raw score < 3.0, Stage 3 or Stage 4, failed liquidity or data quality, failed breakout, deteriorating momentum, excessive extension, poor risk-to-reward, or critical risk flags.

All thresholds live in `config/crypto_settings.toml`.

## 9. Cup-And-Handle Detection Methodology

The detector must measure the pattern before assigning confidence:

- Find a left-side high, rounded decline, low, right-side recovery, handle, and pivot.
- Cup duration must fall inside configured minimum and maximum bars.
- Cup depth must fall inside configured minimum and maximum percentages.
- Right side must recover near the left high.
- Handle must form in the upper portion of the cup.
- Handle depth and volatility must stay within configured limits.
- Handle volume should contract relative to cup volume.
- Breakout requires close above pivot and configured relative volume.

Output includes `detected`, `confidence`, `pivot_price`, `distance_from_pivot_pct`, `cup_depth_pct`, `handle_depth_pct`, `breakout_status`, and quality notes. Malformed, too-deep, too-short, and volatile structures are explicitly rejected.

## 10. AI Agent Input And Output Schemas

Agents receive only structured data that deterministic services calculated or verified.

Research Agent input:

- asset identity, metadata, supply, rank, tags, category, known URLs, market data, available catalyst/news fields, missing-data list.

Research Agent output:

- symbol, project name, sector, summary, market-cap class, catalysts, risks, tokenomics observations, fundamental quality score, confidence, missing information, final view.

Technical Analysis Agent input:

- indicators, stage result, support/resistance, pattern result, relative strength, liquidity result, score breakdown, risk fields, missing data.

Technical Analysis Agent output:

- stage, confidence, trend quality, pattern status, breakout status, pivot, support, invalidation, entry quality, extension risk, volume, momentum, relative strength, risk-to-reward, strengths, weaknesses, required confirmation, conclusion.

Head Analyst Agent input:

- deterministic score/rating, risk flags, Research Agent report, Technical Analysis Agent report, market context.

Head Analyst Agent output:

- quantitative score, automated rating, final analyst rating, confidence, stage, setup summary, bull case, bear case, catalyst, risk, required confirmation, entry zone, invalidation, risk-to-reward, reasons, conclusion.

## 11. API Route Design

Phase 1 routes:

- `GET /health`: service health, database status, CMC configuration presence, timestamp.
- `GET /api/v1/settings`: non-secret settings.
- `GET /api/v1/screener`: latest stored quotes and research classifications.
- `POST /api/v1/scans/coinmarketcap`: start a server-side CMC listings ingest.

Later routes:

- `GET /api/v1/market-overview`
- `GET /api/v1/coins/{cmc_id}`
- `GET /api/v1/coins/{cmc_id}/history`
- `GET /api/v1/reports/latest`
- `GET /api/v1/alerts`
- `POST /api/v1/watchlist`
- `PATCH /api/v1/watchlist/{cmc_id}`
- `POST /api/v1/backtests`
- `GET /api/v1/exports/{format}`

## 12. Frontend Page Structure

Dashboard pages:

- Market Overview: counts, stage/rating distributions, score distribution, sector leaders, data freshness.
- Quant Screener: searchable sortable table with filters, score breakdown, data-quality status, and stale markers.
- Coin Detail: candlestick, volume, moving averages, support/resistance, pivot, score, evidence, agents, history.
- AI Analyst Report: Head Analyst market summary, BUY/WATCH/AVOID groupings, disagreements, missing-data warnings.
- Watchlist: notes, target entry, stop, target, required confirmation, setup status, alerts.
- Settings: CMC key setup status, provider config, thresholds, filters, currency, timezone, alert preferences.

Mobile reading path: overview metrics first, then top ranked table with horizontal scroll, then details as collapsible evidence sections. Hover-only interactions become tap/focus states.

## 13. Development Roadmap

Phase 1: repository structure, FastAPI backend, Next.js frontend scaffold, environment config, database models/migration, CMC client, latest listings ingestion, health checks, basic screener.

Phase 2: indicators, stage analysis, relative strength, liquidity filters, scoring, ratings, explainability.

Phase 3: dashboard pages, charts, filters, watchlist, settings.

Phase 4: AI agents, structured outputs, prompt versioning, audit logs, analyst report.

Phase 5: scheduled scans, historical snapshots, in-app alerts, exports.

Phase 6: backtesting, walk-forward validation, paper-trading mode, validation dashboard.

## 14. Security Risks

- API keys must stay in environment variables and server-side settings only.
- Logs must never include API keys, Authorization headers, full request URLs containing secrets, or raw AI prompts containing secrets.
- Frontend must call the backend, not CoinMarketCap directly.
- Exports must omit secrets and redact prompt/debug metadata.
- AI outputs are advisory interpretation over deterministic values and must not replace calculations.
- Watchlist notes and reports may contain sensitive research; protect them before deploying beyond local use.
- Background jobs need deduplication and rate-limit awareness to avoid runaway API credit usage.

## 15. Testing Strategy

Phase 1 tests:

- settings loading and default thresholds
- CMC response validation from fixture JSON
- CMC client request construction without exposing keys
- database migration creation
- screener repository read/write
- health response without network calls

Later tests:

- technical indicators and moving-average slopes
- stage classification edge cases
- cup-and-handle detection rejection cases
- scoring and rating thresholds
- liquidity filters and extension rules
- risk-to-reward calculations
- agent schema validation and disagreement handling
- alert deduplication
- historical snapshots
- backtest logic and look-ahead-bias prevention
