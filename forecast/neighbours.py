"""Which countries bordered a country in a given year (land borders).

Borders come from forecast/data/neighbours.json (today's map, from Natural Earth). Three
federations are rebuilt for the years they existed, using the codes the country-year tables
give them: RUS stands for the USSR until 1991, SRB for Yugoslavia until 1991 and CZE for
Czechoslovakia until 1992. In those years their neighbours are the union of their members'
neighbours. East Germany, South Yemen and South Vietnam, which aren't on today's map, get
their borders listed here.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

PATH = Path(__file__).resolve().parent / "data" / "neighbours.json"

FEDERATIONS = {  # code: (last year, member codes on today's map)
    "RUS": (1991, ["RUS", "UKR", "BLR", "MDA", "EST", "LVA", "LTU", "GEO", "ARM", "AZE", "KAZ", "UZB", "TKM", "KGZ", "TJK"]),
    "SRB": (1991, ["SRB", "HRV", "SVN", "BIH", "MKD", "MNE", "XKX"]),
    "CZE": (1992, ["CZE", "SVK"]),
}
FORMER = {"DDR": ["DEU", "POL", "CZE"], "YMD": ["YEM", "OMN", "SAU"], "VDR": ["VNM", "LAO", "KHM"]}


@lru_cache(maxsize=1)
def _map():
    return {k: set(v) for k, v in json.loads(PATH.read_text())["neighbours"].items()}


@lru_cache(maxsize=None)
def neighbours(iso: str, year: int) -> frozenset[str]:
    m = _map()
    if iso in FORMER:
        return frozenset(FORMER[iso])
    fed = FEDERATIONS.get(iso)
    if fed and year <= fed[0]:
        members = set(fed[1])
        out = set().union(*(m.get(c, set()) for c in members)) - members
        return frozenset(out)
    return frozenset(m.get(iso, set()))
