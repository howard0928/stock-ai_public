from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class Holding:
    ticker: str
    shares: float


def read_holdings(path: str | Path) -> list[Holding]:
    csv_path = Path(path)
    if not csv_path.exists():
        raise FileNotFoundError(f"Holdings file not found: {csv_path}")

    df = pd.read_csv(csv_path)
    required = {"ticker", "shares"}
    missing = required - set(df.columns.str.lower())
    if missing:
        raise ValueError(f"Holdings CSV is missing required columns: {', '.join(sorted(missing))}")

    normalized = df.rename(columns={column: column.lower() for column in df.columns})
    holdings: list[Holding] = []
    for row in normalized.itertuples(index=False):
        ticker = str(row.ticker).strip().upper()
        if not ticker:
            continue
        holdings.append(Holding(ticker=ticker, shares=float(row.shares)))

    if not holdings:
        raise ValueError("Holdings CSV did not contain any valid tickers")

    return holdings
