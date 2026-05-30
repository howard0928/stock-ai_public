from __future__ import annotations

from datetime import datetime
from typing import Any

from stock_ai import portfolio_db


RECENT_TRADE_LIMIT = 5


def generate_review_report(
    db_path: str,
    market_snapshot: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    news_by_ticker: dict[str, list[dict[str, Any]]],
    trade_performance: dict[int, dict[str, Any]],
) -> tuple[str, dict[str, Any]]:
    holdings = portfolio_db.list_holdings(db_path)
    transactions = portfolio_db.list_transactions(db_path)
    key_tickers = _key_tickers(holdings, transactions[:RECENT_TRADE_LIMIT], market_snapshot)
    data_snapshot = {
        "holdings": holdings,
        "transactions": transactions,
        "market_snapshot": market_snapshot,
        "metrics": metrics,
        "news_by_ticker": news_by_ticker,
        "trade_performance": trade_performance,
        "key_tickers": key_tickers,
    }
    report = _compose_report(holdings, transactions, data_snapshot)
    portfolio_db.save_review_report(db_path, report, key_tickers, data_snapshot)
    return report, data_snapshot


def _compose_report(
    holdings: list[dict[str, Any]],
    transactions: list[dict[str, Any]],
    data_snapshot: dict[str, Any],
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    recent_trades = transactions[:RECENT_TRADE_LIMIT]
    lines = [
        "# 个人交易复盘",
        "",
        f"生成时间：{generated_at}",
        "",
        "## 1. Portfolio Status",
        "",
        *_portfolio_status_lines(holdings, data_snapshot["market_snapshot"]),
        "",
        "## 2. Behavioral Diagnosis",
        "",
        *_behavior_lines(recent_trades, holdings, data_snapshot["market_snapshot"], data_snapshot["trade_performance"]),
        "",
        "## 3. Recent Trade Review",
        "",
        *_recent_trade_review_lines(recent_trades, data_snapshot["trade_performance"]),
        "",
        "## 4. Key Stock Check",
        "",
        *_key_stock_lines(
            data_snapshot["key_tickers"],
            data_snapshot["market_snapshot"],
            data_snapshot["metrics"],
            data_snapshot["news_by_ticker"],
        ),
        "",
        "## 5. Next Actions",
        "",
        *_next_action_lines(recent_trades),
        "",
        "这不是财务建议，只是个人交易复盘辅助。",
    ]
    return "\n".join(lines)


def _portfolio_status_lines(holdings: list[dict[str, Any]], market_snapshot: dict[str, dict[str, Any]]) -> list[str]:
    if not holdings:
        return ["- 事实：当前没有可复盘的持仓记录。"]

    total_value = 0.0
    total_cost = 0.0
    rows = []
    for holding in holdings:
        ticker = holding["ticker"]
        price = market_snapshot.get(ticker, {}).get("current_price", "data unavailable")
        shares = float(holding["shares"])
        avg_cost = float(holding["avg_cost"])
        if _is_number(price):
            market_value = shares * float(price)
            total_value += market_value
            total_cost += shares * avg_cost
            rows.append((ticker, market_value))
        else:
            rows.append((ticker, None))

    largest = max((row for row in rows if row[1] is not None), key=lambda row: row[1], default=None)
    concentration = _top_concentration(rows, total_value)
    unrealized = total_value - total_cost if total_value else None
    return [
        f"- 事实：当前持仓 {len(holdings)} 个；可计算总市值 {_money(total_value) if total_value else 'data unavailable'}。",
        f"- 事实：未实现盈亏 {_money(unrealized) if _is_number(unrealized) else 'data unavailable'}。",
        f"- 事实：最大持仓是 {largest[0]}，市值 {_money(largest[1])}。" if largest else "- 事实：最大持仓 data unavailable。",
        f"- 判断：前 5 大持仓集中度 {concentration}，这是后续风险控制的重点。",
    ]


def _recent_trade_review_lines(
    recent_trades: list[dict[str, Any]],
    trade_performance: dict[int, dict[str, Any]],
) -> list[str]:
    if not recent_trades:
        return ["- 事实：暂无交易记录。"]

    lines = [f"- 事实：本次只复盘最近 {len(recent_trades)} 笔交易。"]
    for trade in recent_trades:
        perf = trade_performance.get(trade["id"], {})
        ticker_return = perf.get("ticker_return", "data unavailable")
        benchmark = perf.get("benchmark", "SPY")
        benchmark_return = perf.get("benchmark_return", "data unavailable")
        result = _relative_result(ticker_return, benchmark_return)
        judgment = _trade_judgment(trade, ticker_return, benchmark_return)
        lines.append(
            "- "
            f"{trade['trade_datetime']}：{trade['action']} {trade['ticker']} {trade['shares']:g} 股，"
            f"理由：{trade['reason'] or 'data unavailable'}。"
            f"交易后表现：{_percent_text(ticker_return)}；同期 {benchmark}：{_percent_text(benchmark_return)}。"
            f"判断：{result}，{judgment}。"
        )
    return lines


def _key_stock_lines(
    key_tickers: list[str],
    market_snapshot: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    news_by_ticker: dict[str, list[dict[str, Any]]],
) -> list[str]:
    if not key_tickers:
        return ["- 事实：暂无重点股票可检查。"]

    lines = []
    for ticker in key_tickers:
        snapshot = market_snapshot.get(ticker, {})
        metric = metrics.get(ticker, {})
        news = news_by_ticker.get(ticker, [])
        one_day = _percent_text(snapshot.get("one_day_percent", "data unavailable"))
        five_day = _percent_text(snapshot.get("five_day_percent", "data unavailable"))
        lines.append(f"- {ticker}：近期表现 1D {one_day}，5D {five_day}。")
        lines.append(f"  - 事实：{_news_summary(news)}")
        lines.append(f"  - 判断：{_thesis_change_text(metric)}")
        lines.append(f"  - 建议：{_stock_conclusion(snapshot, metric, news)}")
    return lines


def _behavior_lines(
    recent_trades: list[dict[str, Any]],
    holdings: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
    trade_performance: dict[int, dict[str, Any]],
) -> list[str]:
    if not recent_trades:
        return ["- 判断：交易记录不足，暂不能诊断行为模式。"]

    issues = []
    unclear_reason = [trade for trade in recent_trades if len(str(trade["reason"]).strip()) < 12]
    short_term = [trade for trade in recent_trades if trade["horizon"] == "short-term"]
    low_confidence = [trade for trade in recent_trades if int(trade["confidence"]) <= 2]
    repeated_tickers = _repeated_recent_tickers(recent_trades)
    concentration = _holding_concentration(holdings, market_snapshot)
    early_sells = [
        trade
        for trade in recent_trades
        if trade["action"] == "sell" and _trade_outperformed_after_action(trade, trade_performance)
    ]
    weak_buys = [
        trade
        for trade in recent_trades
        if trade["action"] == "buy" and _trade_underperformed_after_action(trade, trade_performance)
    ]

    if unclear_reason:
        tickers = ", ".join(trade["ticker"] for trade in unclear_reason[:3])
        issues.append(f"- 判断：交易理由偏短或不清楚，涉及 {tickers}。下一次要写清楚触发条件和失效条件。")
    if early_sells:
        tickers = ", ".join(trade["ticker"] for trade in early_sells[:3])
        issues.append(f"- 判断：可能存在卖出过早，涉及 {tickers}；这些卖出后标的仍跑赢基准。")
    if weak_buys:
        tickers = ", ".join(trade["ticker"] for trade in weak_buys[:3])
        issues.append(f"- 判断：部分买入后跑输基准，涉及 {tickers}；需要复查是否追高或忽略估值。")
    if repeated_tickers or len(recent_trades) >= RECENT_TRADE_LIMIT:
        issues.append("- 判断：近期交易频率偏高，需要警惕 overtrading。")
    if short_term and low_confidence:
        issues.append("- 判断：存在低信心短线交易，可能是 FOMO 或追涨。")
    elif short_term:
        issues.append("- 判断：短线交易较多，需要确认是否在用短期价格波动改变长期 thesis。")
    if _is_number(concentration) and float(concentration) > 70:
        issues.append("- 判断：前 5 大持仓集中度较高，需要警惕 oversizing。")
    if not issues:
        issues.append("- 判断：最近 5 笔交易没有明显的低信心、理由缺失或过度集中信号。")

    return issues[:3]


def _next_action_lines(recent_trades: list[dict[str, Any]]) -> list[str]:
    actions = [
        "- 建议：下一笔交易前，先写一句清楚的交易理由和一句失效条件。",
        "- 建议：如果是短线交易，先确认它不是因为 FOMO、追高或临时情绪。",
        "- 建议：买入或加仓前，先检查这笔交易是否会让单一股票或前 5 大持仓过度集中。",
    ]
    if recent_trades and any(not trade["risk_note"] for trade in recent_trades):
        actions[0] = "- 建议：下一笔交易前，必须补充风险备注和退出条件。"
    return actions


def _key_tickers(
    holdings: list[dict[str, Any]],
    recent_trades: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
) -> list[str]:
    selected = []
    selected.extend(trade["ticker"] for trade in recent_trades)
    top_holdings = _top_holdings_by_value(holdings, market_snapshot, limit=3)
    if top_holdings:
        selected.extend(ticker for ticker, _ in top_holdings)
    else:
        selected.extend(holding["ticker"] for holding in holdings[:3])
    selected.extend(
        ticker
        for ticker, snapshot in market_snapshot.items()
        if _is_number(snapshot.get("one_day_percent")) and abs(float(snapshot["one_day_percent"])) >= 5
    )
    return sorted(dict.fromkeys(selected))


def _top_holdings_by_value(
    holdings: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
    limit: int,
) -> list[tuple[str, float]]:
    rows = []
    for holding in holdings:
        price = market_snapshot.get(holding["ticker"], {}).get("current_price")
        if _is_number(price):
            rows.append((holding["ticker"], float(holding["shares"]) * float(price)))
    return sorted(rows, key=lambda row: row[1], reverse=True)[:limit]


def _relative_result(ticker_return: Any, benchmark_return: Any) -> str:
    if not (_is_number(ticker_return) and _is_number(benchmark_return)):
        return "数据不足，暂不能判断是否跑赢基准"
    return "跑赢基准" if float(ticker_return) >= float(benchmark_return) else "跑输基准"


def _trade_judgment(trade: dict[str, Any], ticker_return: Any, benchmark_return: Any) -> str:
    if not (_is_number(ticker_return) and _is_number(benchmark_return)):
        return "too early to judge"
    outperformed = float(ticker_return) >= float(benchmark_return)
    if trade["action"] == "buy":
        return "right" if outperformed else "wrong"
    return "right" if not outperformed else "too early to judge"


def _trade_outperformed_after_action(
    trade: dict[str, Any],
    trade_performance: dict[int, dict[str, Any]],
) -> bool:
    perf = trade_performance.get(trade["id"], {})
    ticker_return = perf.get("ticker_return", "data unavailable")
    benchmark_return = perf.get("benchmark_return", "data unavailable")
    return _is_number(ticker_return) and _is_number(benchmark_return) and float(ticker_return) > float(benchmark_return)


def _trade_underperformed_after_action(
    trade: dict[str, Any],
    trade_performance: dict[int, dict[str, Any]],
) -> bool:
    perf = trade_performance.get(trade["id"], {})
    ticker_return = perf.get("ticker_return", "data unavailable")
    benchmark_return = perf.get("benchmark_return", "data unavailable")
    return _is_number(ticker_return) and _is_number(benchmark_return) and float(ticker_return) < float(benchmark_return)


def _news_summary(news: list[dict[str, Any]]) -> str:
    if not news:
        return "no reliable news found"
    headlines = [item.get("headline", "").strip() for item in news if item.get("headline")]
    if not headlines:
        return "no reliable news found"
    return "相关新闻：" + "；".join(headlines[:2])


def _thesis_change_text(metric: dict[str, Any]) -> str:
    forward_pe = metric.get("forward_pe", "data unavailable")
    revenue_growth = metric.get("revenue_growth", "data unavailable")
    if _is_number(forward_pe) and float(forward_pe) > 60:
        return f"估值偏高，forward P/E 约 {float(forward_pe):.1f}，需要重新检查原始 thesis。"
    if _is_number(revenue_growth) and float(revenue_growth) < 0:
        return f"收入增长为负，约 {float(revenue_growth):.2f}，可能影响原始 thesis。"
    return "没有可靠数据表明原始 thesis 已明显改变；若关键数据缺失，应继续观察。"


def _stock_conclusion(snapshot: dict[str, Any], metric: dict[str, Any], news: list[dict[str, Any]]) -> str:
    one_day = snapshot.get("one_day_percent", "data unavailable")
    forward_pe = metric.get("forward_pe", "data unavailable")
    if _is_number(one_day) and abs(float(one_day)) >= 5:
        return "needs review"
    if _is_number(forward_pe) and float(forward_pe) > 60:
        return "reduce risk"
    if not news:
        return "watch"
    return "hold"


def _repeated_recent_tickers(recent_trades: list[dict[str, Any]]) -> set[str]:
    counts: dict[str, int] = {}
    for trade in recent_trades:
        counts[trade["ticker"]] = counts.get(trade["ticker"], 0) + 1
    return {ticker for ticker, count in counts.items() if count >= 2}


def _holding_concentration(
    holdings: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
) -> float | None:
    rows = _top_holdings_by_value(holdings, market_snapshot, limit=999)
    total = sum(value for _, value in rows)
    if not total:
        return None
    return sum(value for _, value in rows[:5]) / total * 100


def _top_concentration(rows: list[tuple[str, float | None]], total_value: float) -> str:
    if not total_value:
        return "data unavailable"
    values = sorted((value for _, value in rows if value is not None), reverse=True)
    top_five = sum(values[:5])
    return _percent_text((top_five / total_value) * 100)


def _percent_text(value: Any) -> str:
    if not _is_number(value):
        return "data unavailable"
    return f"{float(value):+.2f}%"


def _money(value: Any) -> str:
    if not _is_number(value):
        return "data unavailable"
    return f"${float(value):,.2f}"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
