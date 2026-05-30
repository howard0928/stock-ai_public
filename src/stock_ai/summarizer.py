from __future__ import annotations

from openai import OpenAI

from stock_ai.market import StockMove
from stock_ai.news import NewsItem


class OpenAINewsSummarizer:
    def __init__(self, api_key: str, model: str) -> None:
        self._client = OpenAI(api_key=api_key)
        self._model = model

    def summarize(self, move: StockMove, news: list[NewsItem]) -> str:
        if not news:
            return "No recent company news was found for this move."

        article_text = _format_news(news)
        prompt = (
            f"{move.ticker} moved {move.change_percent:.2f}% today.\n\n"
            "Summarize the related news for an investor email report. "
            "Write the summary in Simplified Chinese. "
            "Keep it to 2-3 concise bullet points. Mention uncertainty when the news does not clearly explain the move.\n\n"
            f"{article_text}"
        )

        return self._complete(prompt)

    def summarize_market(self, moves: list[StockMove], news: list[NewsItem]) -> str:
        if not news:
            return "No recent market news was found for today's broad movement."

        moved_holdings = "\n".join(
            (
                f"- {move.ticker}: {move.change_percent:+.2f}% "
                f"(previous close ${move.previous_close:,.2f}, latest close ${move.latest_close:,.2f})"
            )
            for move in moves
        )
        article_text = _format_news(news)
        prompt = (
            "Today's portfolio monitoring detected broad movement across multiple holdings.\n\n"
            "Moved holdings:\n"
            f"{moved_holdings}\n\n"
            "Using the market news below, write a concise macro market brief for an investor email report. "
            "Identify the most likely broad-market driver of today's volatility, such as economic data, "
            "interest-rate expectations, central-bank decisions, earnings sentiment, or sector rotation. "
            "Then briefly explain how that macro trend may connect to the moved holdings above. "
            "Write the summary in Simplified Chinese. "
            "Keep it to 3-5 concise bullet points and clearly state uncertainty when the news does not fully explain the moves.\n\n"
            f"{article_text}"
        )

        return self._complete(prompt)

    def _complete(self, prompt: str) -> str:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "你是一名谨慎、清晰的市场新闻摘要助手。"
                            "请始终使用简体中文输出，不提供投资建议。"
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
        except Exception as exc:
            return _summarization_error_message(exc)

        content = response.choices[0].message.content
        return content.strip() if content else "OpenAI returned an empty summary."


def _format_news(news: list[NewsItem]) -> str:
    return "\n\n".join(
        (
            f"Headline: {item.headline}\n"
            f"Source: {item.source}\n"
            f"Summary: {item.summary}\n"
            f"URL: {item.url}"
        )
        for item in news
    )


def _summarization_error_message(exc: Exception) -> str:
    message = str(exc)
    if "insufficient_quota" in message or "exceeded your current quota" in message:
        return (
            "OpenAI summarization was skipped because the API account has no available quota. "
            "The Finnhub news links below were still fetched successfully."
        )

    if "must be verified" in message:
        return (
            "OpenAI summarization failed because this API organization is not verified for the configured model. "
            "Use gpt-4o-mini or verify the organization in OpenAI Platform."
        )

    if "model_not_found" in message or "does not exist" in message:
        return (
            "OpenAI summarization failed because the configured model is unavailable for this API key. "
            "Check OPENAI_MODEL in .env."
        )

    return f"OpenAI summarization failed: {type(exc).__name__}."
