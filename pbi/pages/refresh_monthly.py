"""Refresh the Monthly Buildup and Six-Month Redemptions by Fund pages to the latest loaded date.

    python -m pbi.pages.refresh_monthly <artifact-files dir>

Same inputs and output convention as refresh_daily (writes latest.html next to each live index.html).

Buildup: adds or extends the current month's cohort (dealing date = last business day six months ahead) with one
point per Friday snapshot plus the latest date, marked partial until month-end. The chart has ten colour slots, so
when a new month is added the oldest month is dropped and its colour reused (a rolling ten months).

Six-Month Redemptions by Fund: rebuilds the bars as of the latest date, keeping the user's manual overrides (OVR).
"""
import datetime as dt
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from pbi.data import PB_DATES, RE, RE_SC, QUEUE, horizon, nonre, nonre_by_month, re_fwd, re_rows

AF = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifact-files')
IDS = dict(bu='23f3ee78-9c7e-4913-b938-0d9ea318e29f', bars='75a6d31d-d086-426b-a4c6-af719ead0544')
P = {k: AF / v / 'index.html' for k, v in IDS.items()}
OUT = {k: v.with_name('latest.html') for k, v in P.items()}
END = max(d for d in PB_DATES if d in RE_SC)
M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
FULL = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
hum = lambda d: M[int(d[5:7]) - 1] + '&nbsp;' + str(int(d[8:]))
plain = lambda d: M[int(d[5:7]) - 1] + ' ' + str(int(d[8:]))
mm = lambda v: '${:.1f}M'.format(v / 1e6)
report = {'end': END}


def rep(s, a, b):
    assert s.count(a) == 1, ('not found once', a[:100], s.count(a))
    return s.replace(a, b)


# ================= Buildup =================
BU = ['Private Debt', 'Private Equity LP', 'Global Infrastructure LP', 'Diversified Real Estate', 'Diversified Private Assets',
      'Value Add Real Estate LP']


def cohort(d, td):
    return sum(nonre(d, f, exact=td, adjust=False) for f in BU) + sum(re_fwd(d, f, exact=td) for f in RE)


def dealing_date(month):
    """Last business day of the month six months after `month` ('YYYY-MM'), as used by the funds."""
    y, m = int(month[:4]), int(month[5:7]) + 6
    if m > 12: y += 1; m -= 12
    d = dt.date(y + (m == 12), m % 12 + 1, 1) - dt.timedelta(days=1)
    while d.weekday() >= 5: d -= dt.timedelta(days=1)
    return d.isoformat()


s = P['bu'].read_text(encoding='utf-8')
mon = END[:7]
mid = M[int(mon[5:]) - 1].lower()
td = dealing_date(mon)
days = sorted(d for d in PB_DATES if d[:7] == mon and d in RE_SC or (d[:7] == mon and d < '2026-11-09'))
fridays = [d for d in days if dt.date.fromisoformat(d).weekday() == 4]
pts_d = fridays + ([END] if END not in fridays else [])
partial = END[:7] == mon and dealing_date(mon) and END < (dt.date.fromisoformat(END[:8] + '28') + dt.timedelta(days=4)).replace(day=1).isoformat() \
    and not any(d > END for d in [])  # month not closed until its last business day is loaded
last_bd = (dt.date.fromisoformat(mon + '-28') + dt.timedelta(days=4)).replace(day=1) - dt.timedelta(days=1)
while last_bd.weekday() >= 5: last_bd -= dt.timedelta(days=1)
partial = END < last_bd.isoformat()
vals = [(i + 1, d, round(cohort(d, td))) for i, d in enumerate(pts_d)]
pts = ','.join('{w:%d,d:"%s",v:%d,s:1}' % (w, plain(d), v) for w, d, v in vals)
series = re.search(r'const SERIES = \[\n(.*?)\n\];', s, re.S)
entries = re.findall(r'  \{ id:"(\w+)".*?\] \},?', series.group(1), re.S)
blocks = re.findall(r'(  \{ id:"\w+".*?\] \}),?', series.group(1), re.S)
td_lab = M[int(td[5:7]) - 1] + ' ' + str(int(td[8:]))
new_block = '  { id:"%s", month:"%s",  td:"%s",  v:"%s",%s\n    pts:[%s] }' % (mid, FULL[int(mon[5:]) - 1], td_lab, '{V}', ' partial:true,' if partial else '', pts)
ids = [re.match(r'  \{ id:"(\w+)"', b).group(1) for b in blocks]
dropped = None
if mid in ids:
    i = ids.index(mid)
    colour = re.search(r'v:"(--s\d+)"', blocks[i]).group(1)
    blocks[i] = new_block.replace('{V}', colour)
else:
    dropped = blocks.pop(0)
    colour = re.search(r'v:"(--s\d+)"', dropped).group(1)
    blocks.append(new_block.replace('{V}', colour))
