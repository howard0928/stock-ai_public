from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import finnhub


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
