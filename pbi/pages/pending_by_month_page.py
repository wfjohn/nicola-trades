"""Build the Pending Redemptions by Month page (claude.ai/artifact/3Gu3vA3VjD9kK29ktfFBXE).

    python -m pbi.pages.pending_by_month_page 2026-11-12 1.40 out.html

Needs, for the date: pbi_sells_by_class (queries/sells_by_class_latest.dax), pbi_fof_sells (fof_sells_latest.dax),
pbi_adj_nicola_pd_class, and from Nov 9 2026 pbi_re_sells (python -m pbi.re_files <date>). The USD->CAD rate is
1.40 by the user's choice (Nov 2026).
"""
import json
import sys
from pathlib import Path

from pbi.data import SUP, RE_CUT
from pbi.pending_by_month import build

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'pending_by_month.html'


def notes(D):
    if D['asof'] >= RE_CUT:
        src = ("<b>Sources:</b> every fund is read from Simcorp, through the Beta SIMCORP Pending Transactions model in Power BI. "
               "Real estate has come from Simcorp since Nov&nbsp;9, 2026; before that it came from the pending-trades extract, which stopped picking up new "
               "real estate requests. Simcorp files each real estate request under a placeholder dealing date of Dec&nbsp;31, 2029 and records its real "
               "dealing date separately (Original trade-date in the Simcorp file); requests are shown in that real month. "
               "Sells and switches out to another fund are counted. Switches between share classes of the same fund are not, and neither are "
               "same-day tax sell-and-buy-back pairs (Sell-Crystal).")
    else:
        sup_n, sup_g = len(SUP), sum(s['g'] for s in SUP) / 1e6
        src = ("<b>Sources:</b> Private Debt, Private Equity, Global Infrastructure, Canadian Mortgage, U.S. Mortgage, Diversified Real Estate, Diversified Private Assets, "
               "Venture Capital and Value Add Real Estate are read from Simcorp (Beta SIMCORP Pending Transactions model in Power BI). Canadian and U.S. Real Estate "
               f"dealing months come from the pending-trades extract, plus {sup_n} newer requests (${sup_g:.1f}M in fund currency) that appear only in Simcorp. "
               "Sells and switches out to another fund are counted; switches between share classes of the same fund are not.")
    return [
        src,
        "<b>Real estate queue:</b> real estate redemptions whose dealing date has passed and which are waiting to be paid. Simcorp keeps them under its "
        "placeholder date of Dec&nbsp;31, 2029. The queue bar is drawn with a scale break; its height is not to scale.",
        f"<b>Currency:</b> amounts in U.S. dollar share classes are converted at {D['fx']:g} CAD per USD. "
        "Hover a share-class cell to see the U.S. dollar amount (All requests view).",
        "<b>Fund-of-fund:</b> requests placed by our own funds rather than clients. Core Portfolio redeems from Private Debt, Private Equity, "
        "Global Infrastructure, U.S. Mortgage and both real estate funds; the Diversified Real Estate Fund redeems from Canadian and U.S. Real Estate. "
        "They are identified by the funds' own dealer accounts in Simcorp (250AVS, 254AVS and 270AVS). "
        "Diversified Real Estate Fund's redemptions from the two real estate funds partly fund its own client redemptions, "
        "so adding both counts some dollars twice across the fund family.",
        "<b>Adjustment:</b> Private Debt excludes the Nicola family requests (pbi_adj_nicola_pd_class). The manual overrides on the "
        "Six-Month Redemptions by Fund page are not applied here.",
        "<b>Months shown:</b> only months with pending redemptions.",
    ]


if __name__ == '__main__':
    d, fx, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    D = build(d, fx)
    html = TEMPLATE.read_text(encoding='utf-8')
    html = html.replace('__DATA__', json.dumps(D, separators=(',', ':'))).replace(
        '__NOTES__', json.dumps(''.join('<p class="note">' + n + '</p>' for n in notes(D))))
    Path(out).write_text(html, encoding='utf-8')
    print('wrote', out)
