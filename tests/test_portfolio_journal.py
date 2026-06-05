from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_ai.journal_market import _return_since, _return_since_trade_price
from stock_ai.news import NewsItem, filter_relevant_company_news
from stock_ai.portfolio_db import (
    SnapshotHoldingInput,
    TransactionInput,
    add_transaction,
    create_snapshot,
    get_transaction,
    init_db,
    list_holdings,
    list_transactions,
    update_transaction,
)
from stock_ai.review import generate_review_report


class PortfolioJournalTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.tmp_dir.name) / "journal.sqlite3")
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmp_dir.cleanup()

    def test_buy_updates_holdings_and_saves_trade(self) -> None:
        add_transaction(
            self.db_path,
            TransactionInput(
                trade_datetime="2026-05-01T10:00",
                ticker="aapl",
                action="buy",
                shares=10,
                price=100,
                fees=5,
                reason="Long-term quality business",
                confidence=4,
                horizon="long-term",
                risk_note="Valuation risk",
            ),
        )

        holdings = list_holdings(self.db_path)
        trades = list_transactions(self.db_path)

        self.assertEqual(len(holdings), 1)
        self.assertEqual(holdings[0]["ticker"], "AAPL")
        self.assertEqual(holdings[0]["shares"], 10)
        self.assertEqual(holdings[0]["avg_cost"], 100.5)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["reason"], "Long-term quality business")

    def test_sell_updates_holdings_and_realized_gain_loss(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("MSFT", 10, 100, "Initial thesis")],
        )

        add_transaction(
            self.db_path,
            TransactionInput(
                trade_datetime="2026-05-02T10:00",
                ticker="MSFT",
                action="sell",
                shares=4,
                price=120,
                fees=2,
                reason="Trim after rally",
                confidence=3,
                horizon="medium-term",
                risk_note="May sell too early",
            ),
        )

        holdings = list_holdings(self.db_path)
        trades = list_transactions(self.db_path)

        self.assertEqual(holdings[0]["shares"], 6)
        self.assertEqual(holdings[0]["avg_cost"], 100)
        self.assertEqual(trades[0]["realized_gain_loss"], 78)

    def test_selling_more_than_current_shares_fails(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("NVDA", 2, 500, "")],
        )

        with self.assertRaises(ValueError):
            add_transaction(
                self.db_path,
                TransactionInput(
                    trade_datetime="2026-05-02T10:00",
                    ticker="NVDA",
                    action="sell",
                    shares=3,
                    price=600,
                    fees=0,
                    reason="Risk control",
                    confidence=3,
                    horizon="short-term",
                    risk_note="Position risk",
                ),
            )

        self.assertEqual(list_holdings(self.db_path)[0]["shares"], 2)
        self.assertEqual(list_transactions(self.db_path), [])

    def test_update_transaction_recalculates_holdings(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("MSFT", 10, 100, "Initial thesis")],
        )
        transaction_id = add_transaction(
            self.db_path,
            TransactionInput(
                trade_datetime="2026-05-02T10:00",
                ticker="MSFT",
                action="sell",
                shares=4,
                price=120,
                fees=2,
                reason="Trim after rally",
                confidence=3,
                horizon="medium-term",
                risk_note="May sell too early",
            ),
        )

        update_transaction(
            self.db_path,
            transaction_id,
            TransactionInput(
                trade_datetime="2026-05-03T11:30",
                ticker="MSFT",
                action="sell",
                shares=2,
                price=120,
                fees=2,
                reason="Corrected trim",
                confidence=4,
                horizon="medium-term",
                risk_note="Corrected risk note",
            ),
        )

        holding = list_holdings(self.db_path)[0]
        transaction = get_transaction(self.db_path, transaction_id)

        self.assertEqual(holding["shares"], 8)
        self.assertEqual(holding["avg_cost"], 100)
        self.assertEqual(transaction["trade_datetime"], "2026-05-03T11:30")
        self.assertEqual(transaction["reason"], "Corrected trim")
        self.assertEqual(transaction["realized_gain_loss"], 38)

    def test_missing_news_does_not_fabricate_news_or_clutter_report(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("AMZN", 1, 100, "Cloud and retail thesis")],
        )
        report, _ = generate_review_report(
            self.db_path,
            market_snapshot={"AMZN": {"current_price": "data unavailable"}},
            metrics={"AMZN": {}},
            news_by_ticker={"AMZN": []},
            trade_performance={},
        )

        self.assertNotIn("相关新闻", report)
        self.assertNotIn("no reliable news found", report)
        self.assertIn("价格表现暂不可用", report)

    def test_review_report_is_concise_and_recent_trade_focused(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("AAPL", 10, 100, "Initial thesis")],
        )
        for index in range(6):
            add_transaction(
                self.db_path,
                TransactionInput(
                    trade_datetime=f"2026-05-0{index + 2}T10:00",
                    ticker="AAPL",
                    action="buy",
                    shares=1,
                    price=100 + index,
                    fees=0,
                    reason=f"Reason {index + 1}",
                    confidence=3,
                    horizon="medium-term",
                    risk_note="Risk noted",
                ),
            )

        report, _ = generate_review_report(
            self.db_path,
            market_snapshot={
                "AAPL": {
                    "current_price": 110,
                    "one_day_percent": 1.2,
                    "five_day_percent": 4.5,
                }
            },
            metrics={"AAPL": {"forward_pe": 25}},
            news_by_ticker={"AAPL": []},
            trade_performance={
                trade["id"]: {"ticker_return": 1.0, "benchmark": "SPY", "benchmark_return": 0.5}
                for trade in list_transactions(self.db_path)
            },
        )

        self.assertIn("本次只复盘最近 5 笔交易", report)
        self.assertIn("Reason 6", report)
        self.assertNotIn("Reason 1", report)
        self.assertNotIn("现金", report)
        self.assertNotIn("revenue growth", report)
        self.assertIn("这不是财务建议，只是个人交易复盘辅助。", report)

    def test_review_report_groups_same_day_same_ticker_trades(self) -> None:
        create_snapshot(
            self.db_path,
            "2026-05-01",
            "Initial",
            "",
            [SnapshotHoldingInput("META", 10, 500, "Initial thesis")],
        )
        add_transaction(
            self.db_path,
            TransactionInput(
                trade_datetime="2026-06-05T10:00:00",
                ticker="META",
                action="buy",
                shares=1,
                price=590,
                fees=0.35,
                reason="Add after pullback",
                confidence=3,
                horizon="long-term",
                risk_note="AI risk",
            ),
        )
        add_transaction(
            self.db_path,
            TransactionInput(
                trade_datetime="2026-06-05T15:00:00",
                ticker="META",
                action="buy",
                shares=3,
                price=600,
                fees=0.35,
                reason="Add after pullback",
                confidence=3,
                horizon="long-term",
                risk_note="AI risk",
            ),
        )

        report, _ = generate_review_report(
            self.db_path,
            market_snapshot={
                "META": {
                    "current_price": 610,
                    "one_day_percent": 1.0,
                    "five_day_percent": 2.0,
                }
            },
            metrics={"META": {}},
            news_by_ticker={"META": []},
            trade_performance={},
        )

        self.assertIn("合并为 1 组", report)
        self.assertIn("META，买入 4 股，均价 $597.50，手续费 $0.70", report)
        self.assertEqual(report.count("Add after pullback"), 1)

    def test_news_filter_keeps_relevant_company_news(self) -> None:
        news = [
            NewsItem(
                headline="What's going on in today's session: S&P500 most active stocks",
                source="Example",
                summary="A broad list of active stocks.",
                url="https://example.com/movers",
                published_at=1,
            ),
            NewsItem(
                headline="Marvell shares rise after analyst raises price target",
                source="Example",
                summary="Analyst sees AI data center demand.",
                url="https://example.com/mrvl",
                published_at=2,
            ),
        ]

        filtered = filter_relevant_company_news("MRVL", news, limit=5)

        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].url, "https://example.com/mrvl")

    def test_trade_performance_can_use_actual_trade_price(self) -> None:
        data = pd.DataFrame({"Close": [110.0]})

        self.assertEqual(_return_since_trade_price(data, "AAPL", True, 100.0), 10.0)
        self.assertEqual(_return_since(data, "SPY", True, allow_single_point=True), 0.0)


if __name__ == "__main__":
    unittest.main()
