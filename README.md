# Crypto Quant Research Dashboard

A cryptocurrency-only quantitative research dashboard for identifying Stage 1 bases, early Stage 2 transitions, confirmed Stage 2 breakouts, cup-and-handle structures, relative strength, liquidity quality, and explainable BUY / WATCH / AVOID research classifications.

This is a research and screening tool only. `BUY` is a quantitative research classification, not an instruction to purchase or trade.

## Current Scope

This repository contains the Phase 1 foundation:

- FastAPI backend package in `crypto_quant/`
- CoinMarketCap client scaffold with server-side API key handling
- Streamlit app with CoinMarketCap keyless live data and CoinGecko public API fallback
- Pydantic data contracts for crypto assets, quotes, scores, ratings, and agent outputs
- SQLAlchemy database models and initial migration
- Central crypto settings in `config/crypto_settings.toml`
- AI agent schemas and prompt files for Research, Technical Analysis, and Head Analyst agents
- Next.js TypeScript dashboard scaffold in `frontend/`
- Crypto-specific architecture and methodology plan in `docs/crypto_quant_plan.md`
- Focused backend tests in `tests/`

Only cryptocurrency research components are part of this repo.

## Architecture

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
|   |-- agents/
|   |-- migrations/
|   `-- services/
|-- frontend/
|   |-- app/
|   |-- lib/
|   `-- types/
|-- config/
|   `-- crypto_settings.toml
|-- docs/
|   `-- crypto_quant_plan.md
|-- tests/
|   `-- test_crypto_foundation.py
|-- .env.example
|-- requirements.txt
`-- README.md
```

## Environment

Create a local `.env` file from `.env.example` and fill secrets locally only:

```powershell
Copy-Item .env.example .env
```

Important variables:

```text
COINMARKETCAP_API_KEY=
DATABASE_URL=sqlite:///data/crypto_quant.sqlite
AI_PROVIDER=mock
AI_API_KEY=
APP_ENV=local
APP_SECRET_KEY=
```

Never commit a real `.env` file.

## Backend Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn crypto_quant.api:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /api/v1/settings`
- `GET /api/v1/screener`
- `POST /api/v1/scans/coinmarketcap`

The scan endpoint requires `COINMARKETCAP_API_KEY`.

## Frontend Setup

```powershell
cd frontend
pnpm install
pnpm dev
```

The frontend expects the backend at `http://localhost:8000` by default. Override with:

```powershell
$env:NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
```

## Testing

```powershell
python -m unittest discover -s tests
```

## Live Market Data Workaround

The Streamlit `app.py` first tries CoinMarketCap's keyless public simple-price endpoint:

```text
https://pro-api.coinmarketcap.com/public-api/v1/simple/price
```

If CoinMarketCap returns a temporary busy or unavailable response, the app falls back to CoinGecko's public `/coins/markets` endpoint. The sidebar can scan the top 10-250 coins by market cap, scan categories such as DeFi and RWA, or resolve custom ticker symbols through CoinGecko's public search endpoint before requesting market data. The screener includes a category filter whenever category-tagged rows are loaded. This keeps the dashboard populated with current public prices while preserving the no-key setup.

The current tests cover:

- crypto settings defaults
- five-point score normalization
- rating rejection rules
- CoinMarketCap listing parsing
- repository screener row storage when SQLAlchemy is installed

## Data Limitations

CoinMarketCap plan limits may affect access to historical OHLCV, quote history, category data, and market-pair depth. The system must record missing data explicitly and must not fabricate indicators, history, catalysts, liquidity, or agent conclusions.

See `docs/crypto_quant_plan.md` for the full architecture, database schema, scoring formula, stage rules, cup-and-handle methodology, API route design, AI agent contracts, security risks, and roadmap.

## Roadmap

1. Phase 2: historical OHLCV ingestion, technical indicators, liquidity filters, Stage 1-4 classification, relative strength, and full 5-point scoring.
2. Phase 3: full dashboard pages, charts, filters, watchlist, and settings UI.
3. Phase 4: Research Agent, Technical Analysis Agent, Head Analyst Agent, audit logs, and analyst report page.
4. Phase 5: alerts, scheduled scans, historical snapshots, and exports.
5. Phase 6: validation and backtesting without look-ahead bias.
