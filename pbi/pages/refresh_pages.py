"""Refresh the six published redemption pages from pbi.data.

    python -m pbi.pages.refresh_pages <artifact-files dir>

<artifact-files dir> holds each page's live index.html, downloaded with the Artifact tool (read, path="index.html"),
in a sub-folder named by artifact id. Writes nov6.html next to each. The text replacements are anchored on the
wording published on 2026-11-07; when a page's wording changes, update the matching rep() anchors.
Artifact ids: PE queue d98bc932, RE queue dccd9beb, pipeline 98085321, bars 75a6d31d, buildup 23f3ee78, activity 3a1ba931.
"""
import re, json, datetime as dt
from pathlib import Path
from collections import defaultdict
import sys
from pbi.data import *

AF = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifact-files')
P = {k: AF / v / 'index.html' for k, v in dict(pe='d98bc932-3468-494d-b122-dc359ed82807', re='dccd9beb-8aa0-44e1-984b-54a92b980251',
     pipe='98085321-d731-49a7-9ee5-357126eeb879', bars='75a6d31d-d086-426b-a4c6-af719ead0544',
     bu='23f3ee78-9c7e-4913-b938-0d9ea318e29f', act='3a1ba931-04a9-4197-a936-0dc7aff22e23').items()}
OUT = {k: v.with_name('nov6.html') for k, v in P.items()}
END = LAST_PB
assert LAST_LEG == END, (LAST_LEG, END)
M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
hum = lambda d: M[int(d[5:7]) - 1] + '&nbsp;' + str(int(d[8:]))
mm = lambda v: '${:.1f}M'.format(v / 1e6)
report = {}


def rep(s, a, b):
    assert s.count(a) == 1, ('not found once', a[:90], s.count(a))
    return s.replace(a, b)


# ================= PE queue =================
s = P['pe'].read_text(encoding='utf-8')
m = re.search(r'const RAW = \[(.*?)\];', s, re.S)
raw = json.loads('[' + m.group(1) + ']')
have = {d for d, _ in raw}
add = [[d, round(nonre(d, 'Private Equity LP', lo=d, adjust=False))] for d in PB_DATES if d > raw[-1][0] and d not in have]
raw += add
s = s.replace(m.group(0), 'const RAW = [\n' + ',\n'.join(json.dumps(r) for r in raw) + '\n];')
last = raw[-1]
s = rep(s, '<div class="slabel">Queue Oct 15 ʼ26</div>\n      <div class="sval">$92M</div>',
        '<div class="slabel">Queue {} ʼ26</div>\n      <div class="sval">${:.0f}M</div>'.format(hum(END).replace('&nbsp;', ' '), last[1] / 1e6))
s = rep(s, '<div class="sval up">+$33M</div>', '<div class="sval up">+${:.0f}M</div>'.format((last[1] - raw[0][1]) / 1e6))
s = rep(s, 'Oct 2025 – Oct 2026</p>', 'Oct 2025 – Nov 2026</p>')
s = rep(s, 'const T1=parseDate("2026-10-15").getTime();', 'const T1=parseDate("%s").getTime();' % END)
s = rep(s, '["Sep","2026-09-01"],["Oct","2026-10-01"]', '["Sep","2026-09-01"],["Oct","2026-10-01"],["Nov","2026-11-01"]')
s = rep(s, '"2026-08-31","2026-09-30"];', '"2026-08-31","2026-09-30","2026-10-30"];')
pv = dict(raw)
drop30 = pv['2026-10-29'] - pv['2026-10-30']
s = rep(s, 'The Sep 30 settlement took the queue down by about $20M, smaller than the $27M drop on Aug 31.',
        'The Sep 30 settlement took the queue down by about $20M, smaller than the $27M drop on Aug 31; the Oct 30 settlement took it down by about ${:.0f}M. '
        'From Oct 16 the Simcorp figures come from the Beta SIMCORP Pending Transactions model in Power BI, which matched the Simcorp files to the dollar on every earlier day; '
        'it counts switches out to another fund (Sell-Swap) as sells, as the files did.'.format(drop30 / 1e6))
OUT['pe'].write_text(s, encoding='utf-8')
report['pe'] = dict(added=len(add), last=last, oct30_drop=round(drop30))

