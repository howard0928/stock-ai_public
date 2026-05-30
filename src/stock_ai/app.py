from __future__ import annotations

import subprocess
import sys
import tempfile
from datetime import date, datetime
from html import escape
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from stock_ai.config import Settings
from stock_ai.journal_market import load_fundamental_metrics, load_market_snapshot, load_trade_performance
from stock_ai.news import FinnhubNewsClient
from stock_ai.portfolio_db import (
    DEFAULT_DB_PATH,
    SnapshotHoldingInput,
    TransactionInput,
    add_transaction,
    create_snapshot,
    get_snapshot_holdings,
    init_db,
    latest_review_for_ticker,
    list_holdings,
    list_snapshots,
    list_transactions,
    update_transaction,
)
from stock_ai.review import generate_review_report


def _apply_industrial_theme() -> None:
    st.markdown(
        """
        <style>
        :root {
          --stock-bg: #000000;
          --stock-panel: #080A08;
          --stock-control: #10140F;
          --stock-border: #1B221D;
          --stock-border-strong: #334036;
          --stock-text: #F1F6F1;
          --stock-muted: #B8C2B6;
          --stock-positive: #00E676;
          --stock-negative: #FF3B30;
          --stock-warning: #FFB800;
          --stock-neutral: #D2D9D0;
        }

        html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
          background: var(--stock-bg);
          color: var(--stock-text);
        }

        .stApp, .stMarkdown, .stText, .stCaption, label, p, h1, h2, h3, h4, h5, h6,
        [data-testid="stWidgetLabel"], [data-testid="stSidebar"] * {
          font-family: "IBM Plex Mono", "JetBrains Mono", "Berkeley Mono", "SFMono-Regular", Consolas, monospace;
          font-variant-numeric: tabular-nums;
        }

        h1 {
          letter-spacing: 0;
          font-size: 1.65rem;
          border-bottom: 1px solid var(--stock-border);
          padding-bottom: 0.75rem;
          margin-bottom: 0.35rem;
        }

        h2, h3 {
          color: var(--stock-text);
          letter-spacing: 0;
          border-bottom: 1px solid var(--stock-border);
          padding-bottom: 0.35rem;
        }

        .stCaption, [data-testid="stCaptionContainer"], small {
          color: var(--stock-muted) !important;
        }

        label,
        label p,
        [data-testid="stWidgetLabel"],
        [data-testid="stWidgetLabel"] p,
        [data-testid="stCheckbox"] label,
        [data-testid="stCheckbox"] p,
        [data-testid="stNumberInput"] label,
        [data-testid="stNumberInput"] p,
        [data-testid="stTextInput"] label,
        [data-testid="stTextInput"] p,
        [data-testid="stTextArea"] label,
        [data-testid="stTextArea"] p,
        [data-testid="stSelectbox"] label,
        [data-testid="stSelectbox"] p,
        [data-testid="stSlider"] label,
        [data-testid="stSlider"] p {
          color: var(--stock-text) !important;
          opacity: 1 !important;
        }

        [data-testid="stMarkdownContainer"] p {
          color: var(--stock-text);
        }

        [data-testid="stSidebar"] {
          background: var(--stock-panel);
          border-right: 1px solid var(--stock-border);
        }

        div[data-testid="stVerticalBlockBorderWrapper"],
        div[data-testid="stForm"] {
          background: var(--stock-panel);
          border: 1px solid var(--stock-border);
          border-radius: 0;
          box-shadow: none;
        }

        div[data-testid="stMetric"] {
          background: var(--stock-panel);
          border: 1px solid var(--stock-border);
          border-radius: 0;
          padding: 0.65rem 0.75rem;
        }

        .stock-metric {
          background: var(--stock-panel);
          border: 1px solid var(--stock-border);
          padding: 0.75rem;
          min-height: 84px;
        }

        .stock-metric-label {
          color: var(--stock-muted);
          font-size: 0.72rem;
          line-height: 1.2;
          margin-bottom: 0.45rem;
          text-transform: uppercase;
        }

        .stock-metric-value {
          color: var(--stock-text);
          font-size: 1.1rem;
          line-height: 1.2;
          white-space: nowrap;
          overflow: hidden;
          text-overflow: ellipsis;
          font-variant-numeric: tabular-nums;
        }

        .stock-metric-value.positive { color: var(--stock-positive); }
        .stock-metric-value.negative { color: var(--stock-negative); }
        .stock-metric-value.warning { color: var(--stock-warning); }
        .stock-metric-value.neutral { color: var(--stock-neutral); }

        .section-shell {
          border: 1px solid var(--stock-border);
          background: var(--stock-panel);
          padding: 1rem;
          margin: 0.35rem 0 1rem;
        }

        .section-note {
          color: #E1E8E0;
          background: #10140F;
          border-left: 3px solid var(--stock-border-strong);
          padding: 0.45rem 0.65rem;
          font-size: 0.78rem;
          line-height: 1.45;
          margin: 0 0 0.9rem;
        }

        div[data-testid="stDataFrame"] {
          border: 1px solid var(--stock-border);
          background: var(--stock-panel);
        }

        div[data-testid="stDataFrame"] div {
          font-variant-numeric: tabular-nums;
        }

        button, [data-testid="stBaseButton-secondary"], [data-testid="stBaseButton-primary"] {
          background: var(--stock-control) !important;
          color: var(--stock-text) !important;
          border-radius: 5px !important;
          border: 1px solid var(--stock-border-strong) !important;
          font-family: "IBM Plex Mono", "JetBrains Mono", "Berkeley Mono", "SFMono-Regular", Consolas, monospace !important;
          font-variant-numeric: tabular-nums;
          box-shadow: none !important;
          transition: border-color 120ms ease, background-color 120ms ease, color 120ms ease;
        }

        button:hover, [data-testid="stBaseButton-secondary"]:hover, [data-testid="stBaseButton-primary"]:hover {
          background: #121A13 !important;
          border-color: var(--stock-positive) !important;
          color: var(--stock-positive) !important;
        }

        input, textarea, select, div[data-baseweb="select"] > div {
          background: var(--stock-control) !important;
          color: var(--stock-text) !important;
          border-color: var(--stock-border-strong) !important;
          border-radius: 5px !important;
          font-family: "IBM Plex Mono", "JetBrains Mono", "Berkeley Mono", "SFMono-Regular", Consolas, monospace !important;
          font-variant-numeric: tabular-nums;
        }

        input::placeholder, textarea::placeholder {
          color: var(--stock-muted) !important;
          opacity: 1 !important;
        }

        [data-baseweb="select"] span,
        [data-baseweb="select"] div {
          color: var(--stock-text) !important;
        }

        [data-testid="stNumberInput"] button {
          border-radius: 5px !important;
        }

        [data-testid="stAlert"] {
          background: var(--stock-control);
          border: 1px solid var(--stock-border-strong);
          color: var(--stock-text);
        }

        .terminal-report {
          background: var(--stock-panel);
          border: 1px solid var(--stock-border);
          padding: 1.1rem 1.25rem;
          max-width: 980px;
          line-height: 1.75;
        }

        .terminal-report h1,
        .terminal-report h2,
        .terminal-report h3 {
          border-bottom: 1px solid var(--stock-border);
          margin-top: 0.75rem;
        }

        div[data-baseweb="tab-list"] {
          border-bottom: 1px solid var(--stock-border);
          gap: 0.35rem;
        }

        button[data-baseweb="tab"] {
          border: 1px solid var(--stock-border-strong) !important;
          background: var(--stock-control) !important;
          border-radius: 5px 5px 0 0 !important;
          color: var(--stock-muted) !important;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
          background: #121A13 !important;
          color: var(--stock-positive) !important;
          border-color: var(--stock-positive) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _metric_card(column: Any, label: str, value: str, signal_value: float | None = None) -> None:
    signal_class = _signal_class(signal_value)
    column.markdown(
        f"""
        <div class="stock-metric">
          <div class="stock-metric-label">{escape(label)}</div>
          <div class="stock-metric-value {signal_class}">{escape(value)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    st.set_page_config(page_title="Stock AI Portfolio Journal", layout="wide")
    _apply_industrial_theme()
    st.title("个人投资组合日志与复盘")
    st.caption("本地持仓日志、交易记录和中文复盘。所有数据来自你的 SQLite、行情源或 API；缺失数据会明确显示。")

    db_path = st.sidebar.text_input("SQLite 文件", DEFAULT_DB_PATH)
    init_db(db_path)

    holdings = list_holdings(db_path)
    tickers = [holding["ticker"] for holding in holdings]
    market_snapshot = _cached_market_snapshot(tuple(tickers)) if tickers else {}

    _render_overview(holdings, market_snapshot)
    _render_holdings_table(holdings, market_snapshot)
    _render_single_stock_detail(db_path, holdings, market_snapshot)

    st.subheader("Actions")
    st.markdown('<div class="section-note">三个主操作分开处理，避免交易录入和报告阅读被压缩。</div>', unsafe_allow_html=True)
    large_move_tab, trade_tab, review_tab = st.tabs(["Check large moves", "Add latest trade", "Generate review report"])
    with large_move_tab:
        _render_large_move_button(db_path)
    with trade_tab:
        _render_trade_form(db_path)
    with review_tab:
        _render_review_button(db_path)

    with st.expander("Initial portfolio snapshot", expanded=False):
        _render_snapshot_form(db_path)


def _render_overview(holdings: list[dict[str, Any]], market_snapshot: dict[str, dict[str, Any]]) -> None:
    st.subheader("Portfolio status")
    total_value = 0.0
    total_cost = 0.0
    daily_pl = 0.0
    rows = []
    for holding in holdings:
        ticker = holding["ticker"]
        price = market_snapshot.get(ticker, {}).get("current_price")
        one_day = market_snapshot.get(ticker, {}).get("one_day_percent")
        if not _is_number(price):
            continue
        shares = float(holding["shares"])
        market_value = shares * float(price)
        total_value += market_value
        total_cost += shares * float(holding["avg_cost"])
        if _is_number(one_day):
            previous_value = market_value / (1 + float(one_day) / 100)
            daily_pl += market_value - previous_value
        rows.append((ticker, market_value))

    largest = max(rows, key=lambda item: item[1], default=None)
    top_five = sum(value for _, value in sorted(rows, key=lambda item: item[1], reverse=True)[:5])
    concentration = (top_five / total_value * 100) if total_value else None

    cols = st.columns(5)
    _metric_card(cols[0], "总市值", _money(total_value) if total_value else "data unavailable")
    _metric_card(cols[1], "日内盈亏", _money(daily_pl) if total_value else "data unavailable", daily_pl)
    _metric_card(cols[2], "未实现盈亏", _money(total_value - total_cost) if total_value else "data unavailable", total_value - total_cost)
    _metric_card(cols[3], "最大持仓", largest[0] if largest else "data unavailable")
    _metric_card(cols[4], "前 5 集中度", f"{concentration:.1f}%" if concentration is not None else "data unavailable")


def _render_holdings_table(holdings: list[dict[str, Any]], market_snapshot: dict[str, dict[str, Any]]) -> None:
    st.subheader("Holdings")
    st.markdown('<div class="section-note">核心持仓数据保持在一个可滚动表格里，便于快速比较 10-20 只股票。</div>', unsafe_allow_html=True)
    if not holdings:
        st.info("还没有持仓。先创建初始快照，或添加一笔买入交易。")
        return

    total_value = _portfolio_value(holdings, market_snapshot)
    table = []
    for holding in holdings:
        ticker = holding["ticker"]
        shares = float(holding["shares"])
        avg_cost = float(holding["avg_cost"])
        price = market_snapshot.get(ticker, {}).get("current_price", "data unavailable")
        market_value = shares * float(price) if _is_number(price) else "data unavailable"
        table.append(
            {
                "Ticker": ticker,
                "Shares": shares,
                "Avg cost": avg_cost,
                "Price": price,
                "Market value": market_value,
                "Weight %": (market_value / total_value * 100) if _is_number(market_value) and total_value else "data unavailable",
                "Unrealized P/L": (market_value - shares * avg_cost) if _is_number(market_value) else "data unavailable",
                "1D %": market_snapshot.get(ticker, {}).get("one_day_percent", "data unavailable"),
                "5D %": market_snapshot.get(ticker, {}).get("five_day_percent", "data unavailable"),
            }
        )
    st.dataframe(
        pd.DataFrame(table),
        use_container_width=True,
        hide_index=True,
        height=min(620, 72 + (len(table) + 1) * 36),
        column_config={
            "Ticker": st.column_config.TextColumn("Ticker", width="small"),
            "Shares": st.column_config.NumberColumn("Shares", format="%.4g", width="small"),
            "Avg cost": st.column_config.NumberColumn("Avg cost", format="$%.2f"),
            "Price": st.column_config.NumberColumn("Price", format="$%.2f"),
            "Market value": st.column_config.NumberColumn("Market value", format="$%.2f"),
            "Weight %": st.column_config.NumberColumn("Weight %", format="%.2f%%"),
            "Unrealized P/L": st.column_config.NumberColumn("Unrealized P/L", format="$%.2f"),
            "1D %": st.column_config.NumberColumn("1D %", format="%.2f%%"),
            "5D %": st.column_config.NumberColumn("5D %", format="%.2f%%"),
        },
    )


def _render_single_stock_detail(
    db_path: str,
    holdings: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
) -> None:
    st.subheader("Single-stock detail")
    if not holdings:
        st.info("暂无可查看的股票。")
        return

    selected = st.selectbox("选择 ticker", [holding["ticker"] for holding in holdings])
    holding = next(item for item in holdings if item["ticker"] == selected)
    price = market_snapshot.get(selected, {}).get("current_price", "data unavailable")
    market_value = float(holding["shares"]) * float(price) if _is_number(price) else "data unavailable"

    c1, c2, c3, c4 = st.columns(4)
    _metric_card(c1, "股数", f"{float(holding['shares']):g}")
    _metric_card(c2, "平均成本", _money(holding["avg_cost"]))
    _metric_card(c3, "当前价格", _money(price) if _is_number(price) else "data unavailable")
    _metric_card(c4, "市值", _money(market_value) if _is_number(market_value) else "data unavailable")

    recent_trades = list_transactions(db_path, ticker=selected, limit=10)
    detail_tabs = st.tabs(["Recent trades", "Reasons and thesis", "News and review"])
    with detail_tabs[0]:
        if recent_trades:
            st.dataframe(
                pd.DataFrame(recent_trades),
                use_container_width=True,
                hide_index=True,
                height=min(430, 72 + (len(recent_trades) + 1) * 36),
            )
        else:
            st.info("data unavailable")
    with detail_tabs[1]:
        st.markdown("**交易理由历史**")
        reasons = [trade["reason"] for trade in recent_trades if trade["reason"]]
        st.write("\n\n".join(f"- {reason}" for reason in reasons) if reasons else "data unavailable")

        st.markdown("**当前 thesis summary**")
        st.write(holding["current_thesis_summary"] or "data unavailable")
    with detail_tabs[2]:
        st.markdown("**最新相关新闻**")
        news = _load_news_for_ticker(selected)
        if news:
            for item in news:
                st.markdown(f"- [{item['headline']}]({item['url']}) ({item['source']})")
        else:
            st.write("no reliable news found")

        st.markdown("**最近复盘摘要**")
        latest_review = latest_review_for_ticker(db_path, selected)
        st.write(latest_review["report_markdown"][:800] + "..." if latest_review else "data unavailable")


def _render_large_move_button(db_path: str) -> None:
    st.markdown('<div class="section-note">复用已有 large-move report 逻辑，只把结果显示在当前页面。</div>', unsafe_allow_html=True)
    controls, output = st.columns([1, 2])
    with controls:
        threshold = st.number_input("波动阈值 %", min_value=0.1, value=5.0, step=0.5)
        dry_run = st.checkbox("Dry run", value=False)
        clicked = st.button("Check large moves", use_container_width=True)
    if not clicked:
        return

    holdings = list_holdings(db_path)
    if not holdings:
        st.error("没有当前持仓，无法检查大幅波动。")
        return

    try:
        html = _run_existing_large_move_report(holdings, threshold, dry_run)
    except Exception as exc:
        st.error(str(exc))
        return
    with output:
        st.components.v1.html(html, height=760, scrolling=True)


def _render_trade_form(db_path: str) -> None:
    st.markdown('<div class="section-note">录入一笔真实交易。Total fees 是整笔交易总手续费，不是每股费用。</div>', unsafe_allow_html=True)
    holdings_by_ticker = {holding["ticker"]: holding for holding in list_holdings(db_path)}
    with st.form("add_trade"):
        trade_col, context_col = st.columns([1, 1])
        with trade_col:
            st.markdown("**Trade execution**")
            default_trade_datetime = datetime.now()
            trade_date = st.date_input("Trade date", default_trade_datetime.date())
            trade_time = st.time_input("Trade time", default_trade_datetime.time().replace(second=0, microsecond=0))
            ticker = st.text_input("Ticker")
            action_col, shares_col = st.columns([1, 1])
            with action_col:
                action = st.selectbox("Action", ["buy", "sell"])
            with shares_col:
                shares = st.number_input("Shares", min_value=0.0, step=1.0)
            price_col, fees_col = st.columns([1, 1])
            with price_col:
                price = st.number_input("Price", min_value=0.0, step=1.0)
            with fees_col:
                fees = st.number_input("Total fees", min_value=0.0, value=0.0, step=1.0)
        with context_col:
            st.markdown("**Decision context**")
            confidence = st.slider("Confidence level", 1, 5, 3)
            horizon = st.selectbox("Intended holding period", ["short-term", "medium-term", "long-term"])
            reason = st.text_area("Trade reason", height=120)
            risk_note = st.text_area("Risk note", height=120)
            st.markdown("**Trade preview**")
            st.write(_trade_preview_text(holdings_by_ticker, ticker, action, shares, price, fees))
        submitted = st.form_submit_button("Add trade", use_container_width=True)

    if submitted:
        saved_trade_datetime = datetime.combine(trade_date, trade_time).isoformat(timespec="minutes")
        try:
            add_transaction(
                db_path,
                TransactionInput(
                    trade_datetime=saved_trade_datetime,
                    ticker=ticker,
                    action=action,
                    shares=shares,
                    price=price,
                    fees=fees,
                    reason=reason,
                    confidence=confidence,
                    horizon=horizon,
                    risk_note=risk_note,
                )
            )
        except ValueError as exc:
            st.error(str(exc))
        else:
            _cached_market_snapshot.clear()
            st.success(f"交易已保存，当前持仓已更新。Trade datetime: {saved_trade_datetime}")

    _render_transaction_editor(db_path)


def _render_transaction_editor(db_path: str) -> None:
    st.markdown("### Edit recent transactions")
    st.markdown('<div class="section-note">用于修正已录入交易。保存后会从初始快照和全部交易重新计算当前持仓。</div>', unsafe_allow_html=True)
    transactions = list_transactions(db_path, limit=25)
    if not transactions:
        st.info("暂无交易记录。")
        return

    options = {
        f"#{trade['id']} {trade['trade_datetime']} {trade['ticker']} {trade['action']} {trade['shares']:g} @ {_money(trade['price'])}": trade
        for trade in transactions
    }
    selected_label = st.selectbox("Select transaction to edit", list(options))
    selected = options[selected_label]
    parsed_dt = _parse_trade_datetime(selected["trade_datetime"])

    with st.form(f"edit_transaction_{selected['id']}"):
        edit_left, edit_right = st.columns([1, 1])
        with edit_left:
            edit_date = st.date_input("Edit trade date", parsed_dt.date())
            edit_time = st.time_input("Edit trade time", parsed_dt.time().replace(second=0, microsecond=0))
            edit_ticker = st.text_input("Edit ticker", selected["ticker"])
            edit_action = st.selectbox(
                "Edit action",
                ["buy", "sell"],
                index=0 if selected["action"] == "buy" else 1,
            )
            edit_shares = st.number_input("Edit shares", min_value=0.0, value=float(selected["shares"]), step=1.0)
            edit_price = st.number_input("Edit price", min_value=0.0, value=float(selected["price"]), step=1.0)
            edit_fees = st.number_input("Edit total fees", min_value=0.0, value=float(selected["fees"]), step=1.0)
        with edit_right:
            edit_confidence = st.slider("Edit confidence level", 1, 5, int(selected["confidence"]))
            horizons = ["short-term", "medium-term", "long-term"]
            edit_horizon = st.selectbox(
                "Edit intended holding period",
                horizons,
                index=horizons.index(selected["horizon"]) if selected["horizon"] in horizons else 1,
            )
            edit_reason = st.text_area("Edit trade reason", value=selected["reason"], height=120)
            edit_risk_note = st.text_area("Edit risk note", value=selected["risk_note"], height=120)
        submitted = st.form_submit_button("Save transaction edits", use_container_width=True)

    if not submitted:
        return

    edited_trade_datetime = datetime.combine(edit_date, edit_time).isoformat(timespec="minutes")
    try:
        update_transaction(
            db_path,
            int(selected["id"]),
            TransactionInput(
                trade_datetime=edited_trade_datetime,
                ticker=edit_ticker,
                action=edit_action,
                shares=edit_shares,
                price=edit_price,
                fees=edit_fees,
                reason=edit_reason,
                confidence=edit_confidence,
                horizon=edit_horizon,
                risk_note=edit_risk_note,
            ),
        )
    except ValueError as exc:
        st.error(str(exc))
        return
    _cached_market_snapshot.clear()
    st.success(f"交易已更新，当前持仓已重新计算。Trade datetime: {edited_trade_datetime}")


def _render_review_button(db_path: str) -> None:
    st.markdown('<div class="section-note">生成简洁中文交易复盘，重点看近期行为、重点股票和下一步。</div>', unsafe_allow_html=True)
    controls, report_col = st.columns([1, 2])
    with controls:
        benchmark = st.selectbox("比较基准", ["SPY", "QQQ"])
        clicked = st.button("Generate review", use_container_width=True)
    if not clicked:
        return

    holdings = list_holdings(db_path)
    transactions = list_transactions(db_path)
    tickers = sorted({row["ticker"] for row in holdings} | {row["ticker"] for row in transactions})
    market_snapshot = load_market_snapshot(tickers)
    metrics = load_fundamental_metrics(tickers)
    news_by_ticker = {ticker: _load_news_for_ticker(ticker) for ticker in tickers}
    trade_performance = {
        trade["id"]: load_trade_performance(trade["ticker"], trade["trade_datetime"], benchmark)
        for trade in transactions
    }
    data_status = _build_data_status(tickers, transactions, market_snapshot, metrics, news_by_ticker, trade_performance)
    report, _ = generate_review_report(db_path, market_snapshot, metrics, news_by_ticker, trade_performance)
    with report_col:
        _render_data_status(data_status)
        st.markdown('<div class="terminal-report">', unsafe_allow_html=True)
        st.markdown(report)
        st.markdown("</div>", unsafe_allow_html=True)
        st.download_button("下载 Markdown 报告", report, file_name="portfolio_review.md", use_container_width=True)


def _render_snapshot_form(db_path: str) -> None:
    st.markdown('<div class="section-note">低频设置：只在建立新起点时使用。</div>', unsafe_allow_html=True)
    with st.form("snapshot"):
        snapshot_date = st.date_input("Snapshot date", date.today())
        name = st.text_input("Name", "Initial portfolio snapshot")
        note = st.text_area("Note")
        st.caption("在表格里输入 ticker、shares、avg_cost、initial_thesis。")
        edited = st.data_editor(
            pd.DataFrame(
                [
                    {"ticker": "", "shares": 0.0, "avg_cost": 0.0, "initial_thesis": ""},
                ]
            ),
            num_rows="dynamic",
            use_container_width=True,
        )
        submitted = st.form_submit_button("Save initial snapshot", use_container_width=True)

    if submitted:
        rows = []
        for row in edited.to_dict("records"):
            if str(row.get("ticker", "")).strip():
                rows.append(
                    SnapshotHoldingInput(
                        ticker=str(row.get("ticker", "")),
                        shares=float(row.get("shares", 0) or 0),
                        avg_cost=float(row.get("avg_cost", 0) or 0),
                        initial_thesis=str(row.get("initial_thesis", "") or ""),
                    )
                )
        try:
            create_snapshot(db_path, snapshot_date.isoformat(), name, note, rows)
        except ValueError as exc:
            st.error(str(exc))
            return
        _cached_market_snapshot.clear()
        st.success("初始快照已保存，当前持仓已初始化。")

    snapshots = list_snapshots(db_path)
    if snapshots:
        st.markdown("**已有快照**")
        st.dataframe(pd.DataFrame(snapshots), use_container_width=True, hide_index=True)
        st.markdown("**快照持仓**")
        st.dataframe(pd.DataFrame(get_snapshot_holdings(db_path)), use_container_width=True, hide_index=True)


def _run_existing_large_move_report(holdings: list[dict[str, Any]], threshold: float, dry_run: bool) -> str:
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        holdings_csv = tmp_path / "holdings.csv"
        output_html = tmp_path / "large_move_report.html"
        pd.DataFrame(
            [{"ticker": holding["ticker"], "shares": holding["shares"]} for holding in holdings]
        ).to_csv(holdings_csv, index=False)
        command = [
            sys.executable,
            "-m",
            "stock_ai.cli",
            "--holdings",
            str(holdings_csv),
            "--output",
            str(output_html),
            "--threshold",
            str(threshold),
        ]
        if dry_run:
            command.append("--dry-run")
        result = subprocess.run(command, check=False, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip() or "Large-move report failed.")
        return output_html.read_text(encoding="utf-8")


def _load_news_for_ticker(ticker: str) -> list[dict[str, Any]]:
    settings = Settings.from_env()
    if not settings.finnhub_api_key:
        return []
    try:
        client = FinnhubNewsClient(settings.finnhub_api_key)
        return [item.__dict__ for item in client.company_news(ticker, days=7, limit=5)]
    except Exception:
        return []


@st.cache_data(ttl=900)
def _cached_market_snapshot(tickers: tuple[str, ...]) -> dict[str, dict[str, Any]]:
    return load_market_snapshot(list(tickers))


def _portfolio_value(holdings: list[dict[str, Any]], market_snapshot: dict[str, dict[str, Any]]) -> float:
    total = 0.0
    for holding in holdings:
        price = market_snapshot.get(holding["ticker"], {}).get("current_price")
        if _is_number(price):
            total += float(holding["shares"]) * float(price)
    return total


def _trade_preview_text(
    holdings_by_ticker: dict[str, dict[str, Any]],
    ticker: str,
    action: str,
    shares: float,
    price: float,
    fees: float,
) -> str:
    symbol = ticker.strip().upper()
    if not symbol or shares <= 0:
        return "输入 ticker 和 shares 后显示交易影响预览。"

    holding = holdings_by_ticker.get(symbol)
    current_shares = float(holding["shares"]) if holding else 0.0
    current_avg_cost = float(holding["avg_cost"]) if holding else 0.0
    if action == "sell" and shares > current_shares:
        return f"卖出会失败：当前只持有 {current_shares:g} 股。"
    if action == "buy":
        new_shares = current_shares + shares
        if new_shares == 0:
            return "data unavailable"
        new_avg_cost = ((current_shares * current_avg_cost) + (shares * price) + fees) / new_shares
        return f"买入后：{symbol} {current_shares:g} -> {new_shares:g} 股；新平均成本约 {_money(new_avg_cost)}。"

    new_shares = current_shares - shares
    realized = ((shares * price) - fees) - (shares * current_avg_cost)
    return f"卖出后：{symbol} {current_shares:g} -> {new_shares:g} 股；预计实现盈亏 {_money(realized)}。"


def _parse_trade_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now()


def _build_data_status(
    tickers: list[str],
    transactions: list[dict[str, Any]],
    market_snapshot: dict[str, dict[str, Any]],
    metrics: dict[str, dict[str, Any]],
    news_by_ticker: dict[str, list[dict[str, Any]]],
    trade_performance: dict[int, dict[str, Any]],
) -> dict[str, str]:
    price_count = sum(
        1
        for ticker in tickers
        if _is_number(market_snapshot.get(ticker, {}).get("current_price"))
    )
    benchmark_count = sum(
        1
        for trade in transactions
        if _is_number(trade_performance.get(trade["id"], {}).get("benchmark_return"))
    )
    news_count = sum(1 for ticker in tickers if news_by_ticker.get(ticker))
    metric_count = sum(
        1
        for ticker in tickers
        if any(value != "data unavailable" for value in metrics.get(ticker, {}).values())
    )
    total_tickers = len(tickers)
    total_trades = len(transactions)
    return {
        "Prices": f"{price_count}/{total_tickers} tickers available" if total_tickers else "no tickers",
        "Benchmark": f"{benchmark_count}/{total_trades} trades comparable" if total_trades else "no trades",
        "News": f"{news_count}/{total_tickers} tickers with news" if total_tickers else "no tickers",
        "Fundamentals": f"{metric_count}/{total_tickers} tickers with data" if total_tickers else "no tickers",
    }


def _render_data_status(data_status: dict[str, str]) -> None:
    st.markdown("**Data status**")
    cols = st.columns(len(data_status))
    for column, (label, value) in zip(cols, data_status.items()):
        _metric_card(column, label, value)


def _money(value: Any) -> str:
    if not _is_number(value):
        return "data unavailable"
    return f"${float(value):,.2f}"


def _signal_class(value: float | None) -> str:
    if value is None or not _is_number(value):
        return "neutral"
    if value > 0:
        return "positive"
    if value < 0:
        return "negative"
    return "neutral"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


if __name__ == "__main__":
    main()
