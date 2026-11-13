"""Daily Simcorp sells by fund family and dealing date, from the day's last Simcorp file, for pbi_simcorp_sells.

    python -m pbi.daily_files check 2026-11-06            # compare with what is stored (loaded from Power BI)
    python -m pbi.daily_files load  2026-11-09 2026-11-12 # replace those dates in pbi_simcorp_sells

The day's last Nicola_PendingOrders file is what Power BI's Beta SIMCORP model holds for that date (see re_files).
Non-real-estate families only (real estate is in pbi_re_sells). Same rules as queries/simcorp_sells_daily.dax: Tx Type Sell (Sell-Swap is a Sell with TxSubType Swap), Sell-Crystal
skipped, dealing date after the snapshot date. Fund family comes from Power BI's fund names already in the database
(pbi_sells_by_class), and real estate from re_family; an unknown fund id stops the load. The nine Nicola-family
Private Debt wires are also written to pbi_adj_nicola_pd and pbi_adj_nicola_pd_class.
"""
import csv
import sys
from collections import defaultdict

from .data import conn, re_family
from .re_files import source_file, mdy

NICOLA = {f'20260925000{n}' for n in ('531', '542', '543', '544', '545', '546', '547', '548', '549')}
FAMS = {fid: f for fid, f in conn.execute("SELECT DISTINCT fund_id, fund_family FROM pbi_sells_by_class")}
SKIP_PREFIX = ()   # fund ids outside the illiquid families are ignored if not in FAMS and not real estate


def family(fid):
    return re_family(fid) or FAMS.get(fid)


def read(d):
    p = source_file(d)
    agg, nic, nic_class, unknown = defaultdict(lambda: [0, 0.0]), defaultdict(float), defaultdict(float), defaultdict(float)
    with open(p, encoding='latin-1', newline='') as fh:
        for r in csv.DictReader(fh):
            fid = (r.get('Fund ID') or '').strip()
            if r.get('Tx Type') not in ('Sell', 'Sell-Swap') or (r.get('TxSubType') or '').strip() == 'Crystal':
                continue
            td = mdy(r['Trade Date'])
            g = abs(float((r['Gross Amt'] or '0').replace(',', '')))
            w = r['Wire Order #'].strip()
            if w in NICOLA:
                nic[td] += g; nic_class[(fid, td)] += g
            if td <= d:
                continue
            if re_family(fid):
                continue   # real estate: pbi_re_sells (re_files), which places parked requests in their real month
            f = family(fid)
            if not f:
                unknown[(fid, r['Fund Desc'][:40])] += g
                continue
            agg[(f, td)][0] += 1; agg[(f, td)][1] += g
    return p, agg, nic, nic_class, unknown


def main(mode, dates):
    for d in dates:
        p, agg, nic, nic_class, unknown = read(d)
        print(f'{d}: {p.name}')
        if unknown:
            print('  fund ids not in an illiquid family (ignored):', {k: round(v) for k, v in sorted(unknown.items())})
        if mode == 'check':
            have = {(f, td): (n, g) for f, td, n, g in conn.execute(
                "SELECT fund_family, trade_date, n, gross FROM pbi_simcorp_sells WHERE snapshot_date=?", (d,))}
            fams = sorted({k[0] for k in have} | {k[0] for k in agg})
            for f in fams:
                a = sum(v[1] for k, v in agg.items() if k[0] == f and k[1] <= '2030-12-31')
                b = sum(v[1] for k, v in have.items() if k[0] == f and k[1] <= '2030-12-31')
                diff = [(td, round(agg.get((f, td), [0, 0])[1] - have.get((f, td), (0, 0))[1], 2))
                        for td in sorted({k[1] for k in agg if k[0] == f} | {k[1] for k in have if k[0] == f})]
                diff = [x for x in diff if abs(x[1]) > 0.01]
                print(f'  {f:28s} file {a:16,.2f}  stored {b:16,.2f}  {"MATCH" if not diff else diff[:5]}')
        else:
            conn.execute('DELETE FROM pbi_simcorp_sells WHERE snapshot_date=?', (d,))
            conn.executemany('INSERT INTO pbi_simcorp_sells VALUES (?,?,?,?,?)',
                             [(d, f, td, n, g) for (f, td), (n, g) in agg.items()])
            conn.execute('DELETE FROM pbi_adj_nicola_pd WHERE snapshot_date=?', (d,))
            conn.executemany('INSERT INTO pbi_adj_nicola_pd VALUES (?,?,?)', [(d, td, g) for td, g in nic.items()])
            conn.execute('DELETE FROM pbi_adj_nicola_pd_class WHERE snapshot_date=?', (d,))
            conn.executemany('INSERT INTO pbi_adj_nicola_pd_class VALUES (?,?,?,?)', [(d, fid, td, g) for (fid, td), g in nic_class.items()])
            conn.commit()
            print(f'  loaded {len(agg)} family/date rows; Nicola PD {dict((k, round(v)) for k, v in nic.items())}')


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2:])