# ================= RE queue =================
s = P['re'].read_text(encoding='utf-8')
m = re.search(r'const LEG = (\[.*?\]);', s); LEGS = json.loads(m.group(1))
keep = [r for r in LEGS if r[0] <= '2026-10-16']
newd = sorted(d for d in LEG if d > '2026-10-16')
fwd = lambda d, f: round(abs(conn.execute(f"SELECT SUM(gross_amt) FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? AND {W[f]}", (LEG[d], d)).fetchone()[0] or 0))
LEGS = keep + [[d, fwd(d, RE[0]), fwd(d, RE[1])] for d in newd]
s = s.replace(m.group(0), 'const LEG = ' + json.dumps(LEGS, separators=(',', ':')) + ';')
sup = defaultdict(lambda: [0.0, 0.0])
for x in SUP: sup[x['cd']][0 if x['f'] == RE[0] else 1] += x['g']
m = re.search(r'const SUP = (\[.*?\]);', s)
s = s.replace(m.group(0), 'const SUP = ' + json.dumps([[d, round(v[0]), round(v[1])] for d, v in sorted(sup.items())], separators=(',', ':')) + ';')
mon = defaultdict(lambda: [0, 0, 0, 0, 0, 0, 0, 0])
for f, i in ((RE[0], 0), (RE[1], 2)):
    for td, g in conn.execute(f"SELECT trade_date, ABS(gross_amt) FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? AND {W[f]}", (LEG[END], END)):
        mon[td[:7]][i] += g; mon[td[:7]][i + 1] += 1
for x in SUP:
    if x['o'] > END:
        i = 4 if x['f'] == RE[0] else 6
        mon[x['o'][:7]][i] += x['g']; mon[x['o'][:7]][i + 1] += 1
months = [[k] + [round(v) if j % 2 == 0 else v for j, v in enumerate(vals)] for k, vals in sorted(mon.items())]
m = re.search(r'const MONTHS = (\[.*?\]);', s)
s = s.replace(m.group(0), 'const MONTHS = ' + json.dumps(months, separators=(',', ':')) + ';')
s = rep(s, 'through Nov&nbsp;2, 2026.', 'through %s, 2026.' % hum(END))
s = rep(s, 'from October 2025 to November 2 2026', 'from October 2025 to November %d 2026' % int(END[8:]))
s = rep(s, '" requests, Sep 24 to Oct 15";', '" requests, Sep 24 to %s";' % hum(END).replace('&nbsp;', ' '))
s = rep(s, '67 of them, created Sep 24 to Oct 15 and worth $11.4M, are added on their creation date, each placed in the dealing month six months out. Earlier requests that Simcorp holds under a placeholder date are not used.',
        '{} of them, created Sep 24 to {} and worth {}, are added on their creation date in their dealing month, six months out. They are identified from Simcorp&rsquo;s create date '
        '(Pending Redemptions &ndash; Fund Impact model in Power BI) and exclude {} requests ({}) that match an extract order by class, dealing date and amount within 2%. '
        'Earlier requests that Simcorp holds under a placeholder date are not used.'.format(len(SUP), hum(max(x['cd'] for x in SUP)), mm(sum(x['g'] for x in SUP)),
                                                                                          len(SUP_DUP), mm(sum(x['g'] for x in SUP_DUP))))
s = rep(s, 'Simcorp has sent no files after Oct&nbsp;15, so no further Simcorp additions are possible; the 67 above were checked against the Nov&nbsp;2 extract and none has appeared there. ',
        'Until Nov&nbsp;2 this page added only the 67 requests ($11.4M) Simcorp held under its placeholder date. Simcorp has since given those requests real dealing dates, '
        'and its create dates show many more that the extract never captured, so the additions were rebuilt on that basis and raise the line from Sep&nbsp;24 onward. ')
OUT['re'].write_text(s, encoding='utf-8')
report['re'] = dict(legs_last=LEGS[-1], sup=(len(SUP), round(sum(x['g'] for x in SUP))), months=months)

# ================= Pipeline =================
s = P['pipe'].read_text(encoding='utf-8')
m = re.search(r'const D = (\{.*?\});\n', s, re.S); D = json.loads(m.group(1))
old = {f['name']: dict(zip(D['dates'], f['v'])) for f in D['funds']}
PBSET = set(PB_DATES)
dates = sorted({d for d in D['dates'] if d < CUT} | {d for d in LEG if d >= CUT} | set(PB_DATES))
fam_name = {'Canadian Mortgage Fund': 'Canadian Mortgage'}
adj = {}
for f in D['funds']:
    fam = fam_name.get(f['name'], f['name'])
    v = []
    for d in dates:
        if d < CUT: v.append(old[f['name']].get(d)); continue
        if fam in RE: v.append(round(re_fwd(d, fam, hi=horizon(d))) if d in LEG else None)
        else: v.append(round(nonre(d, fam, lo=d, hi=horizon(d))) if d in PBSET else None)
    f['v'] = v
for d in dates:
    if d in NIC and d < NIC[d][0] <= horizon(d): adj[d] = round(NIC[d][1])
