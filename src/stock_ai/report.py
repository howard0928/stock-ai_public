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
  <style>
    :root {{
      --bg: #000000;
      --panel: #080A08;
      --control: #10140F;
      --border: #1B221D;
      --border-strong: #334036;
      --text: #F1F6F1;
      --muted: #B8C2B6;
      --positive: #00E676;
      --negative: #FF3B30;
      --warning: #FFB800;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      padding: 20px;
      background: var(--bg);
      color: var(--text);
      font-family: "IBM Plex Mono", "JetBrains Mono", "SFMono-Regular", Consolas, monospace;
      font-variant-numeric: tabular-nums;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      background: var(--panel);
      border: 1px solid var(--border-strong);
    }}
    header {{
      padding: 22px 24px;
      border-bottom: 1px solid var(--border);
      background: #050705;
    }}
    h1, h2 {{
      margin: 0;
      letter-spacing: 0;
      color: var(--text);
    }}
    h1 {{ font-size: 23px; margin-bottom: 8px; }}
    h2 {{ font-size: 16px; margin-bottom: 12px; }}
    p {{ margin: 0; color: var(--muted); line-height: 1.5; }}
    a {{ color: var(--positive); text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .section {{
      padding: 20px 24px;
      border-bottom: 1px solid var(--border);
    }}
    .section:last-child {{ border-bottom: 0; }}
    .badge {{
      display: inline-block;
      margin: 0 0 12px;
      padding: 5px 8px;
      border: 1px solid var(--border-strong);
      color: var(--warning);
      background: var(--control);
      font-size: 12px;
      font-weight: 700;
    }}
    .summary {{
      line-height: 1.65;
      color: var(--text);
      border: 1px solid var(--border);
      background: #050705;
      padding: 12px 14px;
    }}
    .report-table {{
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }}
    .report-table th {{
      padding: 10px;
      text-align: left;
      color: var(--muted);
      border-bottom: 1px solid var(--border-strong);
      background: var(--control);
      font-size: 12px;
    }}
    .report-table td {{
      padding: 10px;
      border-top: 1px solid var(--border);
      color: var(--text);
      vertical-align: top;
    }}
    .ticker {{ font-weight: 700; color: var(--text); }}
    .positive {{ color: var(--positive) !important; font-weight: 700; }}
    .negative {{ color: var(--negative) !important; font-weight: 700; }}
    .news-list {{ margin: 0; padding-left: 20px; line-height: 1.55; }}
    .news-list li {{ margin: 6px 0; color: var(--muted); }}
    .empty {{ color: var(--muted); padding: 16px; }}
    .item-detail {{
      padding: 0 10px 16px !important;
      border-bottom: 1px solid var(--border);
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escape(title)}</h1>
      <p>{subtitle} Generated {escape(generated_at)}.</p>
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
            "<td colspan=\"6\" class=\"empty\">"
            f"No holdings moved more than {threshold_percent:.1f}% in the latest market session."
            "</td>"
            "</tr>"
        )

    return f"""
    <section class="section">
    <table class="report-table" role="presentation" cellspacing="0" cellpadding="0">
      <thead>
        <tr>
          <th>Ticker</th>
          <th>Move</th>
          <th>Previous Close</th>
          <th>Latest Close</th>
          <th>Shares</th>
          <th>Market Value</th>
        </tr>
      </thead>
      <tbody>
        {rows}
      </tbody>
    </table>
    </section>
"""


def _render_macro_report(report: MacroReport) -> str:
    summary_html = _render_summary(report.summary)
    move_rows = "\n".join(_render_macro_move(move) for move in report.moves)
    links = "".join(
        f'<li><a href="{escape(news.url)}">'
        f"{escape(news.headline)}</a> <span>({escape(news.source)})</span></li>"
        for news in report.news
    )
    if not links:
        links = '<li>No recent market news found.</li>'

    return f"""
    <section class="section">
      <div class="badge">今日触发市场宏观异动监控</div>
      <h2>Macro Brief</h2>
      <div class="summary">{summary_html}</div>
    </section>
    <section class="section">
      <h2>Moved Holdings Context</h2>
      <table class="report-table" role="presentation" cellspacing="0" cellpadding="0">
        <thead>
          <tr>
            <th>Ticker</th>
            <th>Move</th>
            <th>Latest Close</th>
            <th>Market Value</th>
          </tr>
        </thead>
        <tbody>{move_rows}</tbody>
      </table>
    </section>
    <section class="section">
      <h2>Market News Used</h2>
      <ul class="news-list">{links}</ul>
    </section>
"""


def _render_macro_move(move: StockMove) -> str:
    color_class = "positive" if move.change_percent >= 0 else "negative"
    return f"""
          <tr>
            <td class="ticker">{escape(move.ticker)}</td>
            <td class="{color_class}">{move.change_percent:+.2f}%</td>
            <td>${move.latest_close:,.2f}</td>
            <td>${move.market_value:,.2f}</td>
          </tr>
"""


def _render_item(item: ReportItem) -> str:
    move = item.move
    color_class = "positive" if move.change_percent >= 0 else "negative"
    links = "".join(
        f'<li><a href="{escape(news.url)}">'
        f"{escape(news.headline)}</a> <span>({escape(news.source)})</span></li>"
        for news in item.news
    )
    if not links:
        links = '<li>No recent news found.</li>'

    summary_html = _render_summary(item.summary)
    return f"""
<tr>
  <td class="ticker">{escape(move.ticker)}</td>
  <td class="{color_class}">{move.change_percent:+.2f}%</td>
  <td>${move.previous_close:,.2f}</td>
  <td>${move.latest_close:,.2f}</td>
  <td>{move.shares:g}</td>
  <td>${move.market_value:,.2f}</td>
</tr>
<tr>
  <td colspan="6" class="item-detail">
    <div class="summary">{summary_html}</div>
    <ul class="news-list">{links}</ul>
  </td>
</tr>
"""


def _render_summary(summary: str) -> str:
    return "<br>".join(escape(line) for line in summary.splitlines() if line.strip())
