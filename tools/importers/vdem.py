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
    ("v2cagenmob", "vdem-mass-mobilization", "Mass mobilization (V-Dem)",
     "How frequent and large mass mobilization events (protests, demonstrations) were that year, on V-Dem's "
     "measurement-model scale (higher is more)."),
    ("e_regionpol", "vdem-region", "Politico-geographic region (V-Dem)",
     "V-Dem's region code: 1 Eastern Europe and post-Soviet, 2 Latin America, 3 North Africa and Middle East, "
     "4 Sub-Saharan Africa, 5 Western Europe and North America, 6 Eastern Asia, 7 South-Eastern Asia, "
     "8 Southern Asia, 9 the Pacific, 10 the Caribbean."),
]
# More of V-Dem's own measures, for forecasting (from 1946, when the forecast data starts).
# (column, table, title, unit). Summaries point to the V-Dem v16 codebook for exact definitions.
EXTRA_FIRST_YEAR = 1946
EXTRA = [
    ("v2x_corr", "vdem-corruption", "Political corruption index", "index (0-1, higher is more corrupt)"),
    ("v2x_execorr", "vdem-executive-corruption", "Executive corruption index", "index (0-1)"),
    ("v2x_pubcorr", "vdem-public-sector-corruption", "Public sector corruption index", "index (0-1)"),
    ("v2x_jucon", "vdem-judicial-constraints", "Judicial constraints on the executive", "index (0-1)"),
    ("v2xlg_legcon", "vdem-legislative-constraints", "Legislative constraints on the executive", "index (0-1)"),
    ("v2x_clphy", "vdem-physical-integrity", "Physical violence index (freedom from state killings and torture)", "index (0-1)"),
    ("v2x_clpol", "vdem-political-liberties", "Political civil liberties index", "index (0-1)"),
    ("v2x_clpriv", "vdem-private-liberties", "Private civil liberties index", "index (0-1)"),
    ("v2x_rule", "vdem-rule-of-law", "Rule of law index", "index (0-1)"),
    ("v2x_freexp_altinf", "vdem-free-expression", "Freedom of expression and alternative sources of information", "index (0-1)"),
    ("v2xcs_ccsi", "vdem-civil-society", "Core civil society index", "index (0-1)"),
    ("v2x_regime", "vdem-regime-type", "Regimes of the World", "category: 0 closed autocracy, 1 electoral autocracy, 2 electoral democracy, 3 liberal democracy"),
    ("v2x_neopat", "vdem-neopatrimonialism", "Neopatrimonial rule index", "index (0-1)"),
    ("v2xnp_client", "vdem-clientelism", "Clientelism index", "index (0-1)"),
    ("v2xel_elecparl", "vdem-election-legislative", "Legislative or constituent assembly election held this year", "yes/no (1/0)"),
    ("v2xel_elecpres", "vdem-election-presidential", "Presidential election held this year", "yes/no (1/0)"),
    ("v2elfrfair", "vdem-election-free-fair", "Election free and fair (last national election)", "scale (about -3 to 3)"),
    ("v2elvotbuy", "vdem-election-vote-buying", "Election vote buying (higher is less)", "scale (about -3 to 3)"),
    ("v2cacamps", "vdem-political-polarization", "Political polarization (higher is more)", "scale (about -3 to 3)"),
    ("v2smpolsoc", "vdem-social-polarization", "Polarization of society (from 2000; higher is less)", "scale (about -3 to 3)"),
    ("v2caviol", "vdem-political-violence", "Political violence by non-state actors (higher is more)", "scale (about -3 to 3)"),
    ("v2clkill", "vdem-freedom-from-killings", "Freedom from political killings (higher is freer)", "scale (about -3 to 3)"),
    ("v2cltort", "vdem-freedom-from-torture", "Freedom from torture (higher is freer)", "scale (about -3 to 3)"),
    ("v2stfisccap", "vdem-fiscal-capacity", "State fiscal capacity", "scale (about -3 to 3)"),
    ("v2svstterr", "vdem-state-territory", "Share of territory under state control", "percent"),
    ("v2xpe_exlsocgr", "vdem-exclusion-social-group", "Exclusion by social group (higher is more excluded)", "index (0-1)"),
    ("v2xpe_exlpol", "vdem-exclusion-political-group", "Exclusion by political group", "index (0-1)"),
    ("v2xpe_exlgeo", "vdem-exclusion-urban-rural", "Exclusion by urban-rural location", "index (0-1)"),
    ("v2xpe_exlecon", "vdem-exclusion-economic", "Exclusion by socio-economic group", "index (0-1)"),
    ("v2exl_legitperf", "vdem-legitimation-performance", "Government claims legitimacy by performance", "scale (about -3 to 3)"),
    ("v2exl_legitideol", "vdem-legitimation-ideology", "Government promotes a specific ideology", "scale (about -3 to 3)"),
    ("v2expathhs", "vdem-hos-path-to-power", "How the head of state came to power", "category: 0 foreign power, 1 force, 2 hereditary, 3 appointed by monarch, 4 appointed by military, 5 appointed by ruling party, 6 appointed by legislature, 7 directly elected, 8 other"),
    ("v2mecenefm", "vdem-media-censorship", "Government censorship of media (higher is less)", "scale (about -3 to 3)"),
    ("v2csreprss", "vdem-cso-repression", "Repression of civil society organisations (higher is less)", "scale (about -3 to 3)"),
    ("v2cademmob", "vdem-prodemocracy-mobilization", "Mobilization for democracy", "scale (about -3 to 3)"),
    ("v2caautmob", "vdem-proautocracy-mobilization", "Mobilization for autocracy", "scale (about -3 to 3)"),
    ("v2x_ex_military", "vdem-regime-military", "Military dimension of the regime", "index (0-1)"),
    ("v2x_ex_party", "vdem-regime-party", "Ruling-party dimension of the regime", "index (0-1)"),
    ("v2x_ex_confidence", "vdem-regime-confidence", "Head of government depends on legislature's confidence", "index (0-1)"),
    ("v2x_ex_hereditary", "vdem-regime-hereditary", "Hereditary dimension of the regime", "index (0-1)"),
    ("v2x_ex_direlect", "vdem-regime-direct-election", "Direct election of the executive", "index (0-1)"),
    ("v2svinlaut", "vdem-international-autonomy", "State independence from foreign powers", "scale (about -3 to 3)"),
    ("v2x_gender", "vdem-women-empowerment", "Women's political empowerment index", "index (0-1)"),
    ("v2x_egal", "vdem-egalitarian-component", "Egalitarian component index", "index (0-1)"),
    ("v2clrspct", "vdem-rigorous-administration", "Rigorous and impartial public administration", "scale (about -3 to 3)"),
    ("v2juhcind", "vdem-high-court-independence", "High court independence", "scale (about -3 to 3)"),
    ("v2exrescon", "vdem-executive-respects-constitution", "Executive respects the constitution", "scale (about -3 to 3)"),
    ("v2psoppaut", "vdem-opposition-autonomy", "Opposition parties' autonomy", "scale (about -3 to 3)"),
    ("v2x_accountability", "vdem-accountability", "Accountability index", "scale"),
]
# Variables V-Dem bundles from other publishers (its "e_" variables). Their licences belong to
# those publishers, so they go to the private folder (.cache/private-tables/), not into git.
PRIVATE_EXTRA = [
    ("e_pt_coup", "vdem-e-coups-successful", "Successful coups (Powell & Thyne, via V-Dem)"),
    ("e_pt_coup_attempts", "vdem-e-coup-attempts", "Coup attempts (Powell & Thyne, via V-Dem)"),
    ("e_coups", "vdem-e-coups-bjornskov-rode", "Coups (Bjørnskov & Rode, via V-Dem)"),
    ("e_total_resources_income_pc", "vdem-e-resource-income-pc", "Petroleum, coal, gas and metals income per capita (Haber & Menaldo / Miller)"),
    ("e_total_oil_income_pc", "vdem-e-oil-income-pc", "Oil income per capita"),
    ("e_total_fuel_income_pc", "vdem-e-fuel-income-pc", "Fuel income per capita"),
    ("e_peaveduc", "vdem-e-education-years", "Average years of education, 15 and older (Clio Infra)"),
    ("e_pelifeex", "vdem-e-life-expectancy", "Life expectancy (Clio Infra / Gapminder)"),
    ("e_pechmor", "vdem-e-child-mortality", "Child mortality (Gapminder)"),
    ("e_miurbani", "vdem-e-urbanization", "Urbanization"),
    ("e_miferrat", "vdem-e-fertility", "Fertility rate"),
    ("e_gdppc", "vdem-e-gdp-pc", "GDP per capita (Fariss et al. latent estimate)"),
    ("e_pop", "vdem-e-population", "Population (Fariss et al.)"),
    ("e_area", "vdem-e-area", "Land area"),
    ("e_cow_exports", "vdem-e-exports", "Exports (Correlates of War trade)"),
    ("e_cow_imports", "vdem-e-imports", "Imports (Correlates of War trade)"),
    ("e_wbgi_pve", "vdem-e-wgi-political-stability", "Political stability and absence of violence (World Bank WGI)"),
    ("e_wbgi_gee", "vdem-e-wgi-government-effectiveness", "Government effectiveness (World Bank WGI)"),
    ("e_wbgi_rle", "vdem-e-wgi-rule-of-law", "Rule of law (World Bank WGI)"),
    ("e_wbgi_rqe", "vdem-e-wgi-regulatory-quality", "Regulatory quality (World Bank WGI)"),
    ("e_ti_cpi", "vdem-e-corruption-perceptions", "Corruption Perceptions Index (Transparency International)"),
    ("e_polity2", "vdem-e-polity2", "Polity2 score (Polity IV/5)"),
    ("e_fh_pr", "vdem-e-fh-political-rights", "Political rights (Freedom House)"),
    ("e_fh_cl", "vdem-e-fh-civil-liberties", "Civil liberties (Freedom House)"),
    ("e_civil_war", "vdem-e-civil-war", "Civil war (Haber & Menaldo)"),
    ("e_miinterc", "vdem-e-internal-conflict", "Internal armed conflict (Clio Infra / Brecke)"),
    ("e_miinflat", "vdem-e-inflation", "Inflation (Clio Infra), longer coverage than the World Bank"),
    ("e_democracy_breakdowns", "vdem-e-democracy-breakdowns", "Democratic breakdowns (Boix, Miller & Rosato)"),
    ("e_democracy_trans", "vdem-e-democracy-transitions", "Democratic transitions (Boix, Miller & Rosato)"),
]
UNITS = {"vdem-mass-mobilization": "scale (about -3 to 3)", "vdem-region": "region code (1-10)"}
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


