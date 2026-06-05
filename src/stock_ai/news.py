from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

import finnhub


COMPANY_ALIASES = {
    "AAPL": ("apple",),
    "AMAT": ("applied materials",),
    "AMZN": ("amazon",),
    "ANET": ("arista", "arista networks"),
    "AVGO": ("broadcom",),
    "COHR": ("coherent",),
    "CRS": ("carpenter technology",),
    "DRAM": ("dram", "global x semiconductor"),
    "GEN": ("gen digital",),
    "GOOG": ("alphabet", "google"),
    "GOOGL": ("alphabet", "google"),
    "META": ("meta", "facebook"),
    "MRVL": ("marvell",),
    "MSFT": ("microsoft",),
    "NVDA": ("nvidia",),
    "ORCL": ("oracle",),
    "PS": ("pluralsight",),
    "SPY": ("s&p 500", "spdr s&p 500"),
    "TSLA": ("tesla",),
    "UBER": ("uber",),
    "VEEV": ("veeva", "veeva systems"),
    "VST": ("vistra",),
}


@dataclass(frozen=True)
class NewsItem:
    headline: str
    source: str
    summary: str
    url: str
    published_at: int


class FinnhubNewsClient:
    def __init__(self, api_key: str) -> None:
        self._client = finnhub.Client(api_key=api_key)

    def market_news(self, limit: int) -> list[NewsItem]:
        articles = self._client.general_news("general", min_id=0)
        return self._normalize_articles(articles, limit)

    def company_news(self, ticker: str, days: int, limit: int) -> list[NewsItem]:
        today = date.today()
        start = today - timedelta(days=days)
        articles = self._client.company_news(ticker, _from=start.isoformat(), to=today.isoformat())
        return self._normalize_articles(articles, limit)

    def relevant_company_news(self, ticker: str, days: int, limit: int) -> list[NewsItem]:
        articles = self.company_news(ticker, days=days, limit=max(limit * 3, limit))
        return filter_relevant_company_news(ticker, articles, limit)

    def _normalize_articles(self, articles: list[dict], limit: int) -> list[NewsItem]:
        news: list[NewsItem] = []
        for article in sorted(articles, key=lambda item: item.get("datetime", 0), reverse=True):
            headline = (article.get("headline") or "").strip()
            url = (article.get("url") or "").strip()
            if not headline or not url:
                continue
            news.append(
                NewsItem(
                    headline=headline,
                    source=(article.get("source") or "Unknown").strip(),
                    summary=(article.get("summary") or "").strip(),
                    url=url,
                    published_at=int(article.get("datetime") or 0),
                )
            )
            if len(news) >= limit:
                break

        return news


def company_news_for_moves(client: FinnhubNewsClient, moves: list[Any], days: int, limit: int) -> list[NewsItem]:
    news: list[NewsItem] = []
    seen_urls: set[str] = set()
    per_ticker_limit = max(1, min(2, limit))
    for move in moves:
        for item in client.relevant_company_news(move.ticker, days=days, limit=per_ticker_limit):
            if item.url in seen_urls:
                continue
            seen_urls.add(item.url)
            news.append(item)
            if len(news) >= limit:
                return news
    return news


def filter_relevant_company_news(ticker: str, articles: list[NewsItem], limit: int) -> list[NewsItem]:
    relevant = [item for item in articles if _looks_relevant_to_trade_review(ticker, item)]
    return relevant[:limit]


def _looks_relevant_to_trade_review(ticker: str, item: NewsItem) -> bool:
    text = f"{item.headline} {item.summary}".lower()
    headline = item.headline.lower()
    symbol = ticker.lower()

    low_signal_phrases = (
        "top movers",
        "most active",
        "what's going on",
        "stay informed",
        "market movers",
        "s&p500 movers",
        "dow jones index",
    )
    if any(phrase in text for phrase in low_signal_phrases):
        return False

    aliases = COMPANY_ALIASES.get(ticker.upper(), ())
    return symbol in headline or any(alias in headline for alias in aliases)
