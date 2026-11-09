"""Load saved Power BI query results into data/trades.db.

    python -m pbi.load sells    <result.txt>   # queries/simcorp_sells_daily.dax
    python -m pbi.load nicola   <result.txt>   # queries/nicola_pd_wires.dax
    python -m pbi.load nicola_class <result>   # queries/nicola_pd_wires_by_class.dax
    python -m pbi.load dates    <result.txt>   # queries/order_dates.dax (accumulates by as_of)
    python -m pbi.load byclass  <result.txt>   # queries/sells_by_class_latest.dax
    python -m pbi.load fof      <result.txt>   # queries/fof_sells_latest.dax

Tables (created if missing):
    pbi_simcorp_sells   snapshot_date, fund_family, trade_date, n, gross       Sell + Sell-Swap, Simcorp, illiquid families
    pbi_adj_nicola_pd   snapshot_date, trade_date, gross                       the 9 Nicola-family Private Debt wires
    pbi_adj_nicola_pd_class  snapshot_date, fund_id, trade_date, gross  same wires by share class
    pbi_order_dates     as_of, wire_order, fund_id, tx_type, trade_date, create_date, re_original_trade_date, gross, amount_type
    pbi_sells_by_class  snapshot_date, fund_family, fund_id, trade_date, n, gross
    pbi_fof_sells       snapshot_date, wire_order, fund_family, fund_id, dealer_acct, trade_date, gross   fund-of-fund orders
"""
import sqlite3
import sys
from pathlib import Path

from .parse import rows, num, iso, wire

DB = Path(__file__).resolve().parents[1] / 'data' / 'trades.db'

SCHEMA = {
    'pbi_simcorp_sells': "snapshot_date TEXT, fund_family TEXT, trade_date TEXT, n INTEGER, gross REAL, "
                         "PRIMARY KEY (snapshot_date, fund_family, trade_date)",
    'pbi_adj_nicola_pd': "snapshot_date TEXT, trade_date TEXT, gross REAL, PRIMARY KEY (snapshot_date, trade_date)",
    'pbi_adj_nicola_pd_class': "snapshot_date TEXT, fund_id TEXT, trade_date TEXT, gross REAL, PRIMARY KEY (snapshot_date, fund_id, trade_date)",
    'pbi_order_dates': "as_of TEXT, wire_order TEXT, fund_id TEXT, tx_type TEXT, trade_date TEXT, create_date TEXT, "
                       "re_original_trade_date TEXT, gross REAL, amount_type TEXT, PRIMARY KEY (as_of, wire_order, fund_id, tx_type)",
    'pbi_sells_by_class': "snapshot_date TEXT, fund_family TEXT, fund_id TEXT, trade_date TEXT, n INTEGER, gross REAL, "
                          "PRIMARY KEY (snapshot_date, fund_id, trade_date)",
    'pbi_fof_sells': "snapshot_date TEXT, wire_order TEXT, fund_family TEXT, fund_id TEXT, dealer_acct TEXT, trade_date TEXT, gross REAL, "
                     "PRIMARY KEY (snapshot_date, wire_order, fund_id)",
}


def connect():
    conn = sqlite3.connect(DB)
    for t, cols in SCHEMA.items():
        conn.execute(f"CREATE TABLE IF NOT EXISTS {t} ({cols})")
    return conn


def _opt(v):
    return iso(v) if v not in ('', None, 'None') else None


def load(kind, path):
    conn = connect()
    data = rows(path)
    if kind == 'sells':
        recs = [(iso(r['Pending Trades Date']), r['Pending Trades Fund Name'] or '', iso(r['Pending Trades Trade Date']),
                 int(num(r['n'])), num(r['g'])) for r in data]
        dates = sorted({r[0] for r in recs})
        conn.executemany("DELETE FROM pbi_simcorp_sells WHERE snapshot_date=?", [(d,) for d in dates])
        conn.executemany("INSERT INTO pbi_simcorp_sells VALUES (?,?,?,?,?)", recs)
    elif kind == 'nicola':
        recs = [(iso(r['Pending Trades Date']), iso(r['Pending Trades Trade Date']), num(r['g'])) for r in data]
        conn.executemany("INSERT OR REPLACE INTO pbi_adj_nicola_pd VALUES (?,?,?)", recs)
    elif kind == 'nicola_class':
        recs = [(iso(r['Pending Trades Date']), r['Pending Trades Fund ID'], iso(r['Pending Trades Trade Date']), num(r['g'])) for r in data]
        conn.executemany("INSERT OR REPLACE INTO pbi_adj_nicola_pd_class VALUES (?,?,?,?)", recs)
    elif kind == 'dates':
        recs = [(iso(r['as_of']), wire(r['w']), r['f'], r['t'], iso(r['td']), _opt(r['cd']), _opt(r['ro']), abs(num(r['g'])), r['at'])
                for r in data]
        conn.executemany("INSERT OR REPLACE INTO pbi_order_dates VALUES (?,?,?,?,?,?,?,?,?)", recs)
    elif kind == 'fof':
        recs = [(iso(r['d']), wire(r['w']), r['fn'], r['f'], r['acct'], iso(r['td']), abs(num(r['g']))) for r in data]
        dates = sorted({r[0] for r in recs})
        conn.executemany("DELETE FROM pbi_fof_sells WHERE snapshot_date=?", [(d,) for d in dates])
        conn.executemany("INSERT INTO pbi_fof_sells VALUES (?,?,?,?,?,?,?)", recs)
    elif kind == 'byclass':
        recs = [(iso(r['Pending Trades Date']), r['Pending Trades Fund Name'], r['Pending Trades Fund ID'], iso(r['Pending Trades Trade Date']),
                 int(num(r['n'])), num(r['g'])) for r in data]
        # replace only the (date, fund) pairs in this result, so one fund can be loaded on its own
        pairs = sorted({(r[0], r[1]) for r in recs})
        conn.executemany("DELETE FROM pbi_sells_by_class WHERE snapshot_date=? AND fund_family=?", pairs)
        conn.executemany("INSERT INTO pbi_sells_by_class VALUES (?,?,?,?,?,?)", recs)
    else:
        raise SystemExit(f'unknown kind {kind!r}')
    conn.commit()
    print(f'{kind}: loaded {len(recs)} rows')


if __name__ == '__main__':
    load(sys.argv[1], sys.argv[2])