D['dates'] = dates; D['adj'] = adj
beyond = {f: round(nonre(END, f, lo=horizon(END), hi='2030-12-31', adjust=False)) for f in FAMS if f not in RE and f != 'Value Add Real Estate LP'}
beyond.update({f: round(re_fwd(END, f) - re_fwd(END, f, hi=horizon(END))) for f in RE})
D['beyond'] = {k: v for k, v in beyond.items() if v > 0}
s = s.replace(m.group(0), 'const D = ' + json.dumps(D, separators=(',', ':')) + ';\n')
pd_raw = nonre(END, 'Private Debt', lo=END, hi=horizon(END), adjust=False)
s = rep(s, 'October&nbsp;2025 to Nov&nbsp;2, 2026. Non-real-estate funds stop at Oct&nbsp;15, the last Simcorp file.</p>', 'October&nbsp;2025 to %s, 2026.</p>' % hum(END))
bey = sorted(D['beyond'].items(), key=lambda x: -x[1])
s = rep(s, 'at the latest date that is only Venture Capital, with $5.8M due beyond six months.',
        'at the latest date that is ' + '; '.join('{} {}'.format(k, mm(v)) for k, v in bey) + ' due beyond six months.')
s = rep(s, 'From Sep&nbsp;24 the non-real-estate funds are read from Simcorp, because the extract stopped picking up new requests; the step at that date is partly the change of source. '
           'Canadian and U.S. Real Estate stay on the extract throughout, plus 67 newer requests that appear only in Simcorp, each counted from the day it was created. '
           'Simcorp&rsquo;s parked real estate queue is not used. Simcorp has sent no files since Oct&nbsp;15, so the non-real-estate funds, and the all-funds total, stop there; '
           'the real estate panels continue on the extract to Nov&nbsp;2. The Oct&nbsp;16 drop in the real estate panels is the October dealing leaving the pipeline.',
        'From Sep&nbsp;24 the non-real-estate funds are read from Simcorp, because the extract stopped picking up new requests; the step at that date is partly the change of source. '
        'Simcorp now comes from the Beta SIMCORP Pending Transactions model in Power BI, which matched the hourly Simcorp files to the dollar on the days tested. '
        'Canadian and U.S. Real Estate stay on the extract throughout, plus {} newer requests ({}) that appear only in Simcorp, each counted from the day it was created. '
        'Simcorp&rsquo;s parked real estate queue is not used. Oct&nbsp;12 (Thanksgiving) has Simcorp data but no extract file, so the real estate panels and the total skip it. '
        'The Oct&nbsp;16 drop in the real estate panels is the October dealing leaving the pipeline.'.format(len(SUP), mm(sum(x['g'] for x in SUP))))
s = rep(s, 'Without the adjustment Private Debt would show $138.1M today.', 'Without the adjustment Private Debt would show %s today.' % mm(pd_raw))
OUT['pipe'].write_text(s, encoding='utf-8')
report['pipe'] = {f['name']: [x for x in f['v'] if x is not None][-1] for f in D['funds']}

# ================= Bars =================
s = P['bars'].read_text(encoding='utf-8')
m = re.search(r'const B = (\{.*?\});\n', s); B = json.loads(m.group(1))
h = horizon(END)
OVR = {'U.S. Real Estate LP': 123600000, 'Canadian Real Estate LP': 102800000, 'Private Equity LP': 101300000}
bym = {}
for r in B['rows']:
    fam = r['name'].replace(' (adjusted)', '')
    if fam in RE:
        mon = defaultdict(float)
        for td, g in conn.execute(f"SELECT trade_date, ABS(gross_amt) FROM trades WHERE snapshot_id=? AND tx_type='Sell' AND trade_date>? AND trade_date<=? AND {W[fam]}", (LEG[END], END, h)):
            mon[td[:7]] += g
        for x in SUP:
            if x['f'] == fam and END < x['o'] <= h: mon[x['o'][:7]] += x['g']
    else:
        mon = nonre_by_month(END, fam, END, h)
    bym[r['name']] = mon
months = sorted({k for v in bym.values() for k, x in v.items() if x})
data = {}
for r in B['rows']:
    fam = r['name'].replace(' (adjusted)', '')
    r['by'] = [round(bym[r['name']].get(k, 0)) for k in months]; data[fam] = sum(r['by'])
    r['asof'] = hum(END).replace('&nbsp;', ' ')
    if fam in OVR: r['total'] = OVR[fam]; r['adj'] = OVR[fam] - data[fam]
    else: r['total'] = data[fam]; r['adj'] = 0
