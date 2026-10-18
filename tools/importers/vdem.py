"""Import three V-Dem indices as country-year tables (1900 onwards).

Source: the V-Dem Institute's own data package on GitHub (vdeminstitute/vdemdata), which
ships the Country-Year Full+Others dataset as vdem.RData. The website's download needs
a registration form; the package is the same data from the same publisher. See
data/datasets/v-dem.yaml for the version, licence (CC BY-SA 4.0) and citation.

  python -m venv .cache/venv && .cache/venv/bin/pip install -r tools/importers/requirements.txt
  git clone --depth 1 https://github.com/vdeminstitute/vdemdata .cache/vdemdata
  .cache/venv/bin/python tools/importers/vdem.py

Countries: V-Dem's country_text_id is ISO 3166-1 alpha-3 for current states and the
ISO 3166-3 former code for South Yemen (YMD), South Vietnam (VDR) and East Germany (DDR).
Kosovo keeps XKX, the code in common use. Units that are not states are dropped and
listed below.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, write_series, write_table  # noqa: E402

PINNED_VERSION = "16.0"
FIRST_YEAR = 1900
DROPPED = {  # V-Dem units that are not sovereign states, left out of country-year tables
    "PSG": "Palestine/Gaza (V-Dem codes Gaza separately from the West Bank, PSE)",
    "PSB": "Palestine/British Mandate (1918-1948)",
    "SML": "Somaliland (not internationally recognised)",
    "ZZB": "Zanzibar (before union with Tanganyika)",
}
INDICATORS = [
    ("v2x_polyarchy", "vdem-electoral-democracy", "Electoral democracy index (V-Dem)",
     "How far the ideal of electoral democracy is achieved, from 0 to 1 (V-Dem's polyarchy index)."),
    ("v2x_libdem", "vdem-liberal-democracy", "Liberal democracy index (V-Dem)",
     "How far the ideal of liberal democracy is achieved, from 0 to 1."),
    ("v2x_civlib", "vdem-civil-liberties", "Civil liberties index (V-Dem)",
     "How far civil liberties are respected, from 0 to 1."),
]
REGIONS = ["americas", "western-europe", "russia-eastern-europe", "middle-east-north-africa",
           "south-central-asia", "east-asia", "sub-saharan-africa", "south-east-asia"]


def load():
    import rdata  # only needed when importing

    pkg = CACHE / "vdemdata"
    version = next(l.split(":", 1)[1].strip() for l in (pkg / "DESCRIPTION").read_text().splitlines()
                   if l.startswith("Version:"))
    if version != PINNED_VERSION:
        raise SystemExit(f"vdemdata is version {version}, expected {PINNED_VERSION}; update data/datasets/v-dem.yaml first")
    return rdata.read_rda(str(pkg / "data" / "vdem.RData"))["vdem"]


def main():
    df = load()
    df = df[df["year"] >= FIRST_YEAR]
    dropped = sorted(set(df["country_text_id"]) & set(DROPPED))
    df = df[~df["country_text_id"].isin(DROPPED)]
    last = int(df["year"].max())
    for column, table, title, summary in INDICATORS:
        rows = [(iso, str(int(y)), float(v)) for iso, y, v in zip(df["country_text_id"], df["year"], df[column])]
        path = write_table(table, rows)
        write_series({
            "id": table, "title": title, "summary": summary,
            "occurred": {"start": str(FIRST_YEAR), "end": str(last), "precision": "year"},
            "threads": ["revolutions"], "regions": REGIONS, "importance": 2,
            "unit": "index (0-1)", "dataset": "v-dem", "indicator": column, "table": f"tables/{table}.csv",
            "sources": [{"url": "https://v-dem.net/data/the-v-dem-dataset/", "title": "The V-Dem Dataset",
                         "publisher": "V-Dem Institute", "type": "primary"}],
        })
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")
    print("dropped units:", ", ".join(f"{k} ({DROPPED[k]})" for k in dropped))


if __name__ == "__main__":
    main()
