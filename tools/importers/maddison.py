"""Import the Maddison Project Database 2023: GDP per capita and population, 1900 onwards.

Source: Dataverse doi:10.34894/INZBF2, file maddison2023_web.dta (licence CC BY 4.0; see
data/datasets/maddison-project.yaml, including its rule that graphs credit the original
per-country sources).

  .cache/venv/bin/python tools/importers/maddison.py   (needs pandas: tools/importers/requirements.txt)

Countries: Maddison uses ISO3, with CSK (Czechoslovakia), SUN (USSR) and YUG (Yugoslavia) for
the former federations, which are ISO 3166-3 codes. Rows with no value are skipped.
"""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, write_series, write_table  # noqa: E402

VERSION = "2023"
FILE_ID = 421303  # maddison2023_web.dta on dataverse.nl
URL = f"https://dataverse.nl/api/access/datafile/{FILE_ID}"
FIRST_YEAR = 1900
REGIONS = ["americas", "western-europe", "russia-eastern-europe", "middle-east-north-africa",
           "south-central-asia", "east-asia", "sub-saharan-africa", "south-east-asia"]
SOURCE = {"url": "https://www.rug.nl/ggdc/historicaldevelopment/maddison/releases/maddison-project-database-2023",
          "title": "Maddison Project Database 2023", "publisher": "Groningen Growth and Development Centre",
          "type": "scholarly"}


def load():
    import pandas as pd

    path = CACHE / "maddison" / "maddison2023_web.dta"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(URL, headers={"User-Agent": "threads-of-history importer"})
        path.write_bytes(urllib.request.urlopen(req, timeout=300).read())
    return pd.read_stata(path)


def main():
    df = load()
    df = df[df["year"] >= FIRST_YEAR]
    last = int(df["year"].max())
    for column, table, title, summary, unit in [
        ("gdppc", "maddison-gdp-per-capita", "GDP per capita (Maddison Project)",
         "Real GDP per capita in 2011 US dollars, from the Maddison Project Database 2023.", "2011 US$"),
        ("pop", "maddison-population", "Population (Maddison Project)",
         "Population in thousands, from the Maddison Project Database 2023.", "thousands"),
    ]:
        rows = [(iso, str(int(y)), float(v)) for iso, y, v in zip(df["countrycode"], df["year"], df[column])]
        path = write_table(table, rows)
        write_series({"id": table, "title": title, "summary": summary,
                      "occurred": {"start": str(FIRST_YEAR), "end": str(last), "precision": "year"},
                      "threads": ["econ-crises"], "regions": REGIONS, "importance": 2, "unit": unit,
                      "dataset": "maddison-project", "indicator": column, "table": f"tables/{table}.csv",
                      "sources": [SOURCE]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {sum(1 for r in rows if r[2] == r[2])} rows")


if __name__ == "__main__":
    main()
