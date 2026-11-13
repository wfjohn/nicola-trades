"""Data layer for the redemption pages.

Source rules (agreed with the CIO, Oct-Nov 2026):
  * Non-real-estate funds: Simcorp from Sep 24 2026, read from Power BI (pbi_simcorp_sells). Legacy extract before.
  * Canadian + U.S. Real Estate LP:
      - from RE_CUT (Nov 9 2026, user decision 2026-11-13): Simcorp, request by request (pbi_re_sells, loaded by
        pbi.re_files from the same file Power BI holds). Parked requests (trade date 2029-12-31) go to their real
        dealing month from Original trade-date; those whose dealing date has passed are the queue.
      - before RE_CUT: the legacy "Nwm Pending Trades" extract (trades table), plus Simcorp-only new requests (SUP)
        identified from Simcorp create dates (pbi_order_dates), plus Simcorp's parked queue.
  * The nine Nicola-family Private Debt requests (pbi_adj_nicola_pd) are removed from forward PD views.
"""
import calendar
import sqlite3
from collections import defaultdict
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / 'data' / 'trades.db'
conn = sqlite3.connect(DB)

CUT = '2026-09-24'
RE = ('Canadian Real Estate LP', 'U.S. Real Estate LP')
FAMS = ['Private Debt', 'Private Equity LP', 'U.S. Real Estate LP', 'Canadian Real Estate LP', 'Global Infrastructure LP',
        'Canadian Mortgage', 'U.S. Mortgage', 'Diversified Real Estate', 'Diversified Private Assets', 'Venture Capital LP',
        'Value Add Real Estate LP']
# U.S. Mortgage was added to the pending-by-month page on 2026-11-08. The older pages (refresh_pages) leave it out.
W = {'Canadian Real Estate LP': "(canonical_fund='Canadian Real Estate LP' OR canonical_fund LIKE 'Nicola Canadian Real Estate%')",
     'U.S. Real Estate LP': "(canonical_fund='U.S. Real Estate LP' OR canonical_fund LIKE 'Nicola U.S. Real Estate%')"}
QUEUE = '2029-12-31'   # Simcorp parks the real estate queue at this placeholder dealing date
RE_CUT = '2026-11-09'  # real estate switches from the legacy extract to Simcorp on this snapshot date

# Share-class currency: first three digits of the code after "NWM" (Dim Fund in the Beta SIMCORP model).
USD_BASES = {'131', '139', '171', '249', '231', '241', '261', '269', '281', '291', '301', '331', '341',
             '505', '507', '511', '519', '521', '529', '531', '539', '711'}


def currency(fund_id):
    """N-series classes (NWMxx6yz, e.g. NWM26601): odd last digit = USD, even = CAD. Otherwise by the base code.
    Checked against usd_net_amt in the legacy extract for every class with sells since Jun 2026."""
    code = fund_id[3:]
    if len(code) == 5 and code[2] == '6':
        return 'USD' if code[-1] in '13579' else 'CAD'
    return 'USD' if code[:3] in USD_BASES else 'CAD'


def horizon(d):
    """End of the sixth month after d."""
    y, m = int(d[:4]), int(d[5:7]) + 6
    if m > 12: y += 1; m -= 12
    return '{}-{:02d}-{:02d}'.format(y, m, calendar.monthrange(y, m)[1])


def plus6(d):
    y, m = int(d[:4]), int(d[5:7]) + 6
    if m > 12: y += 1; m -= 12
    return '{}-{:02d}'.format(y, m)


def re_family(fund_id):
    if fund_id.startswith('NWM500'): return 'Canadian Real Estate LP'
    if fund_id.startswith('NWM505'): return 'U.S. Real Estate LP'
    return None


LEG = dict(conn.execute("SELECT snapshot_date, id FROM snapshots WHERE snapshot_date >= '2025-10-01'"))
LAST_LEG = max(LEG)

PB = defaultdict(lambda: defaultdict(float))
for d, f, td, n, g in conn.execute("SELECT snapshot_date, fund_family, trade_date, n, gross FROM pbi_simcorp_sells"):
    if td <= '2030-12-31': PB[(d, f)][td] += g
