"""Import World Bank World Development Indicators through the World Bank API.

Tables:
  wdi-infant-mortality  SP.DYN.IMRT.IN, deaths per 1,000 live births. The Political Instability
                        Task Force found it one of the strongest predictors of instability.
  wdi-inflation         FP.CPI.TOTL.ZG, consumer price inflation, % per year.
  wdi-youth-bulge       people aged 15-24 as a share of everyone aged 15 and over, the usual
                        "youth bulge" measure (Urdal). Built from WDI's age shares by sex
                        (SP.POP.1519/2024.MA/FE.5Y), totals by sex (SP.POP.TOTL.MA/FE.IN) and the
                        under-15 share (SP.POP.0014.TO.ZS). WDI takes these from UN World
                        Population Prospects.
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
    ("FP.CPI.TOTL.ZG", "wdi-inflation", "Inflation, consumer prices (World Bank)",
     "Annual change in consumer prices, in percent (World Bank, World Development Indicators).", "% per year"),
    ("youth-bulge", "wdi-youth-bulge", "Youth bulge (World Bank / UN WPP)",
     "People aged 15-24 as a share of everyone aged 15 and over, computed from World Bank age and population series "
     "(which come from UN World Population Prospects).", "share (0-1)"),
]
# More indicators for forecasting: (code, table, title, unit). Summaries use the API's own definition.
EXTRA = [
    ("NY.GDP.PCAP.KD.ZG", "wdi-gdp-pc-growth", "GDP per capita growth", "% per year"),
    ("NY.GDP.PCAP.KD", "wdi-gdp-pc", "GDP per capita, constant 2015 US$", "US$ (2015)"),
    ("NY.GDP.DEFL.KD.ZG", "wdi-gdp-deflator-inflation", "Inflation, GDP deflator", "% per year"),
    ("NE.TRD.GNFS.ZS", "wdi-trade", "Trade (% of GDP)", "% of GDP"),
    ("NY.GDP.TOTL.RT.ZS", "wdi-resource-rents", "Total natural resources rents (% of GDP)", "% of GDP"),
    ("NY.GDP.PETR.RT.ZS", "wdi-oil-rents", "Oil rents (% of GDP)", "% of GDP"),
    ("NY.GDP.NGAS.RT.ZS", "wdi-gas-rents", "Natural gas rents (% of GDP)", "% of GDP"),
    ("NY.GDP.MINR.RT.ZS", "wdi-mineral-rents", "Mineral rents (% of GDP)", "% of GDP"),
    ("BX.KLT.DINV.WD.GD.ZS", "wdi-fdi", "Foreign direct investment, net inflows (% of GDP)", "% of GDP"),
    ("BX.TRF.PWKR.DT.GD.ZS", "wdi-remittances", "Personal remittances received (% of GDP)", "% of GDP"),
    ("DT.ODA.ODAT.GN.ZS", "wdi-aid", "Net official development assistance received (% of GNI)", "% of GNI"),
    ("GC.DOD.TOTL.GD.ZS", "wdi-government-debt", "Central government debt (% of GDP)", "% of GDP"),
    ("DT.DOD.DECT.GN.ZS", "wdi-external-debt", "External debt stocks (% of GNI)", "% of GNI"),
    ("FI.RES.TOTL.MO", "wdi-reserves-months", "Total reserves in months of imports", "months"),
    ("BN.CAB.XOKA.GD.ZS", "wdi-current-account", "Current account balance (% of GDP)", "% of GDP"),
    ("PA.NUS.FCRF", "wdi-exchange-rate", "Official exchange rate (local currency per US$)", "LCU per US$"),
    ("SL.UEM.TOTL.ZS", "wdi-unemployment", "Unemployment (% of labour force, ILO estimate)", "%"),
    ("SL.UEM.1524.ZS", "wdi-youth-unemployment", "Youth unemployment (% of labour force 15-24, ILO estimate)", "%"),
    ("SP.URB.TOTL.IN.ZS", "wdi-urban-population", "Urban population (% of total)", "%"),
    ("SP.URB.GROW", "wdi-urban-growth", "Urban population growth", "% per year"),
    ("SP.POP.GROW", "wdi-population-growth", "Population growth", "% per year"),
    ("SP.DYN.TFRT.IN", "wdi-fertility", "Fertility rate (births per woman)", "births per woman"),
    ("SP.DYN.LE00.IN", "wdi-life-expectancy", "Life expectancy at birth", "years"),
    ("SH.DYN.MORT", "wdi-child-mortality", "Under-5 mortality rate", "per 1,000 live births"),
    ("NV.AGR.TOTL.ZS", "wdi-agriculture-share", "Agriculture, forestry and fishing (% of GDP)", "% of GDP"),
    ("AG.PRD.FOOD.XD", "wdi-food-production", "Food production index (2014-2016 = 100)", "index"),
    ("SN.ITK.DEFC.ZS", "wdi-undernourishment", "Prevalence of undernourishment", "% of population"),
    ("SE.SEC.ENRR", "wdi-secondary-enrolment", "School enrolment, secondary (% gross)", "%"),
    ("SE.TER.ENRR", "wdi-tertiary-enrolment", "School enrolment, tertiary (% gross)", "%"),
    ("IT.NET.USER.ZS", "wdi-internet-users", "Internet users (% of population)", "%"),
    ("IT.CEL.SETS.P2", "wdi-mobile-subscriptions", "Mobile subscriptions (per 100 people)", "per 100 people"),
    ("MS.MIL.XPND.GD.ZS", "wdi-military-spending", "Military expenditure (% of GDP)", "% of GDP"),
    ("MS.MIL.TOTL.TF.ZS", "wdi-armed-forces", "Armed forces personnel (% of labour force)", "%"),
    ("SI.POV.GINI", "wdi-gini", "Gini index", "index (0-100)"),
    ("SM.POP.RHCR.EO", "wdi-refugees-origin", "UNHCR refugees by country of origin", "people"),
    ("SM.POP.RHCR.EA", "wdi-refugees-hosted", "UNHCR refugees by country of asylum", "people"),
    ("EG.ELC.ACCS.ZS", "wdi-electricity-access", "Access to electricity (% of population)", "%"),
    ("FS.AST.PRVT.GD.ZS", "wdi-private-credit", "Domestic credit to private sector (% of GDP)", "% of GDP"),
    ("FR.INR.RINR", "wdi-real-interest-rate", "Real interest rate", "%"),
    ("TX.VAL.FUEL.ZS.UN", "wdi-fuel-exports", "Fuel exports (% of merchandise exports)", "%"),
    ("TX.VAL.FOOD.ZS.UN", "wdi-food-exports", "Food exports (% of merchandise exports)", "%"),
    ("TM.VAL.FOOD.ZS.UN", "wdi-food-imports", "Food imports (% of merchandise imports)", "%"),
    ("TX.VAL.MMTL.ZS.UN", "wdi-metal-exports", "Ores and metals exports (% of merchandise exports)", "%"),
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


class LicenceError(Exception):
    pass


def series(code, real):
    """{(iso3, year): value} for one WDI indicator, after checking its licence."""
    src = get(f"{API}/sources/2/indicators/{code}/metadata?format=json")  # licence fields live here
    notes = json.dumps(src)
    if "CC BY-4.0" not in notes and "CC BY 4.0" not in notes:
        raise LicenceError(f"{code}: licence in API metadata is not CC BY 4.0; check before importing")
    data = get(f"{API}/country/all/indicator/{code}?format=json&per_page=20000&date=1960:2030")[1]
    return {(d["countryiso3code"], int(d["date"])): d["value"] for d in data
            if d["countryiso3code"] in real and d["value"] is not None}


def youth_bulge(real):
    parts = {c: series(c, real) for c in ["SP.POP.1519.MA.5Y", "SP.POP.2024.MA.5Y", "SP.POP.1519.FE.5Y",
                                          "SP.POP.2024.FE.5Y", "SP.POP.TOTL.MA.IN", "SP.POP.TOTL.FE.IN",
                                          "SP.POP.0014.TO.ZS"]}
    out = {}
    for key in parts["SP.POP.0014.TO.ZS"]:
        if not all(key in p for p in parts.values()):
            continue
        men, women = parts["SP.POP.TOTL.MA.IN"][key], parts["SP.POP.TOTL.FE.IN"][key]
        youth = (men * (parts["SP.POP.1519.MA.5Y"][key] + parts["SP.POP.2024.MA.5Y"][key])
                 + women * (parts["SP.POP.1519.FE.5Y"][key] + parts["SP.POP.2024.FE.5Y"][key])) / 100
        adults = (men + women) * (1 - parts["SP.POP.0014.TO.ZS"][key] / 100)
        if adults > 0:
            out[key] = youth / adults
    return out


def main():
    countries = get(f"{API}/country?format=json&per_page=400")[1]
    real = {c["id"] for c in countries if c["region"]["value"] != "Aggregates"}
    for code, table, title, summary, unit in INDICATORS:
        meta = get(f"{API}/indicator/{code if code != 'youth-bulge' else 'SP.POP.1519.MA.5Y'}?format=json")[1][0]
        values = youth_bulge(real) if code == "youth-bulge" else series(code, real)
        rows = [(iso, str(y), v) for (iso, y), v in values.items()]
        last = max(int(r[1]) for r in rows)
        path = write_table(table, rows)
        write_series({"id": table, "title": title, "summary": summary,
                      "occurred": {"start": "1960", "end": str(last), "precision": "year"},
                      "threads": ["industry"], "regions": REGIONS, "importance": 2, "unit": unit,
                      "dataset": "world-bank-wdi", "indicator": code, "table": f"tables/{table}.csv",
                      "sources": [{"url": f"https://data.worldbank.org/indicator/{code if code != 'youth-bulge' else 'SP.POP.1519.MA.5Y'}",
                                   "title": meta["name"] if code != "youth-bulge" else "Population by age group (WDI)",
                                   "publisher": "The World Bank: World Development Indicators", "type": "primary"}]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")
    skipped = []
    for code, table, title, unit in EXTRA:
        try:
            values = series(code, real)
        except LicenceError as e:
            skipped.append(str(e))
            continue
        except (IndexError, KeyError, TypeError):
            skipped.append(f"{code}: the API returned no data or an error")
            continue
        meta = get(f"{API}/indicator/{code}?format=json")[1][0]
        rows = [(iso, str(y), v) for (iso, y), v in values.items()]
        if not rows:
            skipped.append(f"{code}: no data")
            continue
        path = write_table(table, rows, digits=4)
        note = " ".join((meta.get("sourceNote") or "").split())
        write_series({"id": table, "title": f"{title} (World Bank)",
                      "summary": (note[:400].rsplit(" ", 1)[0] + "...") if len(note) > 400 else (note or title),
                      "occurred": {"start": str(min(int(r[1]) for r in rows)), "end": str(max(int(r[1]) for r in rows)),
                                   "precision": "year"},
                      "threads": ["industry"], "regions": REGIONS, "importance": 1, "unit": unit,
                      "dataset": "world-bank-wdi", "indicator": code, "table": f"tables/{table}.csv",
                      "sources": [{"url": f"https://data.worldbank.org/indicator/{code}", "title": meta["name"],
                                   "publisher": "The World Bank: World Development Indicators", "type": "primary"}]})
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")
    for s in skipped:
        print("skipped", s)


if __name__ == "__main__":
    main()
