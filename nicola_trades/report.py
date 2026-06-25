"""Excel report generation with consistent formatting."""

from pathlib import Path

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.utils.dataframe import dataframe_to_rows

# Colour palette
DARK_BLUE  = "1F4E79"
WHITE      = "FFFFFF"
RED_BG     = "FCE4D6"
GREEN_BG   = "E2EFDA"
GREY_BG    = "F2F2F2"
HEADER_FG  = WHITE


def _apply_header(ws, fill_hex: str = DARK_BLUE):
    fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
    font = Font(color=HEADER_FG, bold=True)
    for cell in ws[1]:
        cell.fill = fill
        cell.font = font
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _apply_row_fill(ws, fill_hex: str):
    fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.fill = fill


def _autofit(ws, max_width: int = 40):
    for col in ws.columns:
        width = max(
            (len(str(cell.value)) if cell.value is not None else 0) for cell in col
        )
        ws.column_dimensions[get_column_letter(col[0].column)].width = min(width + 2, max_width)


def _write_sheet(wb: Workbook, name: str, df: pd.DataFrame, row_fill: str | None = None):
    ws = wb.create_sheet(name)
    for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=1):
        ws.append(row)
    _apply_header(ws)
    if row_fill:
        _apply_row_fill(ws, row_fill)
    _autofit(ws)
    ws.freeze_panes = "A2"
    if ws.max_row > 1:
        ws.auto_filter.ref = ws.dimensions


def write_comparison(result: dict, output: Path, tx_type: str = "Sell") -> Path:
    """Write a comparison result dict to an Excel file with three tabs."""
    date1, date2   = result["date1"], result["date2"]
    removed, added = result["removed"], result["added"]

    from nicola_trades.compare import fund_summary
    summary = fund_summary(removed, added)

    # Human-readable column names for the detail tabs
    detail_cols = {
        "wire_order_num": "Wire Order #",
        "investor_name":  "Investor Name",
        "sin":            "SIN",
        "fund_group":     "Fund Group",
        "canonical_fund": "Fund",
        "fund_id":        "Fund ID",
        "tx_type":        "Tx Type",
        "trade_date":     "Trade Date",
        "settle_date":    "Settle Date",
        "gross_amt":      "Gross Amt",
        "cdn_net_amt":    "CDN Net Amt",
        "usd_net_amt":    "USD Net Amt",
        "shares_units":   "Units",
        "plan_desc":      "Plan",
    }
    summary_cols = {
        "fund_group":     "Fund Group",
        "canonical_fund": "Fund",
        "removed_count":  "Removed Count",
        "removed_gross":  "Removed Gross Amt",
        "added_count":    "Added Count",
        "added_gross":    "Added Gross Amt",
    }

    wb = Workbook()
    wb.remove(wb.active)  # remove default sheet

    _write_sheet(wb, "Summary by Fund", summary.rename(columns=summary_cols))
    _write_sheet(
        wb,
        f"Removed ({date1} → gone by {date2})",
        removed.rename(columns=detail_cols),
        row_fill=RED_BG,
    )
    _write_sheet(
        wb,
        f"Added (new in {date2})",
        added.rename(columns=detail_cols),
        row_fill=GREEN_BG,
    )

    wb.save(output)
    return output


def write_timeseries(pivot: pd.DataFrame, raw: pd.DataFrame, output: Path) -> Path:
    """Write a time series pivot + raw data to Excel."""
    wb = Workbook()
    wb.remove(wb.active)

    _write_sheet(wb, "Trend Summary", pivot, row_fill=GREY_BG)
    _write_sheet(wb, "Raw Data", raw)

    wb.save(output)
    return output
