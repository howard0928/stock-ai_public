from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import yfinance as yf

from stock_ai.holdings import Holding


@dataclass(frozen=True)
class StockMove:
    ticker: str
    shares: float
    previous_close: float
    latest_close: float
    change_percent: float
    market_value: float

    @property
    def direction(self) -> str:
        return "up" if self.change_percent >= 0 else "down"


def get_daily_moves(holdings: list[Holding], threshold_percent: float) -> list[StockMove]:
    tickers = [holding.ticker for holding in holdings]
    if not tickers:
        return []

    data = yf.download(
        tickers=tickers,
        period="2d",
        interval="5m",
        auto_adjust=False,
        prepost=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    if data.empty:
        raise RuntimeError("No market data was returned by yfinance. Check network access and ticker symbols.")

    moves: list[StockMove] = []
    for holding in holdings:
        closes = _closing_prices(data, holding.ticker, len(tickers) == 1)
        prices = _latest_session_prices(closes)
        if prices is None:
            continue

        previous_close, latest_close = prices
        if previous_close == 0:
            continue

        change_percent = ((latest_close - previous_close) / previous_close) * 100
        if abs(change_percent) >= threshold_percent:
            moves.append(
                StockMove(
                    ticker=holding.ticker,
                    shares=holding.shares,
                    previous_close=previous_close,
                    latest_close=latest_close,
                    change_percent=change_percent,
                    market_value=latest_close * holding.shares,
                )
            )

    return sorted(moves, key=lambda move: abs(move.change_percent), reverse=True)


def _latest_session_prices(closes: pd.Series) -> tuple[float, float] | None:
    if len(closes) < 2:
        return None

    session_closes = closes.groupby(closes.index.date).last().dropna()
    if len(session_closes) < 2:
        return None

    previous_close = float(session_closes.iloc[-2])
    latest_close = float(closes.iloc[-1])
    return previous_close, latest_close


def _closing_prices(data: pd.DataFrame, ticker: str, single_ticker: bool) -> pd.Series:
    if data.empty:
        return pd.Series(dtype=float)

    if isinstance(data.columns, pd.MultiIndex):
        close = _multi_index_close(data, ticker)
    elif single_ticker:
        close = data.get("Close")
    else:
        try:
            close = data[ticker]["Close"]
        except KeyError:
            return pd.Series(dtype=float)

    if close is None:
        return pd.Series(dtype=float)
    return close.dropna()


def _multi_index_close(data: pd.DataFrame, ticker: str) -> pd.Series | None:
    if ticker in data.columns.get_level_values(0):
        try:
            return data[ticker]["Close"]
        except KeyError:
            return None

    if "Close" in data.columns.get_level_values(0):
        try:
            return data["Close"][ticker]
        except KeyError:
            return None

    return None
