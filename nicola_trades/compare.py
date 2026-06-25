"""Two-snapshot diff logic."""

import sqlite3
from datetime import date

import pandas as pd

from nicola_trades import funds as fund_map

TRADE_COLS = """
    t.wire_order_num, t.tx_type, t.investor_name, t.sin,
    t.fund_id, t.canonical_fund, t.trade_date, t.settle_date,
    t.gross_amt, t.cdn_net_amt, t.usd_net_amt, t.shares_units, t.plan_desc
"""


def _resolve_snapshot_id(conn: sqlite3.Connection, d: date) -> int:
    row = conn.execute(
        "SELECT id, file_name FROM snapshots WHERE snapshot_date = ? ORDER BY ingested_at DESC LIMIT 1",
        (str(d),),
    ).fetchone()
    if row is None:
        available = [
            r["snapshot_date"]
            for r in conn.execute("SELECT snapshot_date FROM snapshots ORDER BY snapshot_date")
        ]
        raise ValueError(
            f"No snapshot found for {d}.\n"
            f"Available dates: {', '.join(available) if available else '(none — run ingest.py first)'}"
        )
    return row["id"]


def _fetch(conn: sqlite3.Connection, snapshot_id: int, tx_type: str | None) -> pd.DataFrame:
    query = f"SELECT {TRADE_COLS} FROM trades t WHERE t.snapshot_id = ?"
    params: list = [snapshot_id]
    if tx_type:
        query += " AND t.tx_type = ?"
        params.append(tx_type)
    return pd.read_sql_query(query, conn, params=params)


def diff(
    conn: sqlite3.Connection,
    date1: date,
    date2: date,
    tx_type: str | None = "Sell",
) -> dict:
    """
    Compare two snapshots and return a dict with keys:
        date1, date2, all1, all2, removed, added, unchanged_count
    """
    id1 = _resolve_snapshot_id(conn, date1)
    id2 = _resolve_snapshot_id(conn, date2)

    df1 = _fetch(conn, id1, tx_type)
    df2 = _fetch(conn, id2, tx_type)

    ids1 = set(df1["wire_order_num"])
    ids2 = set(df2["wire_order_num"])

    removed = df1[df1["wire_order_num"].isin(ids1 - ids2)].copy()
    added   = df2[df2["wire_order_num"].isin(ids2 - ids1)].copy()

    # Add fund group column
    for df in (removed, added, df1, df2):
        df["fund_group"] = df["canonical_fund"].map(fund_map.group)

    return {
        "date1": date1,
        "date2": date2,
        "all1": df1,
        "all2": df2,
        "removed": removed.sort_values(["canonical_fund", "investor_name"]),
        "added":   added.sort_values(["canonical_fund", "investor_name"]),
        "unchanged_count": len(ids1 & ids2),
    }


def fund_summary(removed: pd.DataFrame, added: pd.DataFrame) -> pd.DataFrame:
    """Aggregate removed/added counts and amounts by canonical fund."""

    def agg(df: pd.DataFrame, label: str) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=["canonical_fund", f"{label}_count", f"{label}_gross"])
        return (
            df.groupby(["fund_group", "canonical_fund"])
            .agg(**{f"{label}_count": ("wire_order_num", "count"),
                    f"{label}_gross": ("gross_amt", "sum")})
            .reset_index()
        )

    rem = agg(removed, "removed")
    add = agg(added,   "added")

    summary = pd.merge(rem, add, on=["fund_group", "canonical_fund"], how="outer").fillna(0)
    summary["removed_count"] = summary["removed_count"].astype(int)
    summary["added_count"]   = summary["added_count"].astype(int)
    return summary.sort_values(["fund_group", "canonical_fund"])
