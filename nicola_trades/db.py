import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "trades.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id            INTEGER PRIMARY KEY,
            file_name     TEXT    UNIQUE NOT NULL,
            snapshot_date DATE    NOT NULL,
            file_hash     TEXT    NOT NULL,
            ingested_at   DATETIME DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trades (
            id             INTEGER PRIMARY KEY,
            snapshot_id    INTEGER NOT NULL REFERENCES snapshots(id),
            wire_order_num TEXT    NOT NULL,
            tx_type        TEXT,
            investor_name  TEXT,
            sin            TEXT,
            fund_id        TEXT,
            canonical_fund TEXT,
            trade_date     DATE,
            settle_date    DATE,
            gross_amt      REAL,
            cdn_net_amt    REAL,
            usd_net_amt    REAL,
            shares_units   REAL,
            plan_desc      TEXT,
            UNIQUE(snapshot_id, wire_order_num)
        );

        CREATE INDEX IF NOT EXISTS idx_trades_snapshot ON trades(snapshot_id);
        CREATE INDEX IF NOT EXISTS idx_trades_wire     ON trades(wire_order_num);
        CREATE INDEX IF NOT EXISTS idx_trades_tx_type  ON trades(tx_type);
        CREATE INDEX IF NOT EXISTS idx_snapshots_date  ON snapshots(snapshot_date);
    """)
    conn.commit()
