# Swing Setup Research Agent

An AI-assisted stock research and tracking application for swing trading candidates. It focuses on cup-and-handle breakouts, Stage 1 to Stage 2 transitions, volume confirmation, relative strength, and a readable monitoring dashboard.

This is a research and tracking tool only. It does not place trades, send orders, or automate trading decisions.

## Project Architecture

```text
.
├── app.py                         # Streamlit dashboard
├── data/
│   └── watchlist.csv              # Starter watchlist
├── stock_research_agent/
│   ├── alerts.py                  # Breakout and setup alerts
│   ├── backtesting.py             # Simple breakout follow-through tests
│   ├── config.py                  # Defaults and paths
│   ├── data_provider.py           # Market data adapters
│   ├── indicators.py              # Moving averages and relative strength
│   ├── patterns.py                # Cup-and-handle detection
│   ├── scanner.py                 # End-to-end scan pipeline
│   ├── scoring.py                 # Setup quality score
│   ├── stage_analysis.py          # Stage 1 / Stage 2 logic
│   ├── storage.py                 # SQLite schema and persistence
│   └── watchlist.py               # Watchlist loading
└── tests/
    └── test_research_logic.py
```

## Data Pipeline

1. Load symbols from `data/watchlist.csv`.
2. Pull daily OHLCV data from the configured provider.
3. Store daily prices in SQLite.
4. Calculate 10-day, 20-day, 50-day, 150-day, and 200-day moving averages.
5. Resample daily bars into weekly OHLCV.
6. Calculate relative strength versus the selected benchmark.
7. Run stage analysis and cup-and-handle detection.
8. Score each setup and save scan results.
9. Generate alerts and display results in the dashboard.

The default provider is Yahoo Finance via `yfinance`. A CSV provider is also included for offline research and repeatable tests.

## Database Schema

SQLite database: `data/stock_research.sqlite`

Tables:

- `symbols`: ticker metadata, market, sector, name.
- `prices_daily`: historical daily OHLCV.
- `scan_runs`: each scan timestamp, market, benchmark.
- `scan_candidates`: score, stage, pattern status, pivot distance, volume ratio, relative strength.
- `alerts`: breakout, near-pivot, and Stage 2 setup alerts.
- `watchlist_notes`: manual notes by ticker.
- `backtest_runs`: reserved for storing backtest summaries.

## Pattern Detection Logic

Cup-and-handle detection checks:

- Cup duration between 35 and 325 trading days.
- Cup depth between 12% and 40%.
- Right side recovers to at least 85% of the left-side high.
- Handle forms after the right-side recovery.
- Handle pullback stays at or below 15%.
- Breakout requires a close above pivot with volume above the configured volume ratio.

The detector returns one of:

- `Breakout`
- `Handle near pivot`
- `Handle forming`
- `Cup formed`
- `Cup forming`
- `No cup`
- `Insufficient data`

## Stage Analysis Logic

Stage analysis uses daily and weekly structure:

- `Stage 1 accumulation`: contained base depth, price near long moving averages, flattening 50-day average.
- `Stage 2 uptrend`: price above 50-day, 150-day, and 200-day averages with the 200-day average rising.
- `Stage 3 distribution / transition`: mixed structure around major moving averages.
- `Stage 4 decline`: price below long moving averages.

## Scoring System

Each stock receives a 0-100 setup score:

- Stage quality: up to 25 points.
- Cup-and-handle quality: up to 25 points.
- Volume confirmation: up to 20 points.
- Relative strength trend: up to 15 points.
- Moving-average trend alignment: up to 15 points.

The score is intended for ranking candidates, not for automatic buy or sell decisions.

The richer criteria engine in `stock_research_agent/criteria_engine.py` uses the requested scoring categories:

- Stage 2 transition quality: 25 points.
- Cup and handle quality: 25 points.
- Volume confirmation: 15 points.
- Relative strength: 15 points.
- Risk/reward structure: 10 points.
- Market condition: 10 points.

It classifies each stock as `Ignore`, `Early Watch`, `Strong Watch`, `Breakout Candidate`, `Breakout Confirmed`, `Extended / Too Late`, or `Failed Breakout`.

## Dashboard Layout

The Streamlit dashboard is now organized into pages:

