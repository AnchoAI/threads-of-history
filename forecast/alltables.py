"""Features from every table we have, found automatically: "gather data and let the model find patterns".

For each country-year table in data/tables/ and .cache/private-tables/ (see panel.PRIVATE):
  - its value in year t (or the latest in the 3 years before, for tables with gaps),
  - its change from t-1 to t.
For each world-level table (entity WLD, the commodity prices), the 1-year log change, and its
effect on this country through what it trades:
  - energy price change x fuel exports share, and x oil rents
  - food price change x food imports share, and x food exports share
  - metals price change x metal exports share
New tables become features with no code change. Everything is from year t or before.
"""
from __future__ import annotations

import math

import numpy as np

from .panel import PRIVATE, TABLES as TABLE_DIR

# Left out of the automatic list: bookkeeping (region codes), and estimates smoothed over all years
# at once, whose value for a year can reflect later years (Fariss et al.'s latent GDP and population,
# bundled by V-Dem), or interpolated between survey years (Clio Infra and Gapminder series). In the
# first all-tables run the GDP one dominated the economic-collapse forecasts, a sign of hindsight.
SKIP = {"vdem-region", "vdem-e-gdp-pc", "vdem-e-population", "vdem-e-education-years", "vdem-e-life-expectancy",
        "vdem-e-child-mortality", "vdem-e-urbanization", "vdem-e-fertility"}
MAX_BACK = 3
TRADE = [  # (world table, country share table, feature name)
    ("pink-energy", "wdi-fuel-exports", "energy price change x fuel exports"),
    ("pink-energy", "wdi-oil-rents", "energy price change x oil rents"),
    ("pink-food", "wdi-food-imports", "food price change x food imports"),
    ("pink-food", "wdi-food-exports", "food price change x food exports"),
    ("pink-metals", "wdi-metal-exports", "metals price change x metal exports"),
]


def discover():
    """(country tables, world tables): every table name, public first, then private ones not in data/."""
    names = {}
    for d in (TABLE_DIR, PRIVATE):
        if d.exists():
            for p in sorted(d.glob("*.csv")):
                names.setdefault(p.stem, p)
    country, world = [], []
    for name, path in names.items():
        if name in SKIP:
            continue
        with path.open(encoding="utf-8") as f:
            next(f)
            first = f.readline()
        (world if first.startswith("WLD,") else country).append(name)
    return country, world


def feature_names(country, world):
    out = []
    for n in country:
        out += [n, f"{n} (1-yr change)"]
    out += [f"{n} (1-yr log change)" for n in world]
    out += [name for w, c, name in TRADE if w in world and c in country]
    return out


def _latest(t, iso, year):
    for y in range(year, year - MAX_BACK - 1, -1):
        v = t.get((iso, y))
        if v is not None:
            return v
    return None


def row(iso, year, tables, country, world):
    out = []
    for n in country:
        t = tables.get(n, {})
        v, before = t.get((iso, year)), t.get((iso, year - 1))
        level = v if v is not None else _latest(t, iso, year - 1)
        out += [level, v - before if v is not None and before is not None else None]
    wchange = {}
    for n in world:
        t = tables.get(n, {})
        a, b = t.get(("WLD", year - 1)), t.get(("WLD", year))
        wchange[n] = math.log(b / a) if a and b and a > 0 and b > 0 else None
        out.append(wchange[n])
    for w, c, _ in TRADE:
        if w in world and c in country:
            share = _latest(tables.get(c, {}), iso, year)
            out.append(wchange[w] * share / 100 if wchange.get(w) is not None and share is not None else None)
    return [np.nan if v is None else float(v) for v in out]