PB_DATES = sorted({d for d, _ in PB})
LAST_PB = PB_DATES[-1] if PB_DATES else None
NIC = {d: (td, g) for d, td, g in conn.execute("SELECT snapshot_date, trade_date, gross FROM pbi_adj_nicola_pd")}


def nonre(d, f, lo=None, hi=None, exact=None, adjust=True):
    """Simcorp sells for family f at snapshot d with dealing date in (lo, hi] or == exact; Nicola PD removed."""
    tot = 0.0
    for td, g in PB[(d, f)].items():
        if (exact and td != exact) or (lo and td <= lo) or (hi and td > hi): continue
        tot += g
    if adjust and f == 'Private Debt' and d in NIC:
        td, g = NIC[d]
        if (exact and td == exact) or (not exact and (not lo or td > lo) and (not hi or td <= hi)): tot -= g
    return tot


def nonre_by_month(d, f, lo, hi, adjust=True):
    out = defaultdict(float)
    for td, g in PB[(d, f)].items():
        if lo < td <= hi: out[td[:7]] += g
    if adjust and f == 'Private Debt' and d in NIC and lo < NIC[d][0] <= hi: out[NIC[d][0][:7]] -= NIC[d][1]
    return out


# ---- Simcorp-only real estate requests
ORDER_ASOF = conn.execute("SELECT MAX(as_of) FROM pbi_order_dates").fetchone()[0]
_near = defaultdict(list)
for fid, g, td in conn.execute("SELECT fund_id, ABS(gross_amt), trade_date FROM trades WHERE snapshot_id=? AND tx_type='Sell'", (LEG[LAST_LEG],)):
    _near[(fid, td)].append(g)
SUP, SUP_DUP = [], []
for w, fid, td, cd, ro, g in conn.execute("SELECT wire_order, fund_id, trade_date, create_date, re_original_trade_date, gross "
                                           "FROM pbi_order_dates WHERE as_of=? AND tx_type LIKE 'Sell%'", (ORDER_ASOF,)):
    f = re_family(fid)
    deal = ro if td == QUEUE else td          # parked rows carry the dealing date in RE origin
    if not f or not cd or cd < CUT or not deal or deal[:7] != plus6(cd): continue
    rec = dict(w=w, f=f, fid=fid, cd=cd, o=deal, g=g)
    # already in the extract: same class + dealing date, amount within 2%
    (SUP_DUP if any(abs(x - g) <= 0.02 * g for x in _near.get((fid, deal), [])) else SUP).append(rec)


RE_SC = {d for (d,) in conn.execute("SELECT DISTINCT snapshot_date FROM pbi_re_sells")}     if conn.execute("SELECT 1 FROM sqlite_master WHERE name='pbi_re_sells'").fetchone() else set()


def re_rows(d, f=None):
    """Simcorp real estate sells at d (d >= RE_CUT): (family, fund_id, dealer_acct, dealing date or QUEUE, gross).
    A parked request whose dealing date has passed (or is blank) is in the queue and keeps the QUEUE date."""
    if d not in RE_SC:
        raise SystemExit(f'pbi_re_sells has no rows for {d}: run python -m pbi.re_files {d}')
    out = []
    for fam, fid, acct, td, deal, g in conn.execute("SELECT fund_family, fund_id, dealer_acct, trade_date, deal_date, gross "
                                                     "FROM pbi_re_sells WHERE snapshot_date=? AND trade_date>?", (d, d)):
        if f and fam != f: continue
        if td == QUEUE:
            td = deal if deal and deal > d else QUEUE
        out.append((fam, fid, acct, td, g))
    return out


def re_fwd(d, f, lo=None, hi=None, exact=None):
    """Real estate forward sells at d, excluding the queue. From RE_CUT: Simcorp. Before: legacy extract + Simcorp-only
    requests created by d."""
    tot = 0.0
    if d >= RE_CUT:
        for _, _, _, td, g in re_rows(d, f):
            if td == QUEUE or (exact and td != exact) or (hi and td > hi): continue
            tot += g
        return tot
    q = f"SELECT trade_date, ABS(gross_amt) FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? AND {W[f]}"
    for td, g in conn.execute(q, (LEG[d], d)):
        if (exact and td != exact) or (hi and td > hi): continue
        tot += g
    for s in SUP:
        if s['f'] != f or s['cd'] > d or s['o'] <= d: continue
        if (exact and s['o'] != exact) or (hi and s['o'] > hi): continue
        tot += s['g']
    return tot