s = s.replace(series.group(0), 'const SERIES = [\n' + ',\n'.join(blocks) + ',\n];')
first = re.match(r'  \{ id:"\w+", month:"(\w+)"', blocks[0]).group(1)[:3]
rng = '%s–%s 2026' % (first, M[int(mon[5:]) - 1])
s = re.sub(r'<title>Redemption Queue Monthly Buildup — [^<]*</title>', '<title>Redemption Queue Monthly Buildup — %s</title>' % rng, s)
s = re.sub(r'<div class="badge">[^<]*</div>', '<div class="badge">%s&nbsp;2026</div>' % rng.replace(' 2026', '').replace('–', ' – '), s)
note = ('%s (%s, %s) is partial through %s at %s. From Nov 9 real estate is read from Simcorp alone (requests Simcorp holds under its '
        'Dec 31, 2029 placeholder are counted in their real dealing month), so the %s point includes real estate requests the extract never captured.'
        % (FULL[int(mon[5:]) - 1], td_lab, td[:4], plain(END), mm(vals[-1][2]), plain(END)))
fn = re.search(r'(document\.getElementById\("footnote"\)\.textContent =\n  ")(.*?)(";)', s, re.S)
body = re.sub(r' %s \([^)]*\) is partial through [^.]*\..*$' % FULL[int(mon[5:]) - 1], '', fn.group(2))
if dropped:
    body += ' The chart shows the latest ten months; %s has moved off it.' % re.match(r'  \{ id:"\w+", month:"(\w+)"', dropped).group(1)
s = s.replace(fn.group(0), fn.group(1) + body + ' ' + note + fn.group(3))
OUT['bu'].write_text(s, encoding='utf-8')
report['bu'] = dict(month=mon, dealing=td, points=vals, partial=partial, dropped=bool(dropped),
                    check_oct30=round(cohort('2026-10-30', '2027-04-30')))

# ================= Six-Month Redemptions by Fund =================
s = P['bars'].read_text(encoding='utf-8')
m = re.search(r'const B = (\{.*?\});\n', s); B = json.loads(m.group(1))
h = horizon(END)
OVR = {'U.S. Real Estate LP': 123600000, 'Canadian Real Estate LP': 102800000, 'Private Equity LP': 101300000}
bym = {}
for r in B['rows']:
    fam = r['name'].replace(' (adjusted)', '')
    if fam in RE:
        mo = defaultdict(float)
        for f, fid, acct, t, g in re_rows(END, fam):
            if t != QUEUE and t <= h: mo[t[:7]] += g
    else:
        mo = nonre_by_month(END, fam, END, h)
    bym[r['name']] = mo
months = sorted({k for v in bym.values() for k, x in v.items() if x})
data = {}
for r in B['rows']:
    fam = r['name'].replace(' (adjusted)', '')
    r['by'] = [round(bym[r['name']].get(k, 0)) for k in months]; data[fam] = sum(r['by'])
    r['asof'] = plain(END)
    if fam in OVR: r['total'] = OVR[fam]; r['adj'] = OVR[fam] - data[fam]
    else: r['total'] = data[fam]; r['adj'] = 0
B['rows'].sort(key=lambda r: -r['total']); B['months'] = months; B['simdate'] = END; B['legdate'] = END
s = s.replace(m.group(0), 'const B = ' + json.dumps(B, separators=(',', ':')) + ';\n')
s = re.sub(r'through [A-Z][a-z]{2}&nbsp;\d+, 2027, as of [A-Z][a-z]{2}&nbsp;\d+, 2026,', 'through %s, %s, as of %s, 2026,' % (hum(h), h[:4], hum(END)), s)
s = re.sub(r'<b>As of:</b> [A-Z][a-z]{2}&nbsp;\d+, 2026 for all funds\.', '<b>As of:</b> %s, 2026 for all funds.' % hum(END), s)
s = s.replace('the pending-trades extract for Canadian and U.S. Real Estate, plus the newer requests that appear only in Simcorp.',
              'Simcorp for Canadian and U.S. Real Estate too from Nov&nbsp;9, 2026, with requests Simcorp holds under its Dec&nbsp;31, 2029 '
              'placeholder counted in their real dealing month (before Nov&nbsp;9 real estate came from the pending-trades extract plus the newer requests that appeared only in Simcorp).')
pd_raw = nonre(END, 'Private Debt', lo=END, hi=h, adjust=False)
s = re.sub(r'Without the adjustment Private Debt would show \$[\d.]+M today\.', 'Without the adjustment Private Debt would show %s today.' % mm(pd_raw), s)
sign = lambda v: ('+$' if v >= 0 else '&minus;$') + '{:.1f}M'.format(abs(v) / 1e6)
s = re.sub(r'The data show \$[\d.]+M, US\$[\d.]+M and \$[\d.]+M \(all as of [^)]*\)\. The differences \([^)]*\)',
           lambda _: 'The data show {}, US{} and {} (all as of {}). The differences ({}, US{} and {})'.format(
               mm(data['Canadian Real Estate LP']), mm(data['U.S. Real Estate LP']), mm(data['Private Equity LP']), hum(END),
               sign(OVR['Canadian Real Estate LP'] - data['Canadian Real Estate LP']), sign(OVR['U.S. Real Estate LP'] - data['U.S. Real Estate LP']),
               sign(OVR['Private Equity LP'] - data['Private Equity LP'])), s)
OUT['bars'].write_text(s, encoding='utf-8')
report['bars'] = {r['name']: (r['total'], sum(r['by']), r['adj']) for r in B['rows']}
print(json.dumps(report, indent=1, default=str))
