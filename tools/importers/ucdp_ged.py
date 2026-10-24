"""Import the UCDP Georeferenced Event Dataset (GED) as country-year tables of violence.

Source: https://ucdp.uu.se/downloads/ (version pinned below; licence CC BY 4.0, see
data/datasets/ucdp-ged.yaml). GED lists individual events of organized violence with dates
and places, from 1989. These tables summarise them by year, keeping some of the within-year
timing that yearly conflict codes lose:

  ucdp-ged-deaths            best estimate of deaths from all organized violence
  ucdp-ged-deaths-q4         deaths in events that started in October-December, to show
                             violence rising into the next year
  ucdp-ged-deaths-nonstate   deaths from non-state conflict and one-sided violence (types 2
                             and 3: armed groups fighting each other, attacks on civilians),
                             which often come before a state-based war
  ucdp-ged-active-months     number of months (0-12) with at least one event

Only country-years with at least one event get a row. Coverage starts in 1989, so from then
on a missing row means no recorded violence (the forecasting code treats it as 0); before
1989 it means "not covered".

  python tools/importers/ucdp_ged.py
"""
from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
import zipfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, write_series, write_table  # noqa: E402

VERSION = "26.1"
URL = "https://ucdp.uu.se/downloads/ged/ged261-csv.zip"
FIRST_YEAR = 1989
REGIONS = ["americas", "western-europe", "russia-eastern-europe", "middle-east-north-africa",
           "south-central-asia", "east-asia", "sub-saharan-africa", "south-east-asia"]
SOURCE = {"url": "https://ucdp.uu.se/downloads/", "title": "UCDP Dataset Download Center",
          "publisher": "Uppsala Conflict Data Program", "type": "primary"}
DROP = {751}


def events():
    path = CACHE / "ucdp" / Path(URL).name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "threads-of-history importer"})
        path.write_bytes(urllib.request.urlopen(req, timeout=600).read())
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        yield from csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8"))


def main():
    gw = {int(k): v for k, v in json.loads((Path(__file__).parent / "gw_to_iso3.json").read_text()).items()}
    deaths, q4, nonstate = defaultdict(float), defaultdict(float), defaultdict(float)
    months = defaultdict(set)
    unmapped, last, n = set(), 0, 0
    for e in events():
        g = int(e["country_id"])
        if g in DROP:
            continue
        iso = gw.get(g)
        if iso is None:
            unmapped.add((g, e["country"]))
            continue
        year, month = int(e["date_start"][:4]), int(e["date_start"][5:7])
        key = (iso, year)
        best = float(e["best"] or 0)
        deaths[key] += best
        if month >= 10:
            q4[key] += best
        if e["type_of_violence"] in ("2", "3"):
            nonstate[key] += best
        months[key].add(month)
        last, n = max(last, year), n + 1
    if unmapped:
        raise SystemExit(f"no ISO3 code for {sorted(unmapped)}; add them to gw_to_iso3.json")
    span = {"start": str(FIRST_YEAR), "end": str(last), "precision": "year"}
    for table, data, title, summary, unit in [
        ("ucdp-ged-deaths", deaths, "Deaths from organized violence (UCDP GED)",
         "Best estimate of deaths from state-based, non-state and one-sided violence on the country's territory.", "deaths"),
        ("ucdp-ged-deaths-q4", q4, "Deaths in October-December (UCDP GED)",
         "Best estimate of deaths in events that began in the last three months of the year.", "deaths"),
        ("ucdp-ged-deaths-nonstate", nonstate, "Deaths from non-state and one-sided violence (UCDP GED)",
         "Best estimate of deaths from fighting between armed groups and from attacks on civilians.", "deaths"),
        ("ucdp-ged-active-months", {k: len(v) for k, v in months.items()}, "Months with organized violence (UCDP GED)",
         "Number of months in the year with at least one recorded event of organized violence.", "months (0-12)"),
    ]:
        path = write_table(table, [(iso, str(y), v) for (iso, y), v in data.items()])
        write_series({"id": table, "title": title, "summary": summary, "occurred": span,
                      "threads": ["usru"], "regions": REGIONS, "importance": 2, "unit": unit,
                      "dataset": "ucdp-ged", "indicator": table.removeprefix("ucdp-ged-"),
                      "table": f"tables/{table}.csv", "sources": [SOURCE]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(data)} rows")
    print(f"{n} events")


if __name__ == "__main__":
    main()
