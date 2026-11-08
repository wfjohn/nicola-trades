"""Activity page: complete October 2026 (Sep 30 -> Oct 30).

    python -m pbi.pages.activity <saved result of queries/activity_orders.dax> [artifact-files dir]

Non-RE (8 families incl. Canadian Mortgage and Value Add; VC excluded as on the page): Power BI Simcorp orders, wire-level diff.
RE (Canadian + U.S.): legacy wire-level diff, plus Simcorp-only requests created in October.
Trade dates in Sep or Oct excluded. Cancel-resubmit pairs stripped: same account (or investor), same fund family, amounts within 5%."""
import re, sys, json
from collections import defaultdict
from pathlib import Path
from pbi.parse import tables, num, iso
from pbi.data import conn, LEG, SUP, RE, W

res = tables(sys.argv[1])
rows = [r for k, r in res if k in ('csv', 'json')][0]
NONRE = {'Private Debt', 'Private Equity LP', 'Global Infrastructure LP', 'Canadian Mortgage', 'Diversified Real Estate', 'Diversified Private Assets', 'Value Add Real Estate LP'}
snap = defaultdict(dict)
for r in rows:
    if r['fn'] not in NONRE: continue
    w = str(r['w']).strip().removesuffix('.0')
    snap[iso(r['d'])][w] = (r['fn'], str(r['acct']).strip(), abs(num(r['g'])), iso(r['td']))
print('Power BI rows:', {d: len(v) for d, v in snap.items()})


def norm(s): return re.sub(r'\s+', ' ', str(s).upper().strip()).replace('.', '').replace(',', '')


def leg(d):
    out = {}
    for f in RE:
        for w, inv, g, td in conn.execute(f"SELECT wire_order_num, investor_name, ABS(gross_amt), trade_date FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND {W[f]}", (LEG[d],)):
            if td[:7] in ('2026-09', '2026-10'): continue
            out[w] = (f, norm(inv), g, td)
    return out


def strip_pairs(A, R, same):
    used, n, keep = set(), 0, []
    for a in sorted(A, key=lambda x: -x[2]):
        best = None
        for j, r in enumerate(R):
            if j in used or r[0] != a[0] or not same(a[1], r[1]): continue
            hi = max(a[2], r[2])
            if hi and abs(a[2] - r[2]) / hi > 0.05: continue
            dd = abs(a[2] - r[2])
            if best is None or dd < best[0]: best = (dd, j)
        if best: used.add(best[1]); n += 1
        else: keep.append(a)
    return keep, [r for j, r in enumerate(R) if j not in used], n


F, T = snap['2026-09-30'], snap['2026-10-30']
A = [T[w] for w in T if w not in F]; R = [F[w] for w in F if w not in T]
a1, r1, n1 = strip_pairs(A, R, lambda x, y: x == y and x not in ('', 'None'))
LF, LT = leg('2026-09-30'), leg('2026-10-30')
A2 = [LT[w] for w in LT if w not in LF]; R2 = [LF[w] for w in LF if w not in LT]
same = lambda x, y: x == y or (x.startswith('AGENTEX') and y.startswith('AGENTEX')) or x in y or y in x
a2, r2, n2 = strip_pairs(A2, R2, same)
sup_oct = [s for s in SUP if '2026-10-01' <= s['cd'] <= '2026-10-30' and s['o'] > '2026-10-31']
added = sum(x[2] for x in a1) + sum(x[2] for x in a2) + sum(s['g'] for s in sup_oct)
removed = sum(x[2] for x in r1) + sum(x[2] for x in r2)
pairs = n1 + n2
print('non-RE Simcorp: added ${:,.0f} removed ${:,.0f} pairs {}'.format(sum(x[2] for x in a1), sum(x[2] for x in r1), n1))
print('RE extract:     added ${:,.0f} removed ${:,.0f} pairs {}'.format(sum(x[2] for x in a2), sum(x[2] for x in r2), n2))
print('RE Simcorp-only created in October: {} ${:,.0f}'.format(len(sup_oct), sum(s['g'] for s in sup_oct)))
print('OCTOBER: added ${:,.0f} removed ${:,.0f} pairs {}'.format(added, removed, pairs))
bigr = sorted(r1 + r2, key=lambda x: -x[2])[:8]
for x in bigr: print('   removed', x)

p = Path(sys.argv[2] if len(sys.argv) > 2 else 'artifact-files') / '3a1ba931-04a9-4197-a936-0dc7aff22e23' / 'index.html'
s = p.read_text(encoding='utf-8')
def rep(s, a, b):
    assert s.count(a) == 1, a[:80]; return s.replace(a, b)
ADD = json.loads(re.search(r'const ADDED   = (\[.*?\]);', s).group(1))
REM = json.loads(re.search(r'const REMOVED = (\[.*?\]);', s).group(1))
PR = json.loads(re.search(r'const PAIRS   = (\[.*?\]);', s).group(1))
ADD[-1], REM[-1], PR[-1] = round(added), round(removed), pairs
s = re.sub(r'const ADDED   = \[.*?\];', 'const ADDED   = ' + json.dumps(ADD).replace(',', ', ') + ';', s)
s = re.sub(r'const REMOVED = \[.*?\];', 'const REMOVED = ' + json.dumps(REM).replace(',', ', ') + ';', s)
s = re.sub(r'const PAIRS   = \[.*?\];', 'const PAIRS   = ' + json.dumps(PR).replace(',', ', ') + ';', s)
s = rep(s, "'Sep 26','Oct 26*']", "'Sep 26','Oct 26']")
s = rep(s, "'October 2026 (partial)']", "'October 2026']")
s = rep(s, 'Oct 2025 &ndash; Sep 2026 &ensp;', 'Oct 2025 &ndash; Oct 2026 &ensp;')
s = rep(s, ' &ensp;&middot;&ensp; October partial (through Oct 15)</p>', '</p>')
ta, tr = sum(ADD), sum(REM)
fmtB = lambda v: '${:.2f}B'.format(v / 1e9) if v >= 1e9 else '${:.0f}M'.format(v / 1e6)
s = rep(s, '<div class="stat-value v-added">$1.24B</div>', '<div class="stat-value v-added">%s</div>' % fmtB(ta))
s = rep(s, '<div class="stat-value v-removed">$97M</div>', '<div class="stat-value v-removed">%s</div>' % fmtB(tr))
s = rep(s, '<div class="stat-value v-net">$1.15B</div>', '<div class="stat-value v-net">%s</div>' % fmtB(ta - tr))
s = rep(s, '<div class="stat-value v-neutral">142</div>', '<div class="stat-value v-neutral">%d</div>' % sum(PR))
s = rep(s, '142 pairs excluded in total.', '%d pairs excluded in total.' % sum(PR))
s = rep(s, 'October 2026 (Sep 30 → Oct 15) is partial.', 'October 2026 (Sep 30 → Oct 30) is complete.')
s = rep(s, "October compares Simcorp’s Sep 30 and Oct 15 files for the non-real-estate funds, and uses the extract plus Simcorp requests for real estate.",
        "October compares Simcorp’s Sep 30 and Oct 30 snapshots for the non-real-estate funds (Beta SIMCORP Pending Transactions model in Power BI; cancel-resubmit pairs matched on account), "
        "and uses the extract plus the {} Simcorp requests created in October that the extract never captured (${:.1f}M) for real estate.".format(len(sup_oct), sum(s['g'] for s in sup_oct) / 1e6))
p.with_name('nov6.html').write_text(s, encoding='utf-8')
print('totals: added {:,} removed {:,} pairs {}'.format(ta, tr, sum(PR)))
