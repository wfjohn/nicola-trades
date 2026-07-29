"""
Load the PositionList CSV into the accounts table, capturing
Primary Planner, ISP, and WPA keyed by account number.

Usage:
    python ingest_accounts.py
    python ingest_accounts.py --file "C:\\path\\to\\PositionList.csv"
"""

import sys
from pathlib import Path

import click
import pandas as pd

from nicola_trades import db

DEFAULT_CSV = Path(__file__).parent / "PositionList.csv"


@click.command()
@click.option(
    "--file", "-f",
    default=str(DEFAULT_CSV),
    show_default=True,
    help="Path to the PositionList CSV.",
)
def main(file: str):
    path = Path(file)
    if not path.exists():
        click.echo(f"ERROR: File not found: {path}", err=True)
        sys.exit(1)

    click.echo(f"Reading {path.name} ...")
    df = pd.read_csv(path, low_memory=False)

    df = df.rename(columns={
        "Investment[AccountNumber]":      "account_number",
        "Client[HouseholdName]":          "household_name",
        "Client[Client]":                 "client_name",
        "Client[PrimaryPlanner]":         "primary_planner",
        "Client[InternalServicePlanner]": "isp",
        "Client[WPAs]":                   "wpa",
    })

    keep = ["account_number", "household_name", "client_name", "primary_planner", "isp", "wpa"]
    df = df[keep].dropna(subset=["account_number"]).drop_duplicates(subset=["account_number"])
    click.echo(f"  {len(df):,} unique accounts found.")

    conn = db.connect()
    db.init(conn)

    conn.execute("DELETE FROM accounts")
    conn.executemany(
        """
        INSERT INTO accounts (account_number, household_name, client_name, primary_planner, isp, wpa)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        df[keep].itertuples(index=False, name=None),
    )
    conn.commit()
    conn.close()
    click.echo(f"Done. {len(df):,} accounts loaded.")


if __name__ == "__main__":
    main()