def pending_by_class(d):
    """{(family, fund_id, 'YYYY-MM'): gross in class currency} at snapshot d, all forward dealing dates.
    Non-RE from Simcorp (pbi_sells_by_class). RE from RE_CUT: Simcorp (re_rows), queue under 2029-12; before RE_CUT:
    legacy + Simcorp-only + Simcorp's parked queue (2029-12)."""
    out = defaultdict(float)
    new_re = d >= RE_CUT
    for f, fid, td, g in conn.execute("SELECT fund_family, fund_id, trade_date, gross FROM pbi_sells_by_class WHERE snapshot_date=?", (d,)):
        if f in RE and (new_re or td != QUEUE): continue      # RE comes from re_rows, or (before RE_CUT) the extract
        if td > '2030-12-31': continue
        out[(f, fid, td[:7])] += g
    for fid, td, g in conn.execute("SELECT fund_id, trade_date, gross FROM pbi_adj_nicola_pd_class WHERE snapshot_date=?", (d,)):
        if td > d: out[('Private Debt', fid, td[:7])] -= g     # Nicola-family PD adjustment, per class
    if new_re:
        for f, fid, _, td, g in re_rows(d):
            out[(f, fid, td[:7])] += g
        return out
    for f in RE:
        q = f"SELECT fund_id, trade_date, ABS(gross_amt) FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? AND {W[f]}"
        for fid, td, g in conn.execute(q, (LEG[d], d)):
            out[(f, fid, td[:7])] += g
    for s in SUP:
        if s['cd'] <= d < s['o']: out[(s['f'], s['fid'], s['o'][:7])] += s['g']
    return out


# ---- Fund-of-fund redemptions: orders placed by our own funds (e.g. Core Portfolio redeeming from Private Debt)
def investor_name(acct=None, name=None):
    """Investing fund from a Simcorp dealer account (250AVS_U -> Core Portfolio) or a legacy investor name."""
    if acct:
        return {'250': 'Core Portfolio', '254': 'Core Portfolio', '270': 'Diversified Real Estate Fund'}.get(acct[:3], 'Fund account ' + acct)
    n = name.upper().removeprefix('NICOLA ').removesuffix(' FUND').title()
    return {'Core Portfolio': 'Core Portfolio', 'Diversified Real Estate': 'Diversified Real Estate Fund'}.get(n, n)


def fof_by_class(d):
    """{(family, fund_id, 'YYYY-MM', investor): gross in class currency} at snapshot d. Same sources as pending_by_class:
    Simcorp (pbi_fof_sells, accounts containing 'AVS') for non-RE and the RE queue; for RE dealing months, the legacy
    extract's fund accounts (dealer account starting '5', investor 'NICOLA ... FUND')."""
    out = defaultdict(float)
    new_re = d >= RE_CUT
    for f, fid, acct, td, g in conn.execute("SELECT fund_family, fund_id, dealer_acct, trade_date, gross FROM pbi_fof_sells WHERE snapshot_date=?", (d,)):
        if f not in FAMS or (f in RE and (new_re or td != QUEUE)): continue
        out[(f, fid, td[:7], investor_name(acct=acct))] += g
    if new_re:
        for f, fid, acct, td, g in re_rows(d):
            if 'AVS' in acct: out[(f, fid, td[:7], investor_name(acct=acct))] += g
        return out
    for f in RE:
        q = (f"SELECT fund_id, trade_date, ABS(gross_amt), investor_name FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? "
             f"AND dealer_acct_num LIKE '5%' AND investor_name LIKE 'NICOLA % FUND' AND {W[f]}")
        for fid, td, g, nm in conn.execute(q, (LEG[d], d)):
            out[(f, fid, td[:7], investor_name(name=nm))] += g
    return out
