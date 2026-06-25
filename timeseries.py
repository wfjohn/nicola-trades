"""
Generate a time series trend report across all ingested snapshots.

Usage:
    python timeseries.py
    python timeseries.py --fund "Core Portfolio"
    python timeseries.py --from 2026-01-01 --to 2026-06-30
    python timeseries.py --output my_trend.xlsx
"""

import sys
from datetime import date
from pathlib import Path

import click

from nicola_trades import db
from nicola_trades import timeseries as ts
from nicola_trades import report

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "reports"


@click.command()
@click.option("--fund", "-f", default=None, help="Filter to a single canonical fund name.")
@click.option("--from", "start", default=None, help="Start date (YYYY-MM-DD).")
@click.option("--to",   "end",   default=None, help="End date (YYYY-MM-DD).")
@click.option(
    "--tx-type", "-t",
    default="Sell",
    show_default=True,
    help="Transaction type (Sell / Buy / all).",
)
@click.option("--output", "-o", default=None, help="Output Excel file path.")
def main(fund, start, end, tx_type, output):
    conn = db.connect()
    db.init(conn)

    d_start = date.fromisoformat(start) if start else None
    d_end   = date.fromisoformat(end)   if end   else None
    tx      = None if tx_type.lower() == "all" else tx_type

    click.echo(f"Building time series [tx_type={tx or 'all'}] ...")
    if fund:
        click.echo(f"  Fund filter: {fund}")

    pivot, raw = ts.redemption_trend(conn, fund=fund, start=d_start, end=d_end, tx_type=tx or "Sell")

    if raw.empty:
        click.echo("No data found. Check your filters or run ingest.py first.")
        conn.close()
        return

    dates = raw["snapshot_date"].nunique()
    funds = raw["canonical_fund"].nunique()
    click.echo(f"  {dates} snapshot dates × {funds} funds")

    if output is None:
        DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
        suffix = f"_{fund.replace(' ', '_')}" if fund else ""
        output = str(DEFAULT_OUTPUT_DIR / f"timeseries{suffix}.xlsx")

    out_path = report.write_timeseries(pivot, raw, Path(output))
    click.echo(f"\nReport saved to: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
