"""Import UCDP/PRIO Armed Conflict Dataset as country-year tables.

Source: https://ucdp.uu.se/downloads/ (version pinned below; licence CC BY 4.0, see
data/datasets/ucdp-prio-armed-conflict.yaml). Coverage starts in 1946: a country-year
missing from these tables means no conflict was recorded, and years before 1946 are
simply not covered.

  .cache/venv/bin/python tools/importers/ucdp_armed_conflict.py   (or plain python)

Tables (one row per country-year with at least one conflict located there, by gwno_loc):
  ucdp-any-conflict               1 if any state-based armed conflict (25+ battle deaths)
  ucdp-intrastate-max-intensity   highest intensity of intrastate conflicts that year:
                                  1 = minor (25-999 deaths), 2 = war (1,000+)

Countries: UCDP uses Gleditsch-Ward codes. tools/importers/gw_to_iso3.json maps them to
ISO3, built from the Correlates of War codes in V-Dem v16 (which match Gleditsch-Ward for
every code UCDP uses) plus Grenada (55), Brunei (835) and Serbia after 2006 (340).
Hyderabad (751, 1948) is not a modern state and is dropped.
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
URL = "https://ucdp.uu.se/downloads/ucdpprio/ucdp-prio-acd-261-csv.zip"
DROP = {751: "Hyderabad (1948)"}
REGIONS = ["americas", "western-europe", "russia-eastern-europe", "middle-east-north-africa",
           "south-central-asia", "east-asia", "sub-saharan-africa", "south-east-asia"]
SOURCE = {"url": "https://ucdp.uu.se/downloads/", "title": "UCDP Dataset Download Center",
          "publisher": "Uppsala Conflict Data Program", "type": "primary"}


def rows():
    path = CACHE / "ucdp" / Path(URL).name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "threads-of-history importer"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    with zipfile.ZipFile(path) as z:
        name = next(n for n in z.namelist() if n.endswith(".csv"))
        yield from csv.DictReader(io.TextIOWrapper(z.open(name), encoding="utf-8"))


def main():
    gw = {int(k): v for k, v in json.loads((Path(__file__).parent / "gw_to_iso3.json").read_text()).items()}
    any_conflict, intra = {}, defaultdict(int)
    unmapped, last = set(), 0
    for r in rows():
        if r["version"] != VERSION:
            raise SystemExit(f"file is version {r['version']}, expected {VERSION}")
        year = int(r["year"])
        last = max(last, year)
        for g in (int(x) for x in r["gwno_loc"].split(",")):
            if g in DROP:
                continue
            iso = gw.get(g)
            if iso is None:
                unmapped.add(g)
                continue
            any_conflict[(iso, year)] = 1
            if r["type_of_conflict"] in ("3", "4"):
                intra[(iso, year)] = max(intra[(iso, year)], int(r["intensity_level"]))
    if unmapped:
        raise SystemExit(f"no ISO3 code for Gleditsch-Ward codes {sorted(unmapped)}; add them to gw_to_iso3.json")
    span = {"start": "1946", "end": str(last), "precision": "year"}
    for table, data, title, summary, unit in [
        ("ucdp-any-conflict", any_conflict, "State-based armed conflict (UCDP/PRIO)",
         "Country-years with at least one state-based armed conflict (25 or more battle deaths) on the country's territory.", "1 = yes"),
        ("ucdp-intrastate-max-intensity", intra, "Intrastate conflict intensity (UCDP/PRIO)",
         "Highest intensity of intrastate conflicts on the country's territory: 1 minor (25-999 battle deaths), 2 war (1,000 or more).", "level (1-2)"),
    ]:
        path = write_table(table, [(iso, str(y), v) for (iso, y), v in data.items()])
        write_series({"id": table, "title": title, "summary": summary, "occurred": span,
                      "threads": ["usru"], "regions": REGIONS, "importance": 2, "unit": unit,
                      "dataset": "ucdp-prio-armed-conflict", "indicator": table.removeprefix("ucdp-"),
                      "table": f"tables/{table}.csv", "sources": [SOURCE]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(data)} rows")
    print("dropped:", ", ".join(DROP.values()))


if __name__ == "__main__":
    main()
