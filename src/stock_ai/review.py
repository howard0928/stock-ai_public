from __future__ import annotations

from datetime import datetime
from typing import Any

from stock_ai import portfolio_db


RECENT_TRADE_LIMIT = 5
KEY_STOCK_LIMIT = 6
BENCHMARK_TICKERS = {"SPY", "QQQ"}


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
    status = [f"- 事实：当前持仓 {len(holdings)} 个。"]
    if total_value:
        status[0] += f"总市值 {_money(total_value)}。"
    if _is_number(unrealized):
        status.append(f"- 事实：未实现盈亏 {_money(unrealized)}。")
    if largest:
        status.append(f"- 事实：最大持仓是 {largest[0]}，市值 {_money(largest[1])}。")
    if concentration != "data unavailable":
        status.append(f"- 判断：前 5 大持仓集中度 {concentration}，需要持续控制单一方向风险。")
    return status


def _recent_trade_review_lines(
    recent_trades: list[dict[str, Any]],
    trade_performance: dict[int, dict[str, Any]],
) -> list[str]:
    if not recent_trades:
        return ["- 事实：暂无交易记录。"]

    groups = _trade_groups(recent_trades)
    group_note = f"，合并为 {len(groups)} 组" if len(groups) != len(recent_trades) else ""
    lines = [f"- 事实：本次只复盘最近 {len(recent_trades)} 笔交易{group_note}。"]
    for group in groups:
        lines.append(_trade_group_line(group, trade_performance))
    return lines


