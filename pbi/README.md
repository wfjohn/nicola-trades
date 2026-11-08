# Power BI feed (`pbi/`)

Since late September 2026, Simcorp has been the order book for the non-real-estate funds. The Simcorp folder export stopped on Oct 15. The same data, kept daily, is in Power BI. This package loads that data into `data/trades.db` and builds the redemption pages from it.

## Sources

| Data | Where | Model / table |
|---|---|---|
| Non-real-estate funds, daily, from Sep 24 2026 | Power BI | Beta SIMCORP Pending Transactions (`8e49fab3-87e6-418e-98c3-89516f992d58`), `'Pending Trades'`, source = Simcorp |
| Canadian + U.S. Real Estate LP, all dates | 2025_Octonward folder | `Nwm Pending Trades *.xlsx` → `python ingest.py` → `trades` |
| Create date and real estate original dealing date, latest day only | Power BI | Pending Redemptions - Fund Impact (SLT, `d3def5f5-4cd7-49cd-893a-f692d54d574d`), `'Fabric_Pending Trades'` |
| USD → CAD rate | Power BI | Beta SIMCORP model, `'FX Rates'` |

Before Sep 22 2026, Power BI's `'Pending Trades'` also holds the legacy history, where `source` is blank. After that date, its "Prometa" rows are only SIP, SWP and CI Direct orders. Those orders are also in the legacy extract, so the extract is still needed for real estate.

## Rules baked in

- **Sells:** count Tx Type `Sell` and `Sell-Swap` (a switch out to another fund).
  - The raw Simcorp files label both as "Sell", so this matches them to the dollar.
  - `Switch-Out` (a class switch inside one fund) and `Sell-Crystal`/`Buy-Crystal` pairs are excluded.
- **Wire numbers:** Power BI shows wire numbers with a trailing `.0`. `parse.wire()` strips it.
- **Nicola family Private Debt:** the nine requests (wires `20260925000531`–`549`) are removed from forward Private Debt views. Their totals are in `pbi_adj_nicola_pd`, and the per-class split is in `pbi_adj_nicola_pd_class`.
- **Simcorp-only real estate requests:** a Simcorp real estate sell counts if it meets all of these:
  - its create date is on or after Sep 24;
  - its dealing month is the create month + 6. The dealing date is `re_original_trade_date` when the trade date is the 2029-12-31 placeholder, otherwise the trade date;
  - the extract has no order in the same class with the same dealing date and an amount within 2%.
- **Real estate queue:** Simcorp parks the real estate queue at 2029-12-31. Every parked order checked so far has a past origin date.
- **Currency:** `data.currency(fund_id)` gives each share class's currency.
  - N-series classes (`NWMxx6yz`): an odd last digit is USD.
  - Otherwise the first three digits decide (`USD_BASES`).
  - The rule has been checked against `usd_net_amt` in the extract.

## Daily / weekly refresh

1. Ingest new legacy files: `python ingest.py`. The Sep 30 2026 file must not be re-ingested (it was locked on 2026-11-02), so when that file's hash has changed, stage the new files in a separate folder and use `--folder`.
2. Through the claude.ai Power BI connector, run each query in `pbi/queries/`, changing the dates in each. Save each result and load it:
   ```
   python -m pbi.load sells        <result>   # simcorp_sells_daily.dax
   python -m pbi.load nicola       <result>   # nicola_pd_wires.dax
   python -m pbi.load nicola_class <result>   # nicola_pd_wires_by_class.dax
   python -m pbi.load dates        <result>   # order_dates.dax  (run daily; history builds up)
   python -m pbi.load byclass      <result>   # sells_by_class_latest.dax
   ```
   A result can be the saved connector output (JSON) or a plain `.csv` file.
3. Build the pages:
   ```
   python -m pbi.pages.pending_by_month_page 2026-11-06 1.40117 out.html
   python -m pbi.pages.refresh_pages <folder of downloaded live pages>
   python -m pbi.pages.activity <activity_orders result> <folder of downloaded live pages>
   ```
   `refresh_pages` and `activity` edit the live pages in place by finding their current wording. When a page's wording changes, update the matching anchors.

## Published pages

| Page | Link |
|---|---|
| Pending Redemptions by Month | https://claude.ai/artifact/3Gu3vA3VjD9kK29ktfFBXE |
| Private Equity queue | https://claude.ai/artifact/Ts5rcet9kovm11TFckvxJS |
| Real Estate queue | https://claude.ai/artifact/UGQsJJpek5oiRP9B9LJpnk |
| Six-Month Redemption Pipeline | https://claude.ai/artifact/KmsUEd1jevf8Wv9bPaB3BE |
| Six-Month Redemptions by Fund | https://claude.ai/artifact/FXddC6KnicNFeGF7oJgjXh |
| Redemption Queue Monthly Buildup | https://claude.ai/artifact/5SVrbqLEywZbaEkN78WKxi |
| Illiquid Fund Redemption Activity | https://claude.ai/artifact/8BB9TYQbEYX5zAFhixgHpN |
