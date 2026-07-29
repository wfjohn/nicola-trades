"""
Scan the OneDrive Pending Trades folder, import any new or changed snapshots into
the local SQLite database.

Usage:
    python ingest.py
    python ingest.py --folder "C:\\path\\to\\folder"
    python ingest.py --all          # re-ingest every file (ignore hash check)
"""

import sys
from pathlib import Path

import click

from nicola_trades import db, loader

DEFAULT_FOLDER = (
    Path.home()
    / "Nicola Wealth"
    / "Fund Operations Team-AMC - 2025_Octonward"
)


@click.command()
@click.option(
    "--folder", "-f",
    default=str(DEFAULT_FOLDER),
    show_default=True,
    help="Path to the Pending Trades folder.",
)
@click.option(
    "--all", "force_all",
    is_flag=True,
    default=False,
    help="Re-ingest every file even if already in the database.",
)
def main(folder: str, force_all: bool):
    folder_path = Path(folder)
    if not folder_path.exists():
        click.echo(f"ERROR: Folder not found: {folder_path}", err=True)
        sys.exit(1)

    xlsx_files = sorted(folder_path.glob("Nwm Pending Trades *.xlsx"))
    if not xlsx_files:
        click.echo("No 'Nwm Pending Trades *.xlsx' files found.")
        return

    # Keep only the latest-modified file per calendar date
    candidates = loader.latest_per_date(xlsx_files)
    click.echo(f"Found {len(xlsx_files)} files -> {len(candidates)} unique dates to consider.")

    conn = db.connect()
    db.init(conn)

    # Build set of already-ingested (filename, hash) pairs
    existing = {
        row["file_name"]: row["file_hash"]
        for row in conn.execute("SELECT file_name, file_hash FROM snapshots")
    }

    ingested = skipped = errors = 0

    for path in sorted(candidates, key=lambda p: loader.snapshot_date(p.name) or p.name):
        snap_date = loader.snapshot_date(path.name)
        if snap_date is None:
            click.echo(f"  SKIP (no date in filename): {path.name}")
            continue

        h = loader.file_hash(path)
        if not force_all and existing.get(path.name) == h:
            skipped += 1
            continue

        click.echo(f"  Ingesting {path.name} ({snap_date}) ...", nl=False)
        try:
            df = loader.load_file(path)

            # Upsert snapshot record
            conn.execute(
                """
                INSERT INTO snapshots (file_name, snapshot_date, file_hash)
                VALUES (?, ?, ?)
                ON CONFLICT(file_name) DO UPDATE SET
                    snapshot_date = excluded.snapshot_date,
                    file_hash     = excluded.file_hash,
                    ingested_at   = datetime('now')
                """,
                (path.name, str(snap_date), h),
            )
            snap_id = conn.execute(
                "SELECT id FROM snapshots WHERE file_name = ?", (path.name,)
            ).fetchone()["id"]

            # Delete existing trades for this snapshot (handles re-ingest)
            conn.execute("DELETE FROM trades WHERE snapshot_id = ?", (snap_id,))

            # Remove any other snapshots for the same date (different filename)
            old_ids = conn.execute(
                "SELECT id FROM snapshots WHERE snapshot_date = ? AND id != ?",
                (str(snap_date), snap_id),
            ).fetchall()
            for (old_id,) in old_ids:
                conn.execute("DELETE FROM trades WHERE snapshot_id = ?", (old_id,))
                conn.execute("DELETE FROM snapshots WHERE id = ?", (old_id,))

            rows = [
                (
                    snap_id,
                    row.wire_order_num,
                    row.tx_type,
                    row.investor_name,
                    row.sin,
                    row.fund_id,
                    row.canonical_fund,
                    row.trade_date,
                    row.settle_date,
                    row.gross_amt,
                    row.cdn_net_amt,
                    row.usd_net_amt,
                    row.shares_units,
                    row.plan_desc,
                    getattr(row, 'dealer_acct_num', None),
                )
                for row in df.itertuples(index=False)
            ]
            conn.executemany(
                """
                INSERT OR IGNORE INTO trades
                    (snapshot_id, wire_order_num, tx_type, investor_name, sin,
                     fund_id, canonical_fund, trade_date, settle_date,
                     gross_amt, cdn_net_amt, usd_net_amt, shares_units, plan_desc,
                     dealer_acct_num)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                rows,
            )
            conn.commit()
            click.echo(f" {len(df):,} rows")
            ingested += 1

        except Exception as exc:
            conn.rollback()
            click.echo(f" ERROR: {exc}")
            errors += 1

    conn.close()
    click.echo(
        f"\nDone. Ingested: {ingested}  Skipped (unchanged): {skipped}  Errors: {errors}"
    )


if __name__ == "__main__":
    main()
