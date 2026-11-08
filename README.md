# nicola-trades

Weekly pending trade analysis for NWM fund operations.

Reads snapshot files from the SharePoint "Pending Trades" folder (synced via OneDrive),
stores them in a local SQLite database, and produces Excel comparison and time series reports.

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Workflows

### 1. Ingest new snapshots

Run this weekly (or whenever new files land in the SharePoint folder):

```bash
python ingest.py
```

Options:
```
--folder   Path to the Pending Trades folder (default: auto-detected from OneDrive)
--all      Re-ingest every file even if already in the database
```

### 1b. Power BI feed (Simcorp, from Sep 2026)

Non-real-estate funds now come from Simcorp via Power BI, and real estate still comes from the legacy files. The queries, the loaders (`python -m pbi.load ...`) and the page builders are in [`pbi/`](pbi/README.md).

### 2. Compare two dates

```bash
python compare.py --date1 2026-06-12 --date2 2026-06-19
```

Options:
```
--date1    Earlier snapshot date (YYYY-MM-DD)
--date2    Later snapshot date (YYYY-MM-DD)
--tx-type  Sell / Buy / Switch-In / Switch-Out / all  (default: Sell)
--output   Custom output path (default: reports/comparison_DATE1_vs_DATE2.xlsx)
--list-dates  Show all available snapshot dates in the database
```

Output Excel tabs:
- **Summary by Fund** — removed/added counts and amounts by canonical fund
- **Removed** — trades in date1 that are gone by date2 (red)
- **Added** — trades new in date2 (green)

### 3. Time series trend

```bash
python timeseries.py
python timeseries.py --fund "Core Portfolio"
python timeseries.py --from 2026-01-01 --to 2026-06-30
```

Options:
```
--fund     Filter to a single canonical fund name
--from     Start date (YYYY-MM-DD)
--to       End date (YYYY-MM-DD)
--tx-type  Sell / Buy / all  (default: Sell)
--output   Custom output path (default: reports/timeseries.xlsx)
```

Output Excel tabs:
- **Trend Summary** — pivot: funds as rows, snapshot dates as columns, values = gross amount
- **Raw Data** — one row per (date, fund) with count and gross amount

---

## Fund mapping

Edit `config/funds.yaml` to add new fund IDs or adjust canonical names.
Canonical names match `ClientFlows/utils.py` so both projects share the same fund taxonomy.

```yaml
funds:
  NWM250: "Core Portfolio"
  NWM254: "Core Portfolio"
  # ...
```

Unknown Fund IDs fall back to the raw Fund Desc from Excel — nothing is lost.

---

## Project structure

```
nicola-trades/
├── nicola_trades/      # core library
│   ├── db.py           # SQLite connection + schema
│   ├── loader.py       # Excel parsing + filename date extraction
│   ├── funds.py        # Fund ID → canonical name (reads config/funds.yaml)
│   ├── compare.py      # two-snapshot diff logic
│   ├── timeseries.py   # trend aggregation
│   └── report.py       # Excel output formatting
├── config/
│   └── funds.yaml      # Fund ID → canonical name mapping
├── data/               # SQLite database (gitignored)
├── reports/            # Excel output (gitignored)
├── ingest.py           # CLI: import new snapshots
├── compare.py          # CLI: compare two dates
└── timeseries.py       # CLI: trend report
```
