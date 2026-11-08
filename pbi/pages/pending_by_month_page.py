"""Build the Pending Redemptions by Month page (claude.ai/artifact/3Gu3vA3VjD9kK29ktfFBXE).

    python -m pbi.pages.pending_by_month_page 2026-11-06 1.40117 out.html

Needs pbi_sells_by_class loaded for the date (queries/sells_by_class_latest.dax) and the USD->CAD rate
(FX Rates table in the Beta SIMCORP model).
"""
import json
import sys
from pathlib import Path

from pbi.data import SUP
from pbi.pending_by_month import build

TEMPLATE = Path(__file__).resolve().parents[1] / 'templates' / 'pending_by_month.html'


def notes(D):
    sup_n, sup_g = len(SUP), sum(s['g'] for s in SUP) / 1e6
    return [
        "<b>Sources:</b> Private Debt, Private Equity, Global Infrastructure, Canadian Mortgage, Diversified Real Estate, Diversified Private Assets, "
        "Venture Capital and Value Add Real Estate are read from Simcorp (Beta SIMCORP Pending Transactions model in Power BI). Canadian and U.S. Real Estate "
        f"dealing months come from the pending-trades extract, plus {sup_n} newer requests (${sup_g:.1f}M in fund currency) that appear only in Simcorp. "
        "Sells and switches out to another fund are counted; switches between share classes of the same fund are not.",
        "<b>Real estate queue:</b> Simcorp holds real estate redemptions that have already dealt and are waiting to be paid under a placeholder dealing date "
        "of Dec&nbsp;31, 2029. The queue bar is drawn with a scale break; its height is not to scale.",
        f"<b>Currency:</b> amounts in U.S. dollar share classes are converted at {D['fx']:.5f} CAD per USD (Power BI FX Rates). "
        "Hover a share-class cell to see the U.S. dollar amount.",
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
