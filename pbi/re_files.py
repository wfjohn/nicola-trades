"""Load Simcorp real estate sells, request by request, into pbi_re_sells.

    python -m pbi.re_files 2026-11-09 2026-11-10 2026-11-12

Reads the LAST hourly Simcorp file of each date (Nicola_PendingOrders_DD_MM_YYYY_HH_MM.csv), which is what Power BI's
Beta SIMCORP model holds for that date (checked to the cent for Nov 6-12 2026; its sourcefileTime label does not
match the file name). The file is read instead of Power BI because the Beta model has no column for the real
estate dealing date: Simcorp parks real estate requests at 2029-12-31 and
keeps the real date in the file's `Original trade-date` (`RE origin` before Oct 15 15:00), formatted
YYYYMMDD;amount;S|SA. Rows with TxSubType 'Crystal' are skipped: Power BI labels them Sell-Crystal/Buy-Crystal
(same-day tax crystallization pairs) and they are excluded for every fund. Compare the printed totals with
queries/re_source_files.dax (n and g) before using a date.

Table: pbi_re_sells  snapshot_date, wire_order, fund_family, fund_id, dealer_acct, tx_type, trade_date, deal_date, gross, source_file
  deal_date = the Original trade-date for parked rows (None if blank), otherwise the trade date.
"""
import csv
import sys
from datetime import datetime
from pathlib import Path

from .data import re_family
from .load import connect

FOLDER = Path.home() / 'Nicola Wealth' / 'Fund Operations Team-AMC - Pending Trades' / 'Simcorp'
PARKED = '2029-12-31'
SCHEMA = ("snapshot_date TEXT, wire_order TEXT, fund_family TEXT, fund_id TEXT, dealer_acct TEXT, tx_type TEXT, trade_date TEXT, "
          "deal_date TEXT, gross REAL, source_file TEXT, PRIMARY KEY (snapshot_date, wire_order, fund_id, tx_type)")


def source_file(d):
    y, m, dd = d.split('-')
    files = sorted(FOLDER.glob(f'Nicola_PendingOrders_{dd}_{m}_{y}_*.csv'))
    if not files:
        raise SystemExit(f'{d}: no Nicola_PendingOrders file in {FOLDER}')
    return files[-1]


def mdy(s):
    return datetime.strptime(s.strip(), '%m/%d/%Y').strftime('%Y-%m-%d')


def read(d, path):
    out = []
    with open(path, encoding='latin-1', newline='') as fh:
        for r in csv.DictReader(fh):
            fam = re_family(r.get('Fund ID') or '')
            if not fam or r['Tx Type'] not in ('Sell', 'Sell-Swap') or (r.get('TxSubType') or '').strip() == 'Crystal':
                continue
            td = mdy(r['Trade Date'])
            otd = (r.get('Original trade-date') or r.get('RE origin') or '').split(';')[0].strip()
            deal = (f'{otd[:4]}-{otd[4:6]}-{otd[6:8]}' if otd else None) if td == PARKED else td
            out.append((d, r['Wire Order #'].strip(), fam, r['Fund ID'], r['Dealer Acct #'].strip(), r['Tx Type'], td, deal,
                        abs(float(r['Gross Amt'].replace(',', '') or 0)), path.name))
    return out


def main(args):
    conn = connect()
    conn.execute(f'CREATE TABLE IF NOT EXISTS pbi_re_sells ({SCHEMA})')
    for d in args:
        p = source_file(d)
        recs = read(d, p)
        conn.execute('DELETE FROM pbi_re_sells WHERE snapshot_date=?', (d,))
        conn.executemany('INSERT INTO pbi_re_sells VALUES (?,?,?,?,?,?,?,?,?,?)', recs)
        for fam in sorted({r[2] for r in recs}):
            rr = [r for r in recs if r[2] == fam]
            fwd = [r for r in rr if r[6] > d]
            print(f'{d} {p.name} {fam}: n {len(rr)} gross {sum(r[8] for r in rr):,.2f} forward {sum(r[8] for r in fwd):,.2f}'
                  f'  parked without dealing date {sum(1 for r in rr if r[6] == PARKED and not r[7])}')
    conn.commit()


if __name__ == '__main__':
    main(sys.argv[1:])