- Market Overview: benchmark trend, stocks above 50-day and 200-day averages, breakout counts, and market score.
- Stock Screener: scanned-stock table with filters for market, sector, stage, score, relative strength, volume, and breakout distance.
- Stock Detail: daily and weekly candlestick charts, moving averages, volume, relative strength, pivot, stop, risk/reward, and notes.
- Watchlist: saved stocks, status, price versus pivot, alerts, notes, date added, and score history.
- Backtesting: historical cup-and-handle breakout tests with win rate, average gain/loss, maximum drawdown, failed breakout rate, and performance breakdowns.
- Alerts: near pivot, confirmed breakout, failed breakout, moving-average violation, volume spike, and relative-strength improvement.

## Alert System

Alerts are stored in SQLite and shown in the dashboard.

Current alert types:

- `breakout`: price closes above pivot with volume confirmation.
- `near_pivot`: price is within the configured percent below pivot.
- `stage_2_setup`: Stage 2 structure plus a valid handle or breakout.

## Backtesting Module

The backtesting module is intentionally simple. It evaluates historical cup-and-handle breakout follow-through:

- Uses the criteria engine to find historical confirmed breakout signals.
- Tracks score range and market condition at the time of the signal.
- Enters on the next open.
- Exits after a fixed holding period or a stop-loss touch.
- Reports win rate, average gain, average loss, maximum drawdown, average holding period, failed breakout rate, performance by score range, and performance by market condition.

This is a research aid, not a full portfolio simulator.

## Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Run the dashboard:

```powershell
streamlit run app.py
```

Open the local Streamlit URL shown in the terminal.

To try the MVP without live market data, open the sidebar and click `Load sample data`. This generates deterministic CSV data in `data/sample`, runs a sample scan, and populates SQLite.

## Watchlist Format

Edit `data/watchlist.csv`:

```csv
ticker,market,sector,name
AAPL,US,Technology,Apple
MSFT,US,Technology,Microsoft
```

For ASX symbols with Yahoo Finance, use the `.AX` suffix, such as `BHP.AX`.

The included offline demo watchlist is `data/sample_watchlist.csv`.

## Offline CSV Data

To use offline CSV data, place files in `data/raw`, one file per ticker:

```text
data/raw/AAPL.csv
data/raw/SPY.csv
```

Each CSV must contain:

```csv
date,open,high,low,close,volume
```

Then choose `CSV folder` in the dashboard sidebar.

## Verification

Run the test suite:

```powershell
python -m unittest discover -s tests
```

## Next Practical Improvements

- Add a paid market data provider adapter if you have a preferred API.
- Add email or desktop notifications for alerts.
- Add richer backtesting with stops, position sizing, slippage, and benchmark comparison.
- Add sector and index breadth models for stronger market context.

## Crypto Quant Dashboard Phase 1

This repository now includes the Phase 1 foundation for a separate cryptocurrency quantitative research dashboard. The existing stock Streamlit app remains unchanged.

Phase 1 adds:

- `docs/crypto_quant_plan.md`: system architecture, schema, endpoint plan, data limitations, stage rules, scoring formula, rating rules, agent schemas, API routes, frontend structure, roadmap, security risks, and testing strategy.
- `crypto_quant/`: FastAPI backend package with validated Pydantic models, central config loading, SQLAlchemy database models, repository layer, CoinMarketCap client, ingestion service, scoring/rating helpers, migrations, and AI agent contracts.
- `frontend/`: Next.js TypeScript dashboard shell wired to the backend screener endpoint.
- `config/crypto_settings.toml`: central configurable thresholds for filters, scoring, stage rules, patterns, alerts, scan frequency, currency, and timezone.
- `.env.example`: placeholder-only environment variables.

Install the expanded backend dependencies:

```powershell
pip install -r requirements.txt
```

Start the FastAPI backend:

```powershell
uvicorn crypto_quant.api:app --reload
```

Start the Next.js frontend from the `frontend` folder after installing Node dependencies:

```powershell
pnpm install
pnpm dev
```

Run tests:

```powershell
python -m unittest discover -s tests
```

CoinMarketCap API keys must be stored in environment variables only. The frontend calls the backend and never calls CoinMarketCap directly.
