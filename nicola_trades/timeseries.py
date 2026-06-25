"""Time series aggregation across all ingested snapshots."""

import sqlite3
from datetime import date

import pandas as pd

from nicola_trades import funds as fund_map


def redemption_trend(
    conn: sqlite3.Connection,
    fund: str | None = None,
    start: date | None = None,
    end: date | None = None,
    tx_type: str = "Sell",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Return (pivot, raw) DataFrames.

    pivot: funds as rows, snapshot dates as columns, values = gross amount.
    raw:   one row per (snapshot_date, canonical_fund) with count + gross_amt.
    """
    query = """
        SELECT
            s.snapshot_date,
            t.canonical_fund,
            COUNT(*)       AS trade_count,
            SUM(t.gross_amt) AS gross_amt
        FROM trades t
        JOIN snapshots s ON s.id = t.snapshot_id
        WHERE t.tx_type = ?
    """
    params: list = [tx_type]

    if fund:
        query += " AND t.canonical_fund = ?"
        params.append(fund)
    if start:
        query += " AND s.snapshot_date >= ?"
        params.append(str(start))
    if end:
        query += " AND s.snapshot_date <= ?"
        params.append(str(end))

    query += " GROUP BY s.snapshot_date, t.canonical_fund ORDER BY s.snapshot_date, t.canonical_fund"

    raw = pd.read_sql_query(query, conn, params=params)
    if raw.empty:
        return pd.DataFrame(), raw

    raw["fund_group"] = raw["canonical_fund"].map(fund_map.group)

    pivot = raw.pivot_table(
        index=["fund_group", "canonical_fund"],
        columns="snapshot_date",
        values="gross_amt",
        aggfunc="sum",
    ).fillna(0)
    pivot.index.names = ["Fund Group", "Fund"]
    pivot.columns.name = None
    pivot = pivot.reset_index().sort_values(["Fund Group", "Fund"])

    return pivot, raw
