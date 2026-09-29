"""Shared helpers for importers. Each importer turns one external dataset into
CSV tables under data/tables/ plus the series items that describe them.

An importer script should:
1. download a pinned version of the dataset (the version in its data/datasets/ entry)
   into a cache folder outside git, e.g. .cache/<dataset-id>/;
2. build rows of (ISO3, date, value) for each measure it imports;
3. call write_table() and write_series() for each measure;
4. print what it wrote, then run tools/validate.py.

Running an importer twice on the same download must give identical files.
"""
from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "data"
CACHE = ROOT / ".cache"

sys.path.insert(0, str(ROOT / "tools"))
from validate import DATE, ISO3, date_parts  # noqa: E402


def write_table(name: str, rows: list[tuple[str, str, float] | tuple[str, str, float, str]]) -> Path:
    """Write data/tables/<name>.csv. Rows are (iso3, at, value[, published]).

    Drops missing values (None or NaN), refuses bad codes and dates, and
    sorts by entity then date so reruns are byte-identical.
    """
    clean = []
    for row in rows:
        entity, at, value = row[0], str(row[1]), row[2]
        if value is None or (isinstance(value, float) and math.isnan(value)):
            continue
        if not ISO3.match(entity):
            raise ValueError(f"{name}: {entity!r} is not an ISO3 code")
        if not DATE.match(at):
            raise ValueError(f"{name}: {at!r} is not a date")
        clean.append((entity, at, _fmt(float(value)), *row[3:]))
    clean.sort(key=lambda r: (r[0], date_parts(r[1])))
    has_published = any(len(r) > 3 for r in clean)

    path = DATA / "tables" / f"{name}.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["entity", "at", "value", *(["published"] if has_published else [])])
        for r in clean:
            w.writerow(list(r) + ([""] if has_published and len(r) == 3 else []))
    return path


def write_series(item: dict) -> Path:
    """Write data/series/<id>.yaml for a table-backed series.

    `item` needs at least id, title, summary, occurred, threads, regions,
    importance, unit, dataset, indicator, table and sources. review defaults
    to unverified: imported numbers are only as good as the check of the
    dataset they came from.
    """
    item = {"review": {"status": "unverified"}, **item}
    path = DATA / "series" / f"{item['id']}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(item, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
    return path


def _fmt(v: float) -> str:
    """Shortest exact text for a number: 7.0 -> '7', 0.125 -> '0.125'."""
    return str(int(v)) if v.is_integer() else repr(v)