LEADER_TABLES = [
    ("v2exnamhos", "vdem-hos-tenure", "Years the head of state has been in office", "years"),
    ("v2exnamhog", "vdem-hog-tenure", "Years the head of government has been in office", "years"),
]


def leaders(df):
    """Leader tenure, derived from V-Dem's yearly name of the head of state and of government:
    the number of consecutive years (counting this one) with the same name, from 1900. Also the
    head of state's age, from v2exagehos (which holds the birth year). Written from 1946 like the
    other extra tables."""
    from collections import defaultdict
    last = int(df["year"].max())
    done = []
    for column, table, title, unit in LEADER_TABLES:
        run, rows = defaultdict(lambda: (None, 0)), []
        for iso, y, name in sorted(zip(df["country_text_id"], df["year"], df[column]), key=lambda r: (r[0], r[1])):
            prev_name, n = run[iso]
            name = name if isinstance(name, str) and name.strip() else None
            n = n + 1 if name is not None and name == prev_name else (1 if name is not None else 0)
            run[iso] = (name, n)
            if y >= EXTRA_FIRST_YEAR and name is not None:
                rows.append((iso, str(int(y)), float(n)))
        done.append((column, table, title, unit, rows))
    age = df[df["year"] >= EXTRA_FIRST_YEAR]
    done.append(("v2exagehos", "vdem-hos-age", "Age of the head of state", "years",
                 [(iso, str(int(y)), float(y - v)) for iso, y, v in zip(age["country_text_id"], age["year"], age["v2exagehos"])
                  if v == v and 1700 < v <= y]))
    for column, table, title, unit, rows in done:
        path = write_table(table, rows, digits=1)
        write_series({
            "id": table, "title": f"{title} (V-Dem)",
            "summary": f"{title}, derived from V-Dem variable {column}" + (" (consecutive years with the same name)." if "tenure" in table else "."),
            "occurred": {"start": str(EXTRA_FIRST_YEAR), "end": str(last), "precision": "year"},
            "threads": ["revolutions"], "regions": REGIONS, "importance": 1,
            "unit": unit, "dataset": "v-dem", "indicator": column, "table": f"tables/{table}.csv",
            "sources": [{"url": "https://v-dem.net/data/the-v-dem-dataset/", "title": "The V-Dem Dataset",
                         "publisher": "V-Dem Institute", "type": "primary"}],
        })
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")


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
            "unit": UNITS.get(table, "index (0-1)"), "dataset": "v-dem", "indicator": column, "table": f"tables/{table}.csv",
            "sources": [{"url": "https://v-dem.net/data/the-v-dem-dataset/", "title": "The V-Dem Dataset",
                         "publisher": "V-Dem Institute", "type": "primary"}],
        })
        print(f"wrote {path.relative_to(CACHE.parent)}: {len(rows)} rows")
    extra = df[df["year"] >= EXTRA_FIRST_YEAR]
    for column, table, title, unit in EXTRA:
        rows = [(iso, str(int(y)), float(v)) for iso, y, v in zip(extra["country_text_id"], extra["year"], extra[column])]
        path = write_table(table, rows, digits=4)
        write_series({
            "id": table, "title": f"{title} (V-Dem)",
            "summary": f"{title}. V-Dem variable {column}; see the V-Dem v16 codebook for the exact definition.",
            "occurred": {"start": str(EXTRA_FIRST_YEAR), "end": str(last), "precision": "year"},
            "threads": ["revolutions"], "regions": REGIONS, "importance": 1,
            "unit": unit, "dataset": "v-dem", "indicator": column, "table": f"tables/{table}.csv",
            "sources": [{"url": "https://v-dem.net/data/the-v-dem-dataset/", "title": "The V-Dem Dataset",
                         "publisher": "V-Dem Institute", "type": "primary"}],
        })
        print(f"wrote {path.relative_to(CACHE.parent)}: {sum(1 for r in rows if r[2] == r[2])} rows")
    leaders(df)
    for column, table, title in PRIVATE_EXTRA:
        rows = [(iso, str(int(y)), float(v)) for iso, y, v in zip(extra["country_text_id"], extra["year"], extra[column])]
        path = write_table(table, rows, private=True, digits=4)
        print(f"wrote {path.relative_to(CACHE.parent)} (private): {title}")
    print("dropped units:", ", ".join(f"{k} ({DROPPED[k]})" for k in dropped))


if __name__ == "__main__":
    main()
