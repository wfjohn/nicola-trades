"""Extend the three day-by-day pages (PE queue, RE queue, Six-Month Pipeline) to the latest loaded date.

    python -m pbi.pages.refresh_daily <artifact-files dir>

<artifact-files dir> holds each page's live index.html (Artifact tool read, path="index.html") in a folder named by
artifact id; writes latest.html next to each. Dates come from pbi_simcorp_sells (non-real-estate, pbi.daily_files)
and pbi_re_sells (real estate, pbi.re_files); the page is extended to the last date both have.

Written for the Nov 6 -> Nov 12 2026 refresh, when real estate moved to Simcorp (data.RE_CUT). Text edits find the
date the page currently shows and replace it; wording that only applies once (the RE_CUT notes) is added only if
absent, so the script can be rerun on its own output.
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from pbi.data import conn, PB_DATES, RE, RE_SC, RE_CUT, QUEUE, NIC, horizon, nonre, re_fwd, re_rows, FAMS

AF = Path(sys.argv[1] if len(sys.argv) > 1 else 'artifact-files')
IDS = dict(pe='d98bc932-3468-494d-b122-dc359ed82807', re='dccd9beb-8aa0-44e1-984b-54a92b980251',
           pipe='98085321-d731-49a7-9ee5-357126eeb879')
P = {k: AF / v / 'index.html' for k, v in IDS.items()}
OUT = {k: v.with_name('latest.html') for k, v in P.items()}
END = max(d for d in PB_DATES if d in RE_SC)
M = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
hum = lambda d: M[int(d[5:7]) - 1] + '&nbsp;' + str(int(d[8:]))
plain = lambda d: M[int(d[5:7]) - 1] + ' ' + str(int(d[8:]))
mm = lambda v: '${:.1f}M'.format(v / 1e6)
report = {'end': END}


def rep(s, a, b, count=1):
    assert s.count(a) == count, ('expected %d' % count, a[:100], s.count(a))
    return s.replace(a, b)


def once(s, anchor, text):
    """Insert text before anchor unless already present."""
    return s if text in s else rep(s, anchor, text + anchor)


# ================= PE queue =================
s = P['pe'].read_text(encoding='utf-8')
m = re.search(r'const RAW = \[(.*?)\];', s, re.S)
raw = json.loads('[' + m.group(1) + ']')
prev = raw[-1][0]
raw += [[d, round(nonre(d, 'Private Equity LP', lo=d, adjust=False))] for d in PB_DATES if prev < d <= END]
s = s.replace(m.group(0), 'const RAW = [\n' + ',\n'.join(json.dumps(r) for r in raw) + '\n];')
s = re.sub(r'<div class="slabel">Queue [A-Z][a-z]{2} \d+ ʼ26</div>\n      <div class="sval">\$\d+M</div>',
           '<div class="slabel">Queue {} ʼ26</div>\n      <div class="sval">${:.0f}M</div>'.format(plain(END), raw[-1][1] / 1e6), s)
s = re.sub(r'<div class="sval up">\+\$\d+M</div>', '<div class="sval up">+${:.0f}M</div>'.format((raw[-1][1] - raw[0][1]) / 1e6), s)
s = re.sub(r'const T1=parseDate\("[\d-]+"\)', 'const T1=parseDate("%s")' % END, s)
OUT['pe'].write_text(s, encoding='utf-8')
report['pe'] = raw[-6:]

# ================= RE queue =================
s = P['re'].read_text(encoding='utf-8')
LEG_LAST = json.loads(re.search(r'const LEG = (\[.*?\]);', s).group(1))[-1][0]
sc_dates = sorted(d for d in RE_SC if d >= RE_CUT and d <= END)
SC = [[d, round(re_fwd(d, RE[0])), round(re_fwd(d, RE[1]))] for d in sc_dates]
mon = defaultdict(lambda: [0, 0, 0, 0])
for f, fid, acct, td, g in re_rows(END):
    if td == QUEUE: continue
    i = 0 if f == RE[0] else 2
    mon[td[:7]][i] += g; mon[td[:7]][i + 1] += 1
months = [[k, round(v[0]), v[1], round(v[2]), v[3], 0, 0, 0, 0] for k, v in sorted(mon.items())]
s = re.sub(r'const MONTHS = \[.*?\];', 'const MONTHS = ' + json.dumps(months, separators=(',', ':')) + ';', s)
if 'const SC = ' in s:
    s = re.sub(r'const SC = \[.*?\];', 'const SC = ' + json.dumps(SC, separators=(',', ':')) + ';', s)
else:
    s = rep(s, 'const MONTHS = ', '/* [snapshot date, Canadian RE forward $, U.S. RE forward $] from Simcorp, from %s */\n'
            'const SC = %s;\nconst SC_START = "%s";\n' % (RE_CUT, json.dumps(SC, separators=(',', ':')), RE_CUT) + 'const MONTHS = ')
    # series: extract (+ Simcorp additions) to LEG's last date, then Simcorp alone
    s = rep(s, """  return [r[0], r[1] + cumC, r[2] + cumU, cumC, cumU];
});""", """  return [r[0], r[1] + cumC, r[2] + cumU, cumC, cumU, 0];
}).concat(SC.map(r => [r[0], r[1], r[2], 0, 0, 1]));
const legLast = LEG.length - 1;""")
    s = rep(s, 'const supC = RAW[last][3], supU = RAW[last][4];', 'const supC = RAW[legLast][3], supU = RAW[legLast][4];')
    s = re.sub(r'MONTHS\.reduce\(\(a, r\) => a \+ r\[6\] \+ r\[8\], 0\) \+ " requests, Sep 24 to [A-Z][a-z]{2} \d+"',
               lambda _: '"Sep 24 to %s; Simcorp alone from %s"' % (plain(LEG_LAST), plain(RE_CUT)), s)
    s = rep(s, '<div class="tlabel">Added from Simcorp</div>', '<div class="tlabel">Added from Simcorp, to the switch</div>')
    s = rep(s, '<div class="tlabel">Forward queue today</div>', '<div class="tlabel">Forward requests today</div>')
    # tooltip
    s = rep(s, 'document.getElementById("tip-t").textContent = "In the extract: " + m1(r[1]+r[2]) +\n        (r[3] + r[4] > 0 ? " · from Simcorp: " + m1(r[3]+r[4]) : "");',
            'document.getElementById("tip-t").textContent = r[5] ? "Forward in Simcorp: " + m1(r[1]+r[2]) : "In the extract: " + m1(r[1]+r[2]) +\n        (r[3] + r[4] > 0 ? " · from Simcorp: " + m1(r[3]+r[4]) : "");')
    # second marker
    s = rep(s, """  svg.appendChild(el("line", {x1: mx, x2: mx, y1: MT, y2: yOf(YMIN), stroke: cMark, "stroke-width": 1.2, "stroke-dasharray": "4 3"}));""",
            """  svg.appendChild(el("line", {x1: mx, x2: mx, y1: MT, y2: yOf(YMIN), stroke: cMark, "stroke-width": 1.2, "stroke-dasharray": "4 3"}));
  const sx = xOf(SC_START);
  svg.appendChild(el("line", {x1: sx, x2: sx, y1: MT, y2: yOf(YMIN), stroke: cMark, "stroke-width": 1.2, "stroke-dasharray": "1 3"}));""")
    s = rep(s, '<div class="leg"><span class="pip dash"></span>Simcorp additions begin Sep 24</div>',
            '<div class="leg"><span class="pip dash"></span>Simcorp additions begin Sep 24</div>\n'
            '      <div class="leg"><span class="pip dot"></span>Simcorp only from Nov 9</div>')
    s = once(s, '.pip.dash{', '.pip.dot{height:0;border-top:2px dotted var(--mark);background:none;}\n')
    # table: one source, no "+ Simcorp" columns
    s = rep(s, '<tr><th>Dealing month</th><th>Canadian RE</th><th>+ Simcorp</th><th>U.S. RE</th><th>+ Simcorp</th><th>Total</th><th>Requests</th></tr>',
            '<tr><th>Dealing month</th><th>Canadian RE</th><th>U.S. RE</th><th>Total</th><th>Requests</th></tr>')
    s = rep(s, """    return "<tr><td>" + monName(r[0]) + "</td><td>" + full(r[1]) + '</td><td class="add">' + (r[5] ? full(r[5]) : "—") +
      "</td><td>" + full(r[3]) + '</td><td class="add">' + (r[7] ? full(r[7]) : "—") + "</td><td>" + full(tot) + "</td><td>" + n + "</td></tr>";""",
            """    return "<tr><td>" + monName(r[0]) + "</td><td>" + full(r[1]) + "</td><td>" + full(r[3]) + "</td><td>" + full(tot) + "</td><td>" + n + "</td></tr>";""")
    s = rep(s, """  document.getElementById("tfoot").innerHTML = "<tr><td>Total</td><td>" + full(s(1)) + "</td><td>" + full(s(5)) +
    "</td><td>" + full(s(3)) + "</td><td>" + full(s(7)) + "</td><td>" + full(s(1)+s(3)+s(5)+s(7)) + "</td><td>" +""",
            """  document.getElementById("tfoot").innerHTML = "<tr><td>Total</td><td>" + full(s(1)) +
    "</td><td>" + full(s(3)) + "</td><td>" + full(s(1)+s(3)) + "</td><td>" +""")
    s = rep(s, """  document.getElementById("tbl-sub").textContent = "Forward-dated requests as at " + human(LEG[LEG.length-1][0]) +
    ", by trade-date month. Purple figures are Simcorp additions.";""",
            """  document.getElementById("tbl-sub").textContent = "Requests in Simcorp still to deal, as at " + human(RAW[last][0]) +
    ", by dealing month. Requests Simcorp holds under its Dec 31, 2029 placeholder are shown in their real dealing month; " +
    "the queue of requests already dealt and awaiting payment is not included.";""")
    # notes
    s = rep(s, '<p><b>Simcorp additions:</b> from Sep 24', '<p><b>Simcorp additions (to Nov&nbsp;6):</b> from Sep 24')
    s = rep(s, ' Two U.S. requests left the extract before their dealing date and look like withdrawals rather than settlements: AgentEx Enterprises, $2.9M due Jan&nbsp;2027 (gone Oct&nbsp;23), and Trevor and Dixie Jones, $2.5M due Nov&nbsp;2026 (gone Oct&nbsp;27). The line adds every drop back, so it still counts them; the forward queue and the table do not.',
            ' Two U.S. requests left the extract before their dealing date and look like withdrawals rather than settlements: AgentEx Enterprises, $2.9M due Jan&nbsp;2027 (gone Oct&nbsp;23), and Trevor and Dixie Jones, $2.5M due Nov&nbsp;2026 (gone Oct&nbsp;27). The line adds every drop back, so it still counts them. Simcorp still holds both, so from Nov&nbsp;9 the forward requests and the table include them; they are being checked with Fund Operations.')
    s = once(s, '\n  </div>\n\n</div>', '\n    <p><b>From Nov&nbsp;9, 2026:</b> real estate is read from Simcorp alone, because the extract stopped picking up new real estate '
             'requests and had stopped changing (its Nov&nbsp;9, 10 and 12 files are almost identical). Each point is the requests in Simcorp still to deal, '
             'with Simcorp&rsquo;s placeholder-dated requests placed in their real dealing month. The step at Nov&nbsp;9 is the change of source: Simcorp '
             'holds requests the extract never had and values sell-all requests net of units already redeemed. Drops are still added back, so the line '
             'continues on the same basis. Same-day tax sell-and-buy-back pairs (Sell-Crystal) are not counted, as for every other fund.</p>')
s = re.sub(r'through Nov&nbsp;\d+, 2026\. Requests that entered Simcorp after the extract stopped capturing them are added from Simcorp and marked\.',
           'through %s, 2026. Requests that entered Simcorp after the extract stopped capturing them are added from Simcorp and marked; from Nov&nbsp;9 the line is read from Simcorp alone.' % hum(END), s)
s = re.sub(r'from October 2025 to November \d+ 2026', 'from October 2025 to November %d 2026' % int(END[8:]), s)
s = s.replace('Canadian and U.S. Real Estate LP requests in the pending-trades extract, day by day', 'Canadian and U.S. Real Estate LP redemption requests, day by day')
OUT['re'].write_text(s, encoding='utf-8')
report['re'] = dict(SC=SC, months=months)

# ================= Pipeline =================
s = P['pipe'].read_text(encoding='utf-8')
m = re.search(r'const D = (\{.*?\});\n', s, re.S); D = json.loads(m.group(1))
fam_name = {'Canadian Mortgage Fund': 'Canadian Mortgage'}
new = [d for d in sorted(set(PB_DATES) | RE_SC) if D['dates'][-1] < d <= END and d in RE_SC and d in PB_DATES]
for f in D['funds']:
    fam = fam_name.get(f['name'], f['name'])
    for d in new:
        f['v'].append(round(re_fwd(d, fam, hi=horizon(d)) if fam in RE else nonre(d, fam, lo=d, hi=horizon(d))))
for d in new:
    if d in NIC and d < NIC[d][0] <= horizon(d): D['adj'][d] = round(NIC[d][1])
D['dates'] += new
beyond = {f: round(nonre(END, f, lo=horizon(END), hi='2030-12-31', adjust=False)) for f in FAMS
          if f not in RE and f not in ('Value Add Real Estate LP', 'U.S. Mortgage')}
beyond.update({f: round(re_fwd(END, f) - re_fwd(END, f, hi=horizon(END))) for f in RE})
D['beyond'] = {k: v for k, v in beyond.items() if v > 0}
s = s.replace(m.group(0), 'const D = ' + json.dumps(D, separators=(',', ':')) + ';\n')
s = re.sub(r'October&nbsp;2025 to [A-Z][a-z]{2}&nbsp;\d+, 2026\.</p>', 'October&nbsp;2025 to %s, 2026.</p>' % hum(END), s)
s = s.replace('The real estate queue held outside the pending-trades extract is excluded.',
              'The real estate queue (requests already dealt and awaiting payment) is excluded.')
bey = sorted(D['beyond'].items(), key=lambda x: -x[1])
s = re.sub(r'at the latest date that is [^<]*? due beyond six months\.',
           'at the latest date that is ' + '; '.join('{} {}'.format(k, mm(v)) for k, v in bey) + ' due beyond six months.', s)
pd_raw = nonre(END, 'Private Debt', lo=END, hi=horizon(END), adjust=False)
s = re.sub(r'Without the adjustment Private Debt would show \$[\d.]+M today\.', 'Without the adjustment Private Debt would show %s today.' % mm(pd_raw), s)
s = rep(s, "(p.re ? '<span class=\"tag\">extract + Simcorp additions</span>'", "(p.re ? '<span class=\"tag\">extract, then Simcorp from Nov 9</span>'") \
    if "extract + Simcorp additions" in s else s
s = once(s, ' Simcorp&rsquo;s parked real estate queue is not used.',
         ' From Nov&nbsp;9 the real estate panels are read from Simcorp alone, with Simcorp&rsquo;s placeholder-dated requests placed in their '
         'real dealing month; the step at Nov&nbsp;9 is the change of source (Simcorp holds requests the extract never had).')
s = s.replace(' Simcorp&rsquo;s parked real estate queue is not used.', ' The real estate queue of dealt requests awaiting payment is not used.')
s = s.replace('Canadian and U.S. Real Estate stay on the extract throughout, plus', 'Canadian and U.S. Real Estate stay on the extract until Nov&nbsp;6, plus')
OUT['pipe'].write_text(s, encoding='utf-8')
report['pipe'] = {f['name']: f['v'][-len(new) - 1:] for f in D['funds']}
report['pipe_new'] = new

print(json.dumps(report, indent=1, default=str))
