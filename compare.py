"""
Compare pending trades between two snapshot dates.

Usage:
    python compare.py --date1 2026-06-12 --date2 2026-06-19
    python compare.py --date1 2026-06-12 --date2 2026-06-19 --tx-type Sell
    python compare.py --date1 2026-06-12 --date2 2026-06-19 --output my_report.xlsx
    python compare.py --list-dates
"""

import sys
from datetime import date
from pathlib import Path

import click

from nicola_trades import db
from nicola_trades import compare as cmp
from nicola_trades import report

DEFAULT_OUTPUT_DIR = Path(__file__).parent / "reports"


@click.command()
@click.option("--date1", "-a", default=None, help="Earlier snapshot date (YYYY-MM-DD).")
@click.option("--date2", "-b", default=None, help="Later snapshot date (YYYY-MM-DD).")
@click.option(
    "--tx-type", "-t",
    default="Sell",
    show_default=True,
    help="Transaction type to compare (Sell / Buy / Switch-In / Switch-Out / all).",
)
@click.option("--output", "-o", default=None, help="Output Excel file path.")
@click.option("--list-dates", is_flag=True, default=False, help="List all available snapshot dates.")
def main(date1, date2, tx_type, output, list_dates):
    conn = db.connect()
    db.init(conn)

    if list_dates:
        rows = conn.execute(
            "SELECT snapshot_date, file_name FROM snapshots ORDER BY snapshot_date"
        ).fetchall()
        if not rows:
            click.echo("No snapshots in database. Run ingest.py first.")
        else:
            click.echo(f"{'Date':<14} File")
            click.echo("-" * 60)
            for r in rows:
                click.echo(f"{r['snapshot_date']:<14} {r['file_name']}")
        conn.close()
        return

    if not date1 or not date2:
        click.echo("ERROR: --date1 and --date2 are required (or use --list-dates).", err=True)
        sys.exit(1)

    d1 = date.fromisoformat(date1)
    d2 = date.fromisoformat(date2)
    tx = None if tx_type.lower() == "all" else tx_type

    click.echo(f"Comparing {d1} vs {d2}  [tx_type={tx or 'all'}] ...")

    try:
        result = cmp.diff(conn, d1, d2, tx_type=tx)
    except ValueError as e:
        click.echo(f"ERROR: {e}", err=True)
        conn.close()
        sys.exit(1)

    removed = result["removed"]
    added   = result["added"]

    click.echo(f"  Snapshot {d1}: {len(result['all1']):,} trades")
    click.echo(f"  Snapshot {d2}: {len(result['all2']):,} trades")
    click.echo(f"  Unchanged: {result['unchanged_count']:,}")
    click.echo(f"  Removed:   {len(removed):,}")
    click.echo(f"  Added:     {len(added):,}")

    if output is None:
        DEFAULT_OUTPUT_DIR.mkdir(exist_ok=True)
        output = str(DEFAULT_OUTPUT_DIR / f"comparison_{d1}_vs_{d2}.xlsx")

    out_path = report.write_comparison(result, Path(output), tx_type=tx or "all")
    click.echo(f"\nReport saved to: {out_path}")
    conn.close()


if __name__ == "__main__":
    main()
