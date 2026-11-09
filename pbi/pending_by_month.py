"""Pending redemptions by dealing month, in CAD, per fund family and share class, for one snapshot.
Each class and family also carries `fof`: the part placed by our own funds (fund-of-fund, see data.fof_by_class).

    python -m pbi.pending_by_month 2026-11-06 1.40117 out.json

Sources follow pbi.data: non-RE from Simcorp (pbi_sells_by_class), RE from the legacy extract plus Simcorp-only
requests, and Simcorp's parked real estate queue at 2029-12-31. Nicola-family PD wires are removed.
USD classes are converted at the given USD->CAD rate (FX Rates table in the Beta SIMCORP model).
"""
import json
import re
import sys
from collections import defaultdict

from .data import conn, pending_by_class, fof_by_class, currency, FAMS, QUEUE


def class_label(fid):
    code = fid[3:]
    if len(code) == 5 and code[2] == '6':          # N-series: NWMxx6yz
        n = {'0': 'N-O', '1': 'N-O', '4': 'N-A', '5': 'N-A', '2': 'N-B'}.get(code[-1], 'N')
        return f'Class {n} {currency(fid)}'
    names = [c for (c,) in conn.execute("SELECT DISTINCT canonical_fund FROM trades WHERE fund_id=? AND canonical_fund LIKE '%Class%'", (fid,))]
    m = re.search(r'Class\s*-?\s*(.+)$', names[0]) if names else None
    if m: return 'Class ' + m.group(1).strip()
    code = fid[3:]
    cls = {'4': 'A', '5': 'A', '8': 'I', '9': 'I'}.get(code[3:4], 'O') if len(code) == 4 else 'O'
    return f'Class {cls} {currency(fid)}'


def build(d, fx):
    P = pending_by_class(d)
    rows = defaultdict(lambda: {'native': defaultdict(float), 'cad': defaultdict(float)})
    for (fam, fid, mon), g in P.items():
        if abs(g) < 0.5: continue
        r = rows[(fam, fid)]
        r['native'][mon] += g
        r['cad'][mon] += g * (fx if currency(fid) == 'USD' else 1.0)
    F = fof_by_class(d)
    fof = defaultdict(lambda: defaultdict(float))            # (fam, fid) -> month -> CAD
    by_inv = defaultdict(lambda: defaultdict(float))         # (fam, investor) -> month -> CAD
    for (fam, fid, mon, inv), g in F.items():
        c = g * (fx if currency(fid) == 'USD' else 1.0)
        fof[(fam, fid)][mon] += c
        by_inv[(fam, inv)][mon] += c
    months = sorted({m for r in rows.values() for m in r['cad']})
    out = []
    for fam in FAMS:
        classes = []
        for (f, fid), r in sorted(rows.items(), key=lambda kv: -sum(kv[1]['cad'].values())):
            if f != fam: continue
            classes.append({'id': fid, 'label': class_label(fid), 'ccy': currency(fid),
                            'cad': [round(r['cad'].get(m, 0)) for m in months],
                            'native': [round(r['native'].get(m, 0)) for m in months],
                            'fof': [round(fof[(f, fid)].get(m, 0)) for m in months]})
        if classes:
            invs = {inv: [round(v.get(m, 0)) for m in months] for (f, inv), v in sorted(by_inv.items()) if f == fam}
            out.append({'family': fam, 'classes': classes, 'cad': [sum(c['cad'][i] for c in classes) for i in range(len(months))],
                        'fof': [sum(c['fof'][i] for c in classes) for i in range(len(months))], 'fof_by': invs})
    return {'asof': d, 'fx': fx, 'queue_month': QUEUE[:7], 'months': months, 'funds': out}


if __name__ == '__main__':
    d, fx, path = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    res = build(d, fx)
    json.dump(res, open(path, 'w'), indent=1)
    tot = sum(sum(f['cad']) for f in res['funds'])
    print(f"{len(res['months'])} months, {sum(len(f['classes']) for f in res['funds'])} classes, total CAD {tot:,.0f}")
    for f in res['funds']:
        q = f['cad'][res['months'].index(res['queue_month'])] if res['queue_month'] in res['months'] else 0
        print(f"  {f['family']:<28} total {sum(f['cad']):>15,.0f}   queue {q:>14,.0f}   classes {[c['id'] for c in f['classes']]}")
