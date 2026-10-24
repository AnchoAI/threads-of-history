"""Give each country-year one state from a short, fixed list.

Rules are data: a list of (state, test), checked in order; the first test that passes
wins. A test gets a lookup function `v(indicator)` that returns the value for that
country-year, or None when the table has no row. A country-year is skipped when its
`required` indicators are missing, so gaps in the data never turn into a state.
"""
from __future__ import annotations

from typing import Callable

Lookup = Callable[[str], float | None]

# Draft rules from docs/forecasting.md. Table names are the ones the importers will write.
DEFAULT_RULES: list[tuple[str, Callable[[Lookup], bool]]] = [
    ("civil-war", lambda v: (v("ucdp-intrastate-max-intensity") or 0) >= 2),
    ("armed-conflict", lambda v: (v("ucdp-any-conflict") or 0) >= 1),
    # ("coup", ...) waits for the Powell & Thyne licence (data/datasets/powell-thyne-coups.yaml)
    ("democracy", lambda v: (v("vdem-electoral-democracy") or 0) >= 0.5),
    ("autocracy", lambda v: True),
]
DEFAULT_REQUIRED = ["vdem-electoral-democracy"]
FIRST_COVERED_YEAR = 1946  # UCDP starts here; before it, "no conflict recorded" isn't evidence of peace


def states_of(rules) -> list[str]:
    return [s for s, _ in rules]


def classify(tables: dict[str, dict[tuple[str, int], float]], rules=DEFAULT_RULES,
             required=DEFAULT_REQUIRED, since: int | None = None) -> dict[tuple[str, int], str]:
    keys = set()
    for name in required:
        keys |= {k for k in tables[name] if since is None or k[1] >= since}
    out = {}
    for key in sorted(keys):
        if any(key not in tables[name] for name in required):
            continue
        v = lambda name, key=key: tables.get(name, {}).get(key)
        for state, test in rules:
            if test(v):
                out[key] = state
                break
    return out


def sequences(states: dict[tuple[str, int], str]) -> dict[str, dict[int, str]]:
    """{iso3: {year: state}}"""
    out: dict[str, dict[int, str]] = {}
    for (iso, year), s in states.items():
        out.setdefault(iso, {})[year] = s
    return out
