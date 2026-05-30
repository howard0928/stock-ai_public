from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

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

    def test_missing_news_does_not_fabricate_news(self) -> None:
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

        self.assertIn("no reliable news found", report)
        self.assertIn("data unavailable", report)

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


if __name__ == "__main__":
    unittest.main()
