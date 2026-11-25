"""Load country-year tables from data/tables/ without looking ahead.

A table is a CSV with columns entity, at, value and optionally published (see
tools/importers/common.py). load_table() returns {(iso3, year): value}.

With known_before=X, rows published in year X or later are dropped, so a backtest
pretending to stand at the start of year X sees only what had been published by then.
Rows without a published date count as known at the end of the year they describe.

Tables from datasets whose licence doesn't allow redistribution yet live outside git in
.cache/private-tables/ (see tools/importers/powell_thyne.py). load_table() falls back to
them when data/tables/ has no table of that name; has_table() says whether either exists.
"""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "data" / "tables"
PRIVATE = ROOT / ".cache" / "private-tables"


def has_table(name: str, tables: Path = TABLES) -> bool:
    return (tables / f"{name}.csv").exists() or (tables == TABLES and (PRIVATE / f"{name}.csv").exists())


def load_table(name: str, known_before: int | None = None, tables: Path = TABLES) -> dict[tuple[str, int], float]:
    path = tables / f"{name}.csv"
    if not path.exists() and tables == TABLES:
        path = PRIVATE / f"{name}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} is missing; run its importer first (see data/datasets/)")
    out = {}
    with path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            year = int(row["at"][:4])
            if known_before is not None:
                published = row.get("published") or ""
                # known at the start of known_before if published in an earlier year,
                # or, with no publication date, if the year it describes is over
                known = int(published[:4]) < known_before if published else year < known_before
                if not known:
                    continue
            out[(row["entity"], year)] = float(row["value"])
    return out
