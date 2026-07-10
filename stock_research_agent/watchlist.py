from __future__ import annotations

from pathlib import Path

import pandas as pd

from .models import Symbol


def load_symbols(path: str | Path) -> list[Symbol]:
    frame = pd.read_csv(path)
    required = {"ticker", "market", "sector"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Watchlist is missing columns: {sorted(missing)}")

    symbols: list[Symbol] = []
    for row in frame.itertuples(index=False):
        symbols.append(
            Symbol(
                ticker=str(row.ticker).strip().upper(),
                market=str(row.market).strip(),
                sector=str(row.sector).strip(),
                name=str(getattr(row, "name", "") or ""),
            )
        )
    return symbols
