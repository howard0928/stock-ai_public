from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from html import escape
from typing import TYPE_CHECKING

from stock_ai.market import StockMove

if TYPE_CHECKING:
    from stock_ai.news import NewsItem


@dataclass(frozen=True)
class ReportItem:
    move: StockMove
    news: list["NewsItem"]
    summary: str


@dataclass(frozen=True)
class MacroReport:
    moves: list[StockMove]
    news: list["NewsItem"]
    summary: str


def render_html_report(items: list[ReportItem], threshold_percent: float, macro_report: MacroReport | None = None) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
    content = _render_macro_report(macro_report) if macro_report else _render_stock_report(items, threshold_percent)
    subtitle = (
        "今日触发市场宏观异动监控。"
        if macro_report
        else f"Showing holdings with absolute moves of {threshold_percent:.1f}% or more."
    )
    title = "Market Macro Movement Monitor" if macro_report else "Daily Stock Movement Report"

    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Stock Movement Report</title>
</head>
<body style="margin:0;padding:24px;background:#f6f8fb;font-family:Arial,sans-serif;color:#111827;">
  <main style="max-width:920px;margin:0 auto;background:#ffffff;border:1px solid #e5e7eb;">
    <header style="padding:24px;border-bottom:1px solid #e5e7eb;">
      <h1 style="margin:0 0 8px;font-size:24px;">{escape(title)}</h1>
      <p style="margin:0;color:#4b5563;">{subtitle} Generated {escape(generated_at)}.</p>
    </header>
    {content}
  </main>
</body>
</html>
"""


def _render_stock_report(items: list[ReportItem], threshold_percent: float) -> str:
    rows = "\n".join(_render_item(item) for item in items)
    if not rows:
        rows = (
            "<tr>"
            "<td colspan=\"6\" style=\"padding:16px;border-top:1px solid #e5e7eb;\">"
            f"No holdings moved more than {threshold_percent:.1f}% in the latest market session."
            "</td>"
            "</tr>"
        )

    return f"""
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
      <thead>
        <tr style="background:#f9fafb;text-align:left;">
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Ticker</th>
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Move</th>
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Previous Close</th>
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Latest Close</th>
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Shares</th>
          <th style="padding:12px;border-bottom:1px solid #e5e7eb;">Market Value</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
"""


def _render_macro_report(report: MacroReport) -> str:
    summary_html = _render_summary(report.summary)
    move_rows = "\n".join(_render_macro_move(move) for move in report.moves)
    links = "".join(
        f'<li style="margin:4px 0;"><a href="{escape(news.url)}" style="color:#1d4ed8;">'
        f"{escape(news.headline)}</a> <span style=\"color:#6b7280;\">({escape(news.source)})</span></li>"
        for news in report.news
    )
    if not links:
        links = '<li style="margin:4px 0;color:#6b7280;">No recent market news found.</li>'

    return f"""
    <section style="padding:20px 24px;border-bottom:1px solid #e5e7eb;background:#f8fafc;">
      <div style="display:inline-block;margin:0 0 12px;padding:6px 10px;background:#eef2ff;color:#3730a3;font-weight:bold;font-size:13px;">
        今日触发市场宏观异动监控
      </div>
      <h2 style="margin:0 0 10px;font-size:18px;">Macro Brief</h2>
      <div style="line-height:1.55;color:#111827;">{summary_html}</div>
    </section>
    <section style="padding:20px 24px;border-bottom:1px solid #e5e7eb;">
      <h2 style="margin:0 0 12px;font-size:16px;">Moved Holdings Context</h2>
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border-collapse:collapse;">
        <thead>
          <tr style="background:#f9fafb;text-align:left;">
            <th style="padding:10px;border-bottom:1px solid #e5e7eb;">Ticker</th>
            <th style="padding:10px;border-bottom:1px solid #e5e7eb;">Move</th>
            <th style="padding:10px;border-bottom:1px solid #e5e7eb;">Latest Close</th>
            <th style="padding:10px;border-bottom:1px solid #e5e7eb;">Market Value</th>
          </tr>
        </thead>
        <tbody>{move_rows}</tbody>
      </table>
    </section>
    <section style="padding:20px 24px;">
      <h2 style="margin:0 0 10px;font-size:16px;">Market News Used</h2>
      <ul style="margin:0;padding-left:20px;">{links}</ul>
    </section>
"""


def _render_macro_move(move: StockMove) -> str:
    color = "#047857" if move.change_percent >= 0 else "#b91c1c"
    return f"""
          <tr>
            <td style="padding:10px;border-top:1px solid #e5e7eb;font-weight:bold;">{escape(move.ticker)}</td>
            <td style="padding:10px;border-top:1px solid #e5e7eb;color:{color};font-weight:bold;">{move.change_percent:+.2f}%</td>
            <td style="padding:10px;border-top:1px solid #e5e7eb;">${move.latest_close:,.2f}</td>
            <td style="padding:10px;border-top:1px solid #e5e7eb;">${move.market_value:,.2f}</td>
          </tr>
"""


def _render_item(item: ReportItem) -> str:
    move = item.move
    color = "#047857" if move.change_percent >= 0 else "#b91c1c"
    links = "".join(
        f'<li style="margin:4px 0;"><a href="{escape(news.url)}" style="color:#1d4ed8;">'
        f"{escape(news.headline)}</a> <span style=\"color:#6b7280;\">({escape(news.source)})</span></li>"
        for news in item.news
    )
    if not links:
        links = '<li style="margin:4px 0;color:#6b7280;">No recent news found.</li>'

    summary_html = _render_summary(item.summary)
    return f"""
<tr>
  <td style="padding:12px;border-top:1px solid #e5e7eb;font-weight:bold;">{escape(move.ticker)}</td>
  <td style="padding:12px;border-top:1px solid #e5e7eb;color:{color};font-weight:bold;">{move.change_percent:+.2f}%</td>
  <td style="padding:12px;border-top:1px solid #e5e7eb;">${move.previous_close:,.2f}</td>
  <td style="padding:12px;border-top:1px solid #e5e7eb;">${move.latest_close:,.2f}</td>
  <td style="padding:12px;border-top:1px solid #e5e7eb;">{move.shares:g}</td>
  <td style="padding:12px;border-top:1px solid #e5e7eb;">${move.market_value:,.2f}</td>
</tr>
<tr>
  <td colspan="6" style="padding:0 12px 18px;border-bottom:1px solid #e5e7eb;">
    <div style="margin:8px 0 10px;line-height:1.45;">{summary_html}</div>
    <ul style="margin:0;padding-left:20px;">{links}</ul>
  </td>
</tr>
"""


def _render_summary(summary: str) -> str:
    return "<br>".join(escape(line) for line in summary.splitlines() if line.strip())
