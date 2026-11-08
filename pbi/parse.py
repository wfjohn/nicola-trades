"""Read a saved Power BI ExecuteQuery result.

Small results come back as JSON tables; large ones as a short preview plus an embedded CSV resource.
`tables(path)` returns a list of (kind, rows) per result block, kind in {'json', 'csv', 'preview'}.
"""
import csv
import io
import json
import re


def tables(path):
    parts = json.load(open(path, encoding='utf-8'))
    out = []
    for p in parts:
        t = p.get('text', '')
        if t.startswith('[Resource from'):
            body = t.split(']', 1)[1].lstrip()
            out.append(('csv', list(csv.DictReader(io.StringIO(body)))))
            continue
        try:
            j = json.loads(t)
        except ValueError:
            continue
        er = j.get('executionResult')
        if isinstance(er, dict):
            for tb in er.get('tables', []):
                cols = [c['name'] for c in tb['columns']]
                out.append(('json', [dict(zip(cols, r)) for r in tb['rows']]))
        elif isinstance(er, str):
            m = re.search(r'Showing first (\d+) of (\d+) rows', er)
            out.append(('preview', {'total': int(m.group(2)) if m else None}))
    return out


def rows(path, index=0):
    """The index-th data table (JSON or CSV) in a saved result; a plain .csv file is read directly."""
    if str(path).lower().endswith('.csv'):
        return list(csv.DictReader(open(path, encoding='utf-8-sig')))
    data = [r for k, r in tables(path) if k in ('json', 'csv')]
    return data[index]


def num(v):
    v = str(v).replace("'", '').replace(',', '').replace('"', '').strip()
    return float(v) if v not in ('', 'None', 'null') else 0.0


def iso(v):
    """'11/6/2026 12:00:00 AM', '2026-11-06T00:00:00' -> '2026-11-06'."""
    v = str(v)
    m = re.match(r'(\d{1,2})/(\d{1,2})/(\d{4})', v)
    return f'{m[3]}-{int(m[1]):02d}-{int(m[2]):02d}' if m else v[:10]


def wire(v):
    """Power BI stores Simcorp wire numbers as '20260925000542.0'."""
    return str(v).strip().removesuffix('.0')
