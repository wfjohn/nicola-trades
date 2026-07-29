# Redemption Changes Report

Generate the weekly Added / Removed / Net Added redemptions table for all illiquid funds.

## Usage

```
/redemption-changes <from_date> <to_date>
```

Dates must be in `YYYY-MM-DD` format (e.g. `2026-07-06 2026-07-13`).

## What this does

Runs a Python query against `data/trades.db` comparing two snapshot dates and produces a table showing:

- **Added**: Sell trades present in `to_date` snapshot but NOT in `from_date` snapshot
- **Removed**: Sell trades present in `from_date` snapshot but NOT in `to_date` snapshot, with standard exclusions applied
- **Net Added**: Added minus Removed

All dollar amounts are rounded to the nearest $1,000.

## Standard exclusions (always applied to Removed)

- Trade dates matching the current settlement month (the month containing `to_date`) — these disappear from the queue because they were paid out, not cancelled
- Wire order `AAK0X2H` — Kefin Management Ltd (confirmed non-real cancellation, Dec 31 US RE LP, ~$7.9M)

## Illiquid funds covered

Canadian Real Estate LP, Diversified Real Estate, Diversified Private Assets, Global Infrastructure LP, Private Debt, Private Equity LP, U.S. Real Estate LP, Value Add Real Estate LP, Venture Capital LP

---

## Instructions

When this command is invoked with two dates, write and run the following Python script, substituting the actual dates:

```python
import sqlite3
conn = sqlite3.connect(r'c:\Users\wjohn\OneDrive - Nicola Wealth\Dev\nicola-trades\data\trades.db')

FROM_DATE = '$ARGUMENTS'.split()[0]  # first argument
TO_DATE = '$ARGUMENTS'.split()[1]    # second argument

# Derive the settlement month to exclude (month of to_date)
settle_month = TO_DATE[:7]  # e.g. '2026-07'

illiquid_funds = [
    'Canadian Real Estate LP',
    'Diversified Real Estate',
    'Diversified Private Assets',
    'Global Infrastructure LP',
    'Private Debt',
    'Private Equity LP',
    'U.S. Real Estate LP',
    'Value Add Real Estate LP',
    'Venture Capital LP',
]
placeholders = ','.join('?' * len(illiquid_funds))

added = {f: t for f, t in conn.execute(f'''
    SELECT t2.canonical_fund, ROUND(ABS(SUM(t2.gross_amt)) / 1000) * 1000
    FROM trades t2 JOIN snapshots s2 ON t2.snapshot_id = s2.id
    WHERE s2.snapshot_date = ? AND t2.tx_type = 'Sell'
      AND t2.canonical_fund IN ({placeholders})
      AND t2.wire_order_num NOT IN (
          SELECT t1.wire_order_num FROM trades t1 JOIN snapshots s1 ON t1.snapshot_id = s1.id
          WHERE s1.snapshot_date = ? AND t1.tx_type = 'Sell'
            AND t1.canonical_fund IN ({placeholders})
      )
    GROUP BY t2.canonical_fund
''', [TO_DATE] + illiquid_funds + [FROM_DATE] + illiquid_funds).fetchall()}

removed = {f: t for f, t in conn.execute(f'''
    SELECT t1.canonical_fund, ROUND(ABS(SUM(t1.gross_amt)) / 1000) * 1000
    FROM trades t1 JOIN snapshots s1 ON t1.snapshot_id = s1.id
    WHERE s1.snapshot_date = ? AND t1.tx_type = 'Sell'
      AND t1.canonical_fund IN ({placeholders})
      AND t1.trade_date NOT LIKE ? 
      AND t1.wire_order_num != 'AAK0X2H'
      AND t1.wire_order_num NOT IN (
          SELECT t2.wire_order_num FROM trades t2 JOIN snapshots s2 ON t2.snapshot_id = s2.id
          WHERE s2.snapshot_date = ? AND t2.tx_type = 'Sell'
            AND t2.canonical_fund IN ({placeholders})
      )
    GROUP BY t1.canonical_fund
''', [FROM_DATE] + illiquid_funds + [settle_month + '%'] + [TO_DATE] + illiquid_funds).fetchall()}

print(f'\nAdded / Removed / Net Added — {FROM_DATE} to {TO_DATE}')
print(f'(Excludes {settle_month} settlements and Kefin wire AAK0X2H from Removed)')
print()
print(f"{'Fund':<30}  {'Added':>12}  {'Removed':>12}  {'Net Added':>12}")
print('-' * 72)
tot_a = tot_r = 0
for fund in illiquid_funds:
    a = added.get(fund, 0)
    r = removed.get(fund, 0)
    tot_a += a; tot_r += r
    net = a - r
    a_s = f'${a:>10,}' if a else f'{"—":>12}'
    r_s = f'${r:>10,}' if r else f'{"—":>12}'
    net_s = ('+' if net > 0 else '') + f'${net:>9,}' if (a or r) else f'{"—":>12}'
    print(f'{fund:<30}  {a_s}  {r_s}  {net_s}')
print('-' * 72)
net_tot = tot_a - tot_r
net_sign = '+' if net_tot >= 0 else ''
print(f"{'TOTAL':<30}  ${tot_a:>10,}  ${tot_r:>10,}  {net_sign}${net_tot:>9,}")
conn.close()
```

Write this script to the scratchpad at `C:\Users\wjohn\AppData\Local\Temp\claude\c--Users-wjohn-OneDrive---Nicola-Wealth-Dev-nicola-trades\scratchpad\redq.py`, substituting `$ARGUMENTS` with the actual dates provided, then run it with `python redq.py`.

If only one date is provided, ask the user for both dates before running.
