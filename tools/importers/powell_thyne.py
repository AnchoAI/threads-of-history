"""Import Powell & Thyne's list of coup attempts as private country-year tables.

PRIVATE: the dataset's licence is not confirmed (data/datasets/powell-thyne.yaml), so this
writes to .cache/private-tables/, which git ignores, and adds no series items. forecast/
reads private tables when data/tables/ has no table of that name. Don't move these tables
into data/ until the licence allows redistribution.

Source: the authors' current file, linked from https://jonathanmpowell.com/coups/
  mkdir -p .cache/private-raw && curl -L -o .cache/private-raw/pt_20260829.csv \\
      https://jonathanmpowell.com/wp-content/uploads/2026/08/pt_20260829.csv
  python tools/importers/powell_thyne.py

Columns: country, ccode (Correlates of War), year, month, day, coup (2 = successful, 1 = failed).
Coverage is every state from 1950, so country-years with no coup get 0: rows are written for
every country-year in the V-Dem electoral democracy table from 1950.
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, ROOT  # noqa: E402

RAW = CACHE / "private-raw" / "pt_20260829.csv"
OUT = CACHE / "private-tables"
FIRST_YEAR = 1950
EXTRA_CODES = {"54": "DMA"}  # Dominica, not in V-Dem's code list


def main():
    codes = {**json.loads((Path(__file__).parent / "gw_to_iso3.json").read_text()), **EXTRA_CODES}
    success, attempt = Counter(), Counter()
    for r in csv.DictReader(RAW.open(encoding="utf-8-sig")):
        iso = codes.get(r["ccode"])
        if not iso:
            raise SystemExit(f"no ISO3 code for {r['country']} (ccode {r['ccode']})")
        key = (iso, int(r["year"]))
        attempt[key] += 1
        success[key] += r["coup"] == "2"
    years = set()
    with (ROOT / "data" / "tables" / "vdem-electoral-democracy.csv").open(encoding="utf-8") as f:
        years = {(r["entity"], int(r["at"][:4])) for r in csv.DictReader(f) if int(r["at"][:4]) >= FIRST_YEAR}
    last = max(y for _, y in attempt)
    years = {k for k in years if k[1] <= last} | set(attempt)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, counts in (("pt-coup-attempts", attempt), ("pt-coup-successes", success)):
        path = OUT / f"{name}.csv"
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["entity", "at", "value"])
            for iso, y in sorted(years):
                w.writerow([iso, y, counts.get((iso, y), 0)])
        print(f"wrote {path.relative_to(ROOT)}: {len(years)} rows, {sum(counts.values())} coups")


if __name__ == "__main__":
    main()
