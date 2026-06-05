from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import yfinance as yf


def load_market_snapshot(tickers: list[str]) -> dict[str, dict[str, Any]]:
    symbols = sorted({ticker.strip().upper() for ticker in tickers if ticker.strip()})
    if not symbols:
        return {}

    data = yf.download(
        tickers=symbols,
        period="10d",
        interval="1d",
        auto_adjust=False,
        progress=False,
        group_by="ticker",
        threads=True,
    )
    snapshot: dict[str, dict[str, Any]] = {}
    for symbol in symbols:
        closes = _close_series(data, symbol, len(symbols) == 1)
        if closes.empty:
            snapshot[symbol] = _unavailable_price_snapshot()
            continue
        latest_close = float(closes.iloc[-1])
        previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else None
        five_day_close = float(closes.iloc[-6]) if len(closes) >= 6 else None
        snapshot[symbol] = {
            "current_price": latest_close,
            "one_day_percent": _percent_change(latest_close, previous_close),
            "five_day_percent": _percent_change(latest_close, five_day_close),
        }
    return snapshot


def load_fundamental_metrics(tickers: list[str]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for ticker in sorted({item.strip().upper() for item in tickers if item.strip()}):
        try:
            info = yf.Ticker(ticker).info
        except Exception:
            metrics[ticker] = _unavailable_metrics()
            continue

        metrics[ticker] = {
            "revenue_growth": info.get("revenueGrowth", "data unavailable"),
            "eps_growth": info.get("earningsGrowth", "data unavailable"),
            "forward_pe": info.get("forwardPE", "data unavailable"),
            "price_to_sales": info.get("priceToSalesTrailing12Months", "data unavailable"),
            "profit_margin": info.get("profitMargins", "data unavailable"),
            "free_cash_flow": info.get("freeCashflow", "data unavailable"),
            "analyst_revisions": "data unavailable",
            "earnings_date": _format_earnings_date(info.get("earningsDate")),
        }
    return metrics


def load_trade_performance(
    ticker: str,
    trade_datetime: str,
    benchmark: str = "SPY",
    trade_price: float | None = None,
) -> dict[str, Any]:
    start = _date_part(trade_datetime)
    symbols = [ticker.strip().upper(), benchmark.strip().upper()]
    try:
        data = yf.download(
            tickers=symbols,
            start=start,
            interval="1d",
            auto_adjust=False,
            progress=False,
            group_by="ticker",
            threads=True,
        )
    except Exception:
        return {
            "ticker_return": "data unavailable",
            "benchmark": benchmark,
            "benchmark_return": "data unavailable",
        }

    return {
        "ticker_return": _return_since_trade_price(data, symbols[0], len(symbols) == 1, trade_price),
        "benchmark": benchmark,
        "benchmark_return": _return_since(data, symbols[1], False, allow_single_point=True),
    }


def _return_since_trade_price(
    data: pd.DataFrame,
    ticker: str,
    single_ticker: bool,
    trade_price: float | None,
) -> float | str:
    closes = _close_series(data, ticker, single_ticker)
    if closes.empty:
        return "data unavailable"
    latest = float(closes.iloc[-1])
    if trade_price is not None and trade_price > 0:
        change = _percent_change(latest, trade_price)
        return change if change is not None else "data unavailable"
    return _return_from_closes(closes)


def _return_since(
    data: pd.DataFrame,
    ticker: str,
    single_ticker: bool,
    allow_single_point: bool = False,
) -> float | str:
    closes = _close_series(data, ticker, single_ticker)
    if len(closes) == 1 and allow_single_point:
        return 0.0
    return _return_from_closes(closes)


def _return_from_closes(closes: pd.Series) -> float | str:
    if len(closes) < 2:
        return "data unavailable"
    first = float(closes.iloc[0])
    latest = float(closes.iloc[-1])
    change = _percent_change(latest, first)
    return change if change is not None else "data unavailable"


def _close_series(data: pd.DataFrame, ticker: str, single_ticker: bool) -> pd.Series:
    if data.empty:
        return pd.Series(dtype=float)
    if isinstance(data.columns, pd.MultiIndex):
        try:
            close = data[ticker]["Close"]
        except KeyError:
            return pd.Series(dtype=float)
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


def _percent_change(latest: float, earlier: float | None) -> float | None:
    if earlier in (None, 0):
        return None
    return ((latest - earlier) / earlier) * 100


def _unavailable_price_snapshot() -> dict[str, Any]:
    return {
        "current_price": "data unavailable",
        "one_day_percent": "data unavailable",
        "five_day_percent": "data unavailable",
    }


def _unavailable_metrics() -> dict[str, Any]:
    return {
        "revenue_growth": "data unavailable",
        "eps_growth": "data unavailable",
        "forward_pe": "data unavailable",
        "price_to_sales": "data unavailable",
        "profit_margin": "data unavailable",
        "free_cash_flow": "data unavailable",
        "analyst_revisions": "data unavailable",
        "earnings_date": "data unavailable",
    }


def _format_earnings_date(value: Any) -> str:
    if not value:
        return "data unavailable"
    if isinstance(value, list) and value:
        value = value[0]
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def _date_part(value: str) -> str:
    return value.split("T", 1)[0].split(" ", 1)[0]
