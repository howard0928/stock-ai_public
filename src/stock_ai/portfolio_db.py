from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = "portfolio_journal.sqlite3"


@dataclass(frozen=True)
class SnapshotHoldingInput:
    ticker: str
    shares: float
    avg_cost: float
    initial_thesis: str = ""


@dataclass(frozen=True)
class TransactionInput:
    trade_datetime: str
    ticker: str
    action: str
    shares: float
    price: float
    fees: float
    reason: str
    confidence: int
    horizon: str
    risk_note: str


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    with connect(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_datetime TEXT NOT NULL,
                name TEXT NOT NULL,
                note TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshot_holdings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                ticker TEXT NOT NULL,
                shares REAL NOT NULL,
                avg_cost REAL NOT NULL,
                initial_thesis TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY(snapshot_id) REFERENCES portfolio_snapshots(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_datetime TEXT NOT NULL,
                ticker TEXT NOT NULL,
                action TEXT NOT NULL,
                shares REAL NOT NULL,
                price REAL NOT NULL,
                fees REAL NOT NULL DEFAULT 0,
                reason TEXT NOT NULL DEFAULT '',
                confidence INTEGER NOT NULL,
                horizon TEXT NOT NULL,
                risk_note TEXT NOT NULL DEFAULT '',
                realized_gain_loss REAL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS holdings (
                ticker TEXT PRIMARY KEY,
                shares REAL NOT NULL,
                avg_cost REAL NOT NULL,
                current_thesis_summary TEXT NOT NULL DEFAULT '',
                manual_note TEXT NOT NULL DEFAULT '',
                thesis_updated_at TEXT,
                updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS review_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                generated_at TEXT NOT NULL,
                report_markdown TEXT NOT NULL,
                tickers_included TEXT NOT NULL,
                data_snapshot_json TEXT NOT NULL
            );
            """
        )


def create_snapshot(
    db_path: str | Path,
    snapshot_datetime: str,
    name: str,
    note: str,
    holdings: list[SnapshotHoldingInput],
) -> int:
    if not holdings:
        raise ValueError("At least one holding is required for a snapshot.")

    now = _now()
    clean_holdings = [_clean_snapshot_holding(holding) for holding in holdings]
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO portfolio_snapshots (snapshot_datetime, name, note, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (snapshot_datetime, name.strip() or "Initial snapshot", note.strip(), now),
        )
        snapshot_id = int(cursor.lastrowid)
        for holding in clean_holdings:
            conn.execute(
                """
                INSERT INTO snapshot_holdings
                    (snapshot_id, ticker, shares, avg_cost, initial_thesis, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    snapshot_id,
                    holding.ticker,
                    holding.shares,
                    holding.avg_cost,
                    holding.initial_thesis,
                    now,
                ),
            )
            conn.execute(
                """
                INSERT INTO holdings
                    (ticker, shares, avg_cost, current_thesis_summary, manual_note, thesis_updated_at, updated_at)
                VALUES (?, ?, ?, ?, '', ?, ?)
                ON CONFLICT(ticker) DO UPDATE SET
                    shares = excluded.shares,
                    avg_cost = excluded.avg_cost,
                    current_thesis_summary = excluded.current_thesis_summary,
                    thesis_updated_at = excluded.thesis_updated_at,
                    updated_at = excluded.updated_at
                """,
                (
                    holding.ticker,
                    holding.shares,
                    holding.avg_cost,
                    _initial_thesis_summary(holding.initial_thesis),
                    now,
                    now,
                ),
            )
        return snapshot_id


def add_transaction(db_path: str | Path, transaction: TransactionInput) -> int:
    trade = _clean_transaction(transaction)
    now = _now()
    with connect(db_path) as conn:
        current = conn.execute(
            "SELECT ticker, shares, avg_cost, manual_note FROM holdings WHERE ticker = ?",
            (trade.ticker,),
        ).fetchone()
        current_shares = float(current["shares"]) if current else 0.0
        current_avg_cost = float(current["avg_cost"]) if current else 0.0
        manual_note = str(current["manual_note"]) if current else ""

        if trade.action == "sell" and trade.shares > current_shares:
            raise ValueError(f"Cannot sell {trade.shares:g} shares of {trade.ticker}; only {current_shares:g} held.")

        realized_gain_loss: float | None = None
        if trade.action == "buy":
            new_shares = current_shares + trade.shares
            new_avg_cost = ((current_shares * current_avg_cost) + (trade.shares * trade.price) + trade.fees) / new_shares
        else:
            proceeds = (trade.shares * trade.price) - trade.fees
            cost_basis = trade.shares * current_avg_cost
            realized_gain_loss = proceeds - cost_basis
            new_shares = current_shares - trade.shares
            new_avg_cost = current_avg_cost if new_shares > 0 else 0.0

        cursor = conn.execute(
            """
            INSERT INTO transactions
                (trade_datetime, ticker, action, shares, price, fees, reason, confidence,
                 horizon, risk_note, realized_gain_loss, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade.trade_datetime,
                trade.ticker,
                trade.action,
                trade.shares,
                trade.price,
                trade.fees,
                trade.reason,
                trade.confidence,
                trade.horizon,
                trade.risk_note,
                realized_gain_loss,
                now,
            ),
        )
        transaction_id = int(cursor.lastrowid)
        thesis_summary = build_current_thesis_summary(conn, trade.ticker, manual_note)
        conn.execute(
            """
            INSERT INTO holdings
                (ticker, shares, avg_cost, current_thesis_summary, manual_note, thesis_updated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ticker) DO UPDATE SET
                shares = excluded.shares,
                avg_cost = excluded.avg_cost,
                current_thesis_summary = excluded.current_thesis_summary,
                manual_note = excluded.manual_note,
                thesis_updated_at = excluded.thesis_updated_at,
                updated_at = excluded.updated_at
            """,
            (trade.ticker, new_shares, new_avg_cost, thesis_summary, manual_note, now, now),
        )
        return transaction_id


def get_transaction(db_path: str | Path, transaction_id: int) -> dict[str, Any] | None:
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, trade_datetime, ticker, action, shares, price, fees, reason,
                   confidence, horizon, risk_note, realized_gain_loss, created_at
            FROM transactions
            WHERE id = ?
            """,
            (transaction_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_transaction(db_path: str | Path, transaction_id: int, transaction: TransactionInput) -> None:
    trade = _clean_transaction(transaction)
    with connect(db_path) as conn:
        existing = conn.execute("SELECT id FROM transactions WHERE id = ?", (transaction_id,)).fetchone()
        if not existing:
            raise ValueError(f"Transaction not found: {transaction_id}")

        conn.execute(
            """
            UPDATE transactions
            SET trade_datetime = ?,
                ticker = ?,
                action = ?,
                shares = ?,
                price = ?,
                fees = ?,
                reason = ?,
                confidence = ?,
                horizon = ?,
                risk_note = ?
            WHERE id = ?
            """,
            (
                trade.trade_datetime,
                trade.ticker,
                trade.action,
                trade.shares,
                trade.price,
                trade.fees,
                trade.reason,
                trade.confidence,
                trade.horizon,
                trade.risk_note,
                transaction_id,
            ),
        )
        _rebuild_holdings_from_history(conn)


def rebuild_holdings_from_history(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        _rebuild_holdings_from_history(conn)


def list_holdings(db_path: str | Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT ticker, shares, avg_cost, current_thesis_summary, manual_note, thesis_updated_at, updated_at
            FROM holdings
            WHERE shares > 0
            ORDER BY ticker
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_transactions(db_path: str | Path, ticker: str | None = None, limit: int | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT id, trade_datetime, ticker, action, shares, price, fees, reason,
               confidence, horizon, risk_note, realized_gain_loss, created_at
        FROM transactions
    """
    params: list[Any] = []
    if ticker:
        query += " WHERE ticker = ?"
        params.append(ticker.strip().upper())
    query += " ORDER BY trade_datetime DESC, id DESC"
    if limit:
        query += " LIMIT ?"
        params.append(limit)

    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def list_snapshots(db_path: str | Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, snapshot_datetime, name, note, created_at
            FROM portfolio_snapshots
            ORDER BY snapshot_datetime DESC, id DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_snapshot_holdings(db_path: str | Path, ticker: str | None = None) -> list[dict[str, Any]]:
    query = """
        SELECT sh.id, sh.snapshot_id, sh.ticker, sh.shares, sh.avg_cost, sh.initial_thesis, sh.created_at
        FROM snapshot_holdings sh
        JOIN portfolio_snapshots ps ON ps.id = sh.snapshot_id
    """
    params: list[Any] = []
    if ticker:
        query += " WHERE sh.ticker = ?"
        params.append(ticker.strip().upper())
    query += " ORDER BY ps.snapshot_datetime DESC, sh.id DESC"

    with connect(db_path) as conn:
        rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(row) for row in rows]


def save_review_report(
    db_path: str | Path,
    report_markdown: str,
    tickers: list[str],
    data_snapshot: dict[str, Any],
) -> int:
    generated_at = _now()
    with connect(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO review_reports
                (generated_at, report_markdown, tickers_included, data_snapshot_json)
            VALUES (?, ?, ?, ?)
            """,
            (
                generated_at,
                report_markdown,
                ",".join(sorted(set(tickers))),
                json.dumps(data_snapshot, ensure_ascii=False, default=str),
            ),
        )
        return int(cursor.lastrowid)


def latest_review_for_ticker(db_path: str | Path, ticker: str) -> dict[str, Any] | None:
    symbol = ticker.strip().upper()
    with connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT id, generated_at, report_markdown, tickers_included
            FROM review_reports
            WHERE tickers_included LIKE ?
            ORDER BY generated_at DESC, id DESC
            LIMIT 1
            """,
            (f"%{symbol}%",),
        ).fetchone()
    return _row_to_dict(row) if row else None


def build_current_thesis_summary(conn: sqlite3.Connection, ticker: str, manual_note: str = "") -> str:
    symbol = ticker.strip().upper()
    snapshot = conn.execute(
        """
        SELECT initial_thesis
        FROM snapshot_holdings
        WHERE ticker = ?
        ORDER BY id DESC
        LIMIT 1
        """,
        (symbol,),
    ).fetchone()
    trades = conn.execute(
        """
        SELECT action, reason, risk_note
        FROM transactions
        WHERE ticker = ?
        ORDER BY trade_datetime DESC, id DESC
        LIMIT 5
        """,
        (symbol,),
    ).fetchall()

    parts = []
    if snapshot and snapshot["initial_thesis"]:
        parts.append(f"初始观点：{snapshot['initial_thesis']}")
    trade_reasons = [
        f"{row['action']}：{row['reason']}"
        for row in trades
        if row["reason"]
    ]
    if trade_reasons:
        parts.append("近期交易理由：" + "；".join(trade_reasons))
    risks = [str(row["risk_note"]) for row in trades if row["risk_note"]]
    if risks:
        parts.append("主要风险：" + "；".join(risks[:3]))
    if manual_note:
        parts.append(f"手动备注：{manual_note}")
    return "\n".join(parts) if parts else "data unavailable"


def _rebuild_holdings_from_history(conn: sqlite3.Connection) -> None:
    snapshot = conn.execute(
        """
        SELECT id, snapshot_datetime
        FROM portfolio_snapshots
        ORDER BY snapshot_datetime DESC, id DESC
        LIMIT 1
        """
    ).fetchone()
    now = _now()
    manual_notes = {
        row["ticker"]: row["manual_note"]
        for row in conn.execute("SELECT ticker, manual_note FROM holdings")
    }
    positions: dict[str, dict[str, float]] = {}

    if snapshot:
        for row in conn.execute(
            """
            SELECT ticker, shares, avg_cost
            FROM snapshot_holdings
            WHERE snapshot_id = ?
            """,
            (snapshot["id"],),
        ):
            positions[row["ticker"]] = {
                "shares": float(row["shares"]),
                "avg_cost": float(row["avg_cost"]),
            }

    snapshot_datetime = str(snapshot["snapshot_datetime"]) if snapshot else ""
    trades = conn.execute(
        """
        SELECT id, trade_datetime, ticker, action, shares, price, fees
        FROM transactions
        ORDER BY trade_datetime, id
        """
    ).fetchall()
    for trade in trades:
        if snapshot_datetime and str(trade["trade_datetime"]) < snapshot_datetime:
            continue
        ticker = trade["ticker"]
        if ticker not in positions:
            positions[ticker] = {"shares": 0.0, "avg_cost": 0.0}

        shares = float(trade["shares"])
        price = float(trade["price"])
        fees = float(trade["fees"])
        current_shares = positions[ticker]["shares"]
        current_avg_cost = positions[ticker]["avg_cost"]

        if trade["action"] == "buy":
            new_shares = current_shares + shares
            new_avg_cost = ((current_shares * current_avg_cost) + (shares * price) + fees) / new_shares
            realized_gain_loss = None
        else:
            if shares > current_shares:
                raise ValueError(
                    f"Cannot rebuild holdings: transaction {trade['id']} sells {shares:g} shares "
                    f"of {ticker}, but only {current_shares:g} shares are available at that point."
                )
            proceeds = (shares * price) - fees
            cost_basis = shares * current_avg_cost
            realized_gain_loss = proceeds - cost_basis
            new_shares = current_shares - shares
            new_avg_cost = current_avg_cost if new_shares > 0 else 0.0

        positions[ticker] = {"shares": new_shares, "avg_cost": new_avg_cost}
        conn.execute(
            "UPDATE transactions SET realized_gain_loss = ? WHERE id = ?",
            (realized_gain_loss, trade["id"]),
        )

    conn.execute("DELETE FROM holdings")
    for ticker in sorted(positions):
        manual_note = manual_notes.get(ticker, "")
        conn.execute(
            """
            INSERT INTO holdings
                (ticker, shares, avg_cost, current_thesis_summary, manual_note, thesis_updated_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                ticker,
                positions[ticker]["shares"],
                positions[ticker]["avg_cost"],
                build_current_thesis_summary(conn, ticker, manual_note),
                manual_note,
                now,
                now,
            ),
        )


def _clean_snapshot_holding(holding: SnapshotHoldingInput) -> SnapshotHoldingInput:
    ticker = holding.ticker.strip().upper()
    if not ticker:
        raise ValueError("Ticker is required.")
    if holding.shares < 0:
        raise ValueError("Shares cannot be negative.")
    if holding.avg_cost < 0:
        raise ValueError("Average cost cannot be negative.")
    return SnapshotHoldingInput(
        ticker=ticker,
        shares=float(holding.shares),
        avg_cost=float(holding.avg_cost),
        initial_thesis=holding.initial_thesis.strip(),
    )


def _clean_transaction(transaction: TransactionInput) -> TransactionInput:
    ticker = transaction.ticker.strip().upper()
    action = transaction.action.strip().lower()
    if not ticker:
        raise ValueError("Ticker is required.")
    if action not in {"buy", "sell"}:
        raise ValueError("Action must be buy or sell.")
    if transaction.shares <= 0:
        raise ValueError("Shares must be greater than zero.")
    if transaction.price < 0:
        raise ValueError("Price cannot be negative.")
    if transaction.fees < 0:
        raise ValueError("Fees cannot be negative.")
    if transaction.confidence < 1 or transaction.confidence > 5:
        raise ValueError("Confidence must be between 1 and 5.")

    return TransactionInput(
        trade_datetime=transaction.trade_datetime.strip() or _now(),
        ticker=ticker,
        action=action,
        shares=float(transaction.shares),
        price=float(transaction.price),
        fees=float(transaction.fees),
        reason=transaction.reason.strip(),
        confidence=int(transaction.confidence),
        horizon=transaction.horizon.strip(),
        risk_note=transaction.risk_note.strip(),
    )


def _initial_thesis_summary(initial_thesis: str) -> str:
    return f"初始观点：{initial_thesis.strip()}" if initial_thesis.strip() else "data unavailable"


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
