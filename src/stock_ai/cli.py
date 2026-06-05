from __future__ import annotations

import argparse
from pathlib import Path

from stock_ai.config import Settings
from stock_ai.holdings import read_holdings
from stock_ai.market import StockMove, get_daily_moves
from stock_ai.report import MacroReport, ReportItem, render_html_report


SYSTEMIC_MOVE_COUNT_THRESHOLD = 3


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate an HTML email report for large stock moves.")
    parser.add_argument("--holdings", default="holdings.csv", help="Path to holdings CSV.")
    parser.add_argument("--output", default="report.html", help="Path for generated HTML report.")
    parser.add_argument("--threshold", type=float, default=5.0, help="Absolute percent move threshold.")
    parser.add_argument(
        "--systemic-threshold",
        type=int,
        default=SYSTEMIC_MOVE_COUNT_THRESHOLD,
        help="Number of moved holdings that triggers the market macro path.",
    )
    parser.add_argument("--news-days", type=int, default=3, help="Finnhub company news lookback window.")
    parser.add_argument("--max-news", type=int, default=5, help="Maximum news articles per ticker.")
    parser.add_argument("--dry-run", action="store_true", help="Skip Finnhub and OpenAI calls.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    holdings = read_holdings(args.holdings)
    moves = get_daily_moves(holdings, args.threshold)
    if not moves:
        _write_report([], args.threshold, args.output)
        print(f"Wrote {args.output} with no holdings above the {args.threshold:.1f}% threshold. Skipped Finnhub and OpenAI calls.")
        return

    macro_path = len(moves) >= args.systemic_threshold
    if args.dry_run:
        report_items, macro_report = _build_dry_run_report(moves, macro_path)
    else:
        settings = Settings.from_env()
        _validate_api_keys(settings)
        from stock_ai.news import FinnhubNewsClient
        from stock_ai.news import company_news_for_moves
        from stock_ai.summarizer import OpenAINewsSummarizer

        news_client = FinnhubNewsClient(settings.finnhub_api_key or "")
        summarizer = OpenAINewsSummarizer(settings.openai_api_key or "", settings.openai_model)

        if macro_path:
            news = news_client.market_news(limit=args.max_news)
            if not news:
                news = company_news_for_moves(news_client, moves, days=args.news_days, limit=args.max_news)
            summary = summarizer.summarize_market(moves, news)
            report_items = []
            macro_report = MacroReport(moves=moves, news=news, summary=summary)
        else:
            macro_report = None
            report_items = []
            for move in moves:
                news = news_client.relevant_company_news(move.ticker, days=args.news_days, limit=args.max_news)
                summary = summarizer.summarize(move, news)
                report_items.append(ReportItem(move=move, news=news, summary=summary))

    output_path = _write_report(report_items, args.threshold, args.output, macro_report)
    path_name = "market macro" if macro_path else "individual stock"
    print(f"Wrote {output_path} with {len(moves)} moved holdings using the {path_name} path.")


def _build_dry_run_report(moves: list[StockMove], macro_path: bool) -> tuple[list[ReportItem], MacroReport | None]:
    if macro_path:
        return [], MacroReport(
            moves=moves,
            news=[],
            summary="Dry run: market news fetching and macro summarization were skipped.",
        )

    return [
        ReportItem(move=move, news=[], summary="Dry run: news fetching and summarization were skipped.")
        for move in moves
    ], None


def _write_report(
    report_items: list[ReportItem],
    threshold_percent: float,
    output: str,
    macro_report: MacroReport | None = None,
) -> Path:
    html = render_html_report(report_items, threshold_percent, macro_report)
    output_path = Path(output)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _validate_api_keys(settings: Settings) -> None:
    missing = []
    if not settings.finnhub_api_key:
        missing.append("FINNHUB_API_KEY")
    if not settings.openai_api_key:
        missing.append("OPENAI_API_KEY")
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Add them to .env or export them before running."
        )

    placeholders = []
    if _looks_like_placeholder(settings.finnhub_api_key):
        placeholders.append("FINNHUB_API_KEY")
    if _looks_like_placeholder(settings.openai_api_key):
        placeholders.append("OPENAI_API_KEY")
    if placeholders:
        raise RuntimeError(
            "Placeholder API keys found in .env: "
            + ", ".join(placeholders)
            + ". Replace them with real keys before running without --dry-run."
        )


def _looks_like_placeholder(value: str | None) -> bool:
    if not value:
        return False

    normalized = value.strip().lower()
    placeholder_markers = ("your_", "replace", "placeholder", "example", "demo", "test", "xxx")
    return any(marker in normalized for marker in placeholder_markers)


if __name__ == "__main__":
    main()