def _trade_groups(recent_trades: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
    groups_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for trade in recent_trades:
        key = (_trade_date(trade["trade_datetime"]), trade["ticker"])
        groups_by_key.setdefault(key, []).append(trade)
    return sorted(
        groups_by_key.values(),
        key=lambda trades: max(_trade_sort_key(trade["trade_datetime"]) for trade in trades),
        reverse=True,
    )


def _trade_group_line(group: list[dict[str, Any]], trade_performance: dict[int, dict[str, Any]]) -> str:
    latest_trade = max(group, key=lambda trade: _trade_sort_key(trade["trade_datetime"]))
    ticker = latest_trade["ticker"]
    date_text = _format_trade_date(latest_trade["trade_datetime"])
    time_range = _trade_time_range(group)
    action_text = _group_action_text(group)
    reasons = _group_reasons(group)
    performance_text = _group_performance_sentence(group, trade_performance)
    return f"- {date_text}{time_range}：{ticker}，{action_text}。理由：{reasons}。{performance_text}"


def _group_action_text(group: list[dict[str, Any]]) -> str:
    parts = []
    for action in ("buy", "sell"):
        action_trades = [trade for trade in group if trade["action"] == action]
        if not action_trades:
            continue
        shares = sum(float(trade["shares"]) for trade in action_trades)
        gross = sum(float(trade["shares"]) * float(trade["price"]) for trade in action_trades)
        avg_price = gross / shares if shares else 0
        total_fees = sum(float(trade["fees"]) for trade in action_trades)
        fee_text = f"，手续费 {_money(total_fees)}" if total_fees else ""
        parts.append(f"{_action_text(action)} {shares:g} 股，均价 {_money(avg_price)}{fee_text}")
    return "；".join(parts)


def _group_reasons(group: list[dict[str, Any]]) -> str:
    reasons = []
    for trade in sorted(group, key=lambda item: _trade_sort_key(item["trade_datetime"])):
        reason = _clean_sentence(trade["reason"] or "")
        if reason and reason not in reasons:
            reasons.append(reason)
    return "；".join(reasons[:2]) if reasons else "未记录明确理由"


def _group_performance_sentence(group: list[dict[str, Any]], trade_performance: dict[int, dict[str, Any]]) -> str:
    comparable = []
    for trade in group:
        perf = trade_performance.get(trade["id"], {})
        ticker_return = perf.get("ticker_return", "data unavailable")
        benchmark_return = perf.get("benchmark_return", "data unavailable")
        if _is_number(ticker_return) and _is_number(benchmark_return):
            comparable.append((trade, perf, float(ticker_return), float(benchmark_return)))
    if not comparable:
        return "交易刚发生或数据不足，暂不评价表现。"

    trade, perf, ticker_return, benchmark_return = max(
        comparable,
        key=lambda item: _trade_sort_key(item[0]["trade_datetime"]),
    )
    benchmark = perf.get("benchmark", "SPY")
    result = _relative_result(ticker_return, benchmark_return)
    judgment = _trade_judgment(trade, ticker_return, benchmark_return)
    if len(comparable) != len(group):
        coverage = f"可比较 {len(comparable)}/{len(group)} 笔；"
    else:
        coverage = ""
    return (
        f"{coverage}最近一笔表现 {_percent_text(ticker_return)}，同期 {benchmark} "
        f"{_percent_text(benchmark_return)}；{result}，{judgment}。"
    )


def _trade_time_range(group: list[dict[str, Any]]) -> str:
    times = [_format_trade_time(trade["trade_datetime"]) for trade in group]
    times = [time for time in times if time]
    if not times:
        return ""
    first = min(times)
    last = max(times)
    if first == last:
        return f" {first}"
    return f" {first}-{last}"


def _trade_date(value: str) -> str:
    return value.split("T", 1)[0].split(" ", 1)[0]


def _trade_sort_key(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.min


def _format_trade_date(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%m-%d")
    except ValueError:
        return _trade_date(value)


def _format_trade_time(value: str) -> str:
    try:
        return datetime.fromisoformat(value).strftime("%H:%M")
    except ValueError:
        return ""


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
        performance_text = _stock_performance_text(snapshot)
        parts = [f"- {ticker}：{performance_text}"]
        news_text = _news_summary(news)
        if news_text:
            parts.append(f"新闻：{news_text}")
        thesis_text = _thesis_change_text(metric)
        if thesis_text:
            parts.append(f"判断：{thesis_text}")
        parts.append(f"结论：{_stock_conclusion(snapshot, metric, news)}。")
        lines.append("；".join(parts))
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

    if repeated_tickers:
        tickers = ", ".join(sorted(repeated_tickers)[:3])
        issues.append(f"- 判断：近期反复交易 {tickers}，说明决策还不够稳定；下次加减仓前先写清楚触发条件。")
    if unclear_reason:
        tickers = ", ".join(trade["ticker"] for trade in unclear_reason[:3])
        issues.append(f"- 判断：交易理由偏短或不清楚，涉及 {tickers}。下一次要写清楚触发条件和失效条件。")
    if early_sells:
        tickers = ", ".join(trade["ticker"] for trade in early_sells[:3])
        issues.append(f"- 判断：可能存在卖出过早，涉及 {tickers}；这些卖出后标的仍跑赢基准。")
    if weak_buys:
        tickers = ", ".join(trade["ticker"] for trade in weak_buys[:3])
        issues.append(f"- 判断：部分买入后跑输基准，涉及 {tickers}；需要复查是否追高或忽略估值。")
    if len(recent_trades) >= RECENT_TRADE_LIMIT:
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
    repeated_tickers = _repeated_recent_tickers(recent_trades)
    if repeated_tickers:
        tickers = ", ".join(sorted(repeated_tickers)[:3])
        return [
            f"- 建议：下一次交易 {tickers} 前，先写清楚加仓/减仓触发条件。",
            "- 建议：同一天连续买卖同一方向股票时，先停一分钟检查是不是情绪交易。",
            "- 建议：买入或加仓前，先确认这笔交易不会让前 5 大持仓继续过度集中。",
        ]
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
    holding_tickers = {holding["ticker"] for holding in holdings}
    selected.extend(trade["ticker"] for trade in recent_trades if trade["ticker"] not in BENCHMARK_TICKERS)
    top_holdings = _top_holdings_by_value(holdings, market_snapshot, limit=3)
    if top_holdings:
        selected.extend(ticker for ticker, _ in top_holdings if ticker not in BENCHMARK_TICKERS)
    else:
        selected.extend(holding["ticker"] for holding in holdings[:3] if holding["ticker"] not in BENCHMARK_TICKERS)
    selected.extend(
        ticker
        for ticker, snapshot in market_snapshot.items()
        if ticker in holding_tickers
        if ticker not in BENCHMARK_TICKERS
        if _is_number(snapshot.get("one_day_percent")) and abs(float(snapshot["one_day_percent"])) >= 5
    )
    ordered = list(dict.fromkeys(selected))
    return ordered[:KEY_STOCK_LIMIT]


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
        return "表现数据不足"
    return "跑赢基准" if float(ticker_return) >= float(benchmark_return) else "跑输基准"


def _trade_judgment(trade: dict[str, Any], ticker_return: Any, benchmark_return: Any) -> str:
    if not (_is_number(ticker_return) and _is_number(benchmark_return)):
        return "暂不评价"
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
        return ""
    headlines = [item.get("headline", "").strip() for item in news if item.get("headline")]
    if not headlines:
        return ""
    return "；".join(headlines[:2])


def _thesis_change_text(metric: dict[str, Any]) -> str:
    forward_pe = metric.get("forward_pe", "data unavailable")
    revenue_growth = metric.get("revenue_growth", "data unavailable")
    if _is_number(forward_pe) and float(forward_pe) > 60:
        return f"估值偏高，forward P/E 约 {float(forward_pe):.1f}，需要重新检查原始 thesis。"
    if _is_number(revenue_growth) and float(revenue_growth) < 0:
        return f"收入增长为负，约 {float(revenue_growth):.2f}，可能影响原始 thesis。"
    return ""


def _stock_conclusion(snapshot: dict[str, Any], metric: dict[str, Any], news: list[dict[str, Any]]) -> str:
    one_day = snapshot.get("one_day_percent", "data unavailable")
    forward_pe = metric.get("forward_pe", "data unavailable")
    if _is_number(one_day) and abs(float(one_day)) >= 5:
        return "需要复盘"
    if _is_number(forward_pe) and float(forward_pe) > 60:
        return "降低风险"
    if not news:
        return "观察"
    return "持有"


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


def _stock_performance_text(snapshot: dict[str, Any]) -> str:
    one_day = snapshot.get("one_day_percent", "data unavailable")
    five_day = snapshot.get("five_day_percent", "data unavailable")
    pieces = []
    if _is_number(one_day):
        pieces.append(f"1D {_percent_text(one_day)}")
    if _is_number(five_day):
        pieces.append(f"5D {_percent_text(five_day)}")
    return "，".join(pieces) if pieces else "价格表现暂不可用"


def _money(value: Any) -> str:
    if not _is_number(value):
        return "data unavailable"
    return f"${float(value):,.2f}"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _action_text(action: str) -> str:
    if action == "buy":
        return "买入"
    if action == "sell":
        return "卖出"
    return action


def _clean_sentence(value: str) -> str:
    text = str(value).strip()
    while text.endswith(("。", ".", "；", ";")):
        text = text[:-1].strip()
    return text or "未记录明确理由"
