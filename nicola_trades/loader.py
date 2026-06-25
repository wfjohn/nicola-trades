import re
import hashlib
from datetime import date
from pathlib import Path

import pandas as pd

from nicola_trades import funds as fund_map

# Filename patterns: "Nwm Pending Trades 19-Jun-2026 (3).xlsx" or "...19-Jun-2026.xlsx"
_DATE_RE = re.compile(r"(\d{2}-[A-Za-z]{3}-\d{4})", re.IGNORECASE)
_NUM_RE  = re.compile(r"\((\d+)\)")

COLUMN_MAP = {
    "Wire Order #":  "wire_order_num",
    "Tx Type":       "tx_type",
    "Investor Name": "investor_name",
    "SIN":           "sin",
    "Fund ID":       "fund_id",
    "Trade Date":    "trade_date",
    "Settle Date":   "settle_date",
    "Gross Amt":     "gross_amt",
    "CDN$ Net Amt":  "cdn_net_amt",
    "USD$ Net Amt":  "usd_net_amt",
    "Shares/Units":  "shares_units",
    "Plan Desc.":    "plan_desc",
    "Fund Desc":     "fund_desc",
}


def file_hash(path: Path) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_date(filename: str) -> date | None:
    m = _DATE_RE.search(filename)
    if not m:
        return None
    return pd.to_datetime(m.group(1), format="%d-%b-%Y").date()


def version_number(filename: str) -> int:
    """Return the (N) suffix as an int; 0 if no suffix (base file)."""
    m = _NUM_RE.search(filename)
    return int(m.group(1)) if m else 0


def latest_per_date(paths: list[Path]) -> list[Path]:
    """
    Given a list of snapshot paths, keep only the most-recently-modified file
    for each calendar date so we don't double-ingest intraday saves.
    """
    by_date: dict[date, Path] = {}
    for p in paths:
        d = snapshot_date(p.name)
        if d is None:
            continue
        existing = by_date.get(d)
        if existing is None or p.stat().st_mtime > existing.stat().st_mtime:
            by_date[d] = p
    return list(by_date.values())


def load_file(path: Path) -> pd.DataFrame:
    """Parse a Pending Trades Excel file and return a normalised DataFrame."""
    # Some files have a PB_CACHE sheet first; find the actual data sheet by name.
    xl = pd.ExcelFile(path)
    sheet = next(
        (s for s in xl.sheet_names if "pending trades" in s.lower()),
        xl.sheet_names[-1],  # fall back to last sheet
    )
    df = xl.parse(sheet, dtype={"SIN": str, "Tax ID": str})

    # Keep only columns we need, rename to DB-friendly names
    keep = {k: v for k, v in COLUMN_MAP.items() if k in df.columns}
    df = df[list(keep.keys())].rename(columns=keep)

    # Resolve canonical fund name
    df["canonical_fund"] = df.apply(
        lambda r: fund_map.canonical(r["fund_id"], fallback=r.get("fund_desc", "")),
        axis=1,
    )
    df = df.drop(columns=["fund_desc"], errors="ignore")

    # Normalise dates to strings for SQLite
    for col in ("trade_date", "settle_date"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.strftime("%Y-%m-%d")

    df["sin"] = df["sin"].astype(str).str.strip()
    df["wire_order_num"] = df["wire_order_num"].astype(str).str.strip()

    return df
