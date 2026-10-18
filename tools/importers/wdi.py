"""Import World Bank World Development Indicators through the World Bank API.

First indicator: infant mortality (SP.DYN.IMRT.IN, deaths per 1,000 live births), which the
Political Instability Task Force found to be one of the strongest predictors of instability.
Licence: CC BY 4.0 plus the World Bank's terms, which require the credit line
"The World Bank: <dataset name>: <data source>"; see data/datasets/world-bank-wdi.yaml.
Each indicator's own licence is checked in the API metadata before import.

  python tools/importers/wdi.py

Only real countries are kept: the API's regional and income aggregates are dropped using
the API's own country list (region "Aggregates").
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CACHE, write_series, write_table  # noqa: E402

API = "https://api.worldbank.org/v2"
INDICATORS = [
    ("SP.DYN.IMRT.IN", "wdi-infant-mortality", "Infant mortality rate (World Bank)",
     "Deaths of infants under one year old per 1,000 live births (World Bank, World Development Indicators).",
     "per 1,000 live births"),
]
REGIONS = ["americas", "western-europe", "russia-eastern-europe", "middle-east-north-africa",
           "south-central-asia", "east-asia", "sub-saharan-africa", "south-east-asia"]


def get(url):
    cache = CACHE / "wdi" / (url.split("/v2/")[1].replace("/", "_").replace("?", "_").replace("&", "_") + ".json")
    if cache.exists():
        return json.loads(cache.read_text())
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "threads-of-history importer"})
            data = json.load(urllib.request.urlopen(req, timeout=120))
            break
        except Exception:
            time.sleep(5 * (attempt + 1))
    else:
        raise SystemExit(f"could not fetch {url}")
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data))
    return data


def main():
    countries = get(f"{API}/country?format=json&per_page=400")[1]
    real = {c["id"] for c in countries if c["region"]["value"] != "Aggregates"}
    for code, table, title, summary, unit in INDICATORS:
        meta = get(f"{API}/indicator/{code}?format=json")[1][0]
        src = get(f"{API}/sources/2/indicators/{code}/metadata?format=json")  # licence fields live here
        notes = json.dumps(src)
        if "CC BY-4.0" not in notes and "CC BY 4.0" not in notes:
            raise SystemExit(f"{code}: licence in API metadata is not CC BY 4.0; check before importing")
        data = get(f"{API}/country/all/indicator/{code}?format=json&per_page=20000&date=1960:2030")[1]
        rows = [(d["countryiso3code"], d["date"], d["value"]) for d in data
                if d["countryiso3code"] in real and d["value"] is not None]
        last = max(int(r[1]) for r in rows)
        path = write_table(table, rows)
        write_series({"id": table, "title": title, "summary": summary,
                      "occurred": {"start": "1960", "end": str(last), "precision": "year"},
                      "threads": ["industry"], "regions": REGIONS, "importance": 2, "unit": unit,
                      "dataset": "world-bank-wdi", "indicator": code, "table": f"tables/{table}.csv",
                      "sources": [{"url": f"https://data.worldbank.org/indicator/{code}", "title": meta["name"],
                                   "publisher": "The World Bank: World Development Indicators", "type": "primary"}]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")


if __name__ == "__main__":
    main()