B['rows'].sort(key=lambda r: -r['total']); B['months'] = months; B['simdate'] = END; B['legdate'] = END
s = s.replace(m.group(0), 'const B = ' + json.dumps(B, separators=(',', ':')) + ';\n')
s = rep(s, 'Redemption requests due to deal in the next six months: through Apr&nbsp;30, 2027 for the non-real-estate funds (as of Oct&nbsp;15) and through May&nbsp;31, 2027 for real estate (as of Nov&nbsp;2),',
        'Redemption requests due to deal in the next six months, through %s, 2027, as of %s, 2026,' % (hum(h), hum(END)))
s = rep(s, '<b>As of:</b> Oct&nbsp;15, 2026 for the non-real-estate funds, the last day Simcorp exported; Nov&nbsp;2 for the two real estate funds. Simcorp has sent no files since Oct&nbsp;15. <b>Sources:</b> Simcorp for the non-real-estate funds;',
        '<b>As of:</b> %s, 2026 for all funds. <b>Sources:</b> Simcorp (Beta SIMCORP Pending Transactions model in Power BI) for the non-real-estate funds;' % hum(END))
s = rep(s, 'Without the adjustment Private Debt would show $138.1M today.', 'Without the adjustment Private Debt would show %s today.' % mm(data['Private Debt'] + nonre(END, 'Private Debt', lo=END, hi=h, adjust=False) - nonre(END, 'Private Debt', lo=END, hi=h)))
ovr_txt = re.search(r'The files show \$[^<]*?\(\+\$[^)]*?\)', s).group(0)
s = s.replace(ovr_txt, 'The data show {}, US{} and {} (all as of {}). The differences ({}, US{} and {})'.format(
    mm(data['Canadian Real Estate LP']), mm(data['U.S. Real Estate LP']), mm(data['Private Equity LP']), hum(END),
    '{:+.1f}M'.format(OVR['Canadian Real Estate LP'] / 1e6 - data['Canadian Real Estate LP'] / 1e6).replace('+', '+$').replace('-', '&minus;$'),
    '{:+.1f}M'.format(OVR['U.S. Real Estate LP'] / 1e6 - data['U.S. Real Estate LP'] / 1e6).replace('+', '+$').replace('-', '&minus;$'),
    '{:+.1f}M'.format(OVR['Private Equity LP'] / 1e6 - data['Private Equity LP'] / 1e6).replace('+', '+$').replace('-', '&minus;$')))
OUT['bars'].write_text(s, encoding='utf-8')
report['bars'] = {r['name']: (r['total'], sum(r['by']), r['adj']) for r in B['rows']}

# ================= Buildup: complete October (Apr 30, 2027 cohort) =================
s = P['bu'].read_text(encoding='utf-8')
BU9 = ['Private Debt', 'Private Equity LP', 'Global Infrastructure LP', 'Diversified Real Estate', 'Diversified Private Assets', 'Value Add Real Estate LP']


def cohort(d, td='2027-04-30'):
    return sum(nonre(d, f, exact=td, adjust=False) for f in BU9) + sum(re_fwd(d, f, exact=td) for f in RE)


chk = {d: round(cohort(d)) for d in ('2026-10-02', '2026-10-09', '2026-10-15')}
pts = [(1, '2026-10-02'), (2, '2026-10-09'), (3, '2026-10-16'), (4, '2026-10-23'), (5, '2026-10-30')]
newpts = ','.join('{w:%d,d:"Oct %d",v:%d,s:1}' % (w, int(d[8:]), round(cohort(d))) for w, d in pts)
m = re.search(r'\{ id:"oct", month:"October",   td:"Apr 30",  v:"--s10", partial:true,\s*pts:\[.*?\] \}', s, re.S)
s = s.replace(m.group(0), '{ id:"oct", month:"October",   td:"Apr 30",  v:"--s10",\n    pts:[%s] }' % newpts)
octv = round(cohort('2026-10-30'))
s = rep(s, 'October (Apr 30, 2027) is partial through Oct 15 at $8.7M.";',
        'October (Apr 30, 2027) closed at %s. From Oct 16 Simcorp comes from the Beta SIMCORP Pending Transactions model in Power BI, and real estate adds the Simcorp requests '
        'the extract never captured, identified from Simcorp create dates.";' % mm(octv))
OUT['bu'].write_text(s, encoding='utf-8')
report['bu'] = dict(check_vs_published={'2026-10-02': (chk['2026-10-02'], 437473), '2026-10-09': (chk['2026-10-09'], 4671963), '2026-10-15': (chk['2026-10-15'], 8742544)},
                    oct=[(d, round(cohort(d))) for _, d in pts])
json.dump(report, open(AF / 'refresh_report.json', 'w'), indent=1, default=str)
print(json.dumps(report, indent=1, default=str)[:6000])
