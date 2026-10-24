"""Put the intelligence-estimate questions to our own country-year models.

  python -m forecast.answer_estimates      writes forecast/answers/threads-*.yaml

Our models forecast yes/no outcomes per country and calendar year (forecast/outcomes.py), so they
can only answer questions that map onto one of those outcomes. MAPPING lists those, with how close
the mapping is. Each answer comes from a model trained only on years before the forecast year,
using data up to the year before (so a question asked in mid-1965 is answered from data through
1964: slightly less than the estimate's authors knew).
"""
from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import yaml

from .outcomes import backtest, build

ANSWERS = Path(__file__).resolve().parent / "answers"

# question id: (outcome, country, forecast year, invert, how close the mapping is)
MAPPING = {
    "snie-98-65-uruguay-military-coup-1965": (
        "coup-attempt", "URY", 1965, False,
        "Question: a military coup within a year from June 1965. Model: any coup attempt in calendar 1965."),
    "snie-63-6-54-diem-survives-hinh-crisis-1954": (
        "coup-success", "VDR", 1954, True,
        "Question: Diem's government survives to the end of 1954. Model: one minus the chance of a successful coup in 1954."),
    "snie-63-1-60-diem-regime-collapses-1960": (
        "coup-success", "VDR", 1960, False,
        "Question: Diem's regime collapses or is overthrown within a year from August 1960. Model: a successful coup in calendar 1960."),
}
UNMAPPED = ("The other questions ask who starts a war, whether a third country intervenes in a war, whether a "
            "blockade is lifted, or about a nuclear programme. Our outcomes are new conflicts in countries at peace, "
            "coups, regime change and economic crises per country-year, so they don't fit; and the countries in "
            "several questions were already at war, which our onset outcome excludes.")


def main():
    rows, _, _, _ = build()
    answers = {}
    for qid, (outcome, iso, year, invert, how) in MAPPING.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            r = backtest(rows, outcome, [year])
        case = next((c for c in (r or {}).get("cases", []) if c[0] == iso and c[1] == year), None)
        if case is None:
            print(f"{qid}: no forecast ({iso} {year} not eligible or not enough training data)")
            continue
        for model, p in case[2].items():
            answers.setdefault(model, {})[qid] = {"p": round(1 - p if invert else p, 4), "mapping": how}
        print(qid, {m: round(1 - p if invert else p, 3) for m, p in case[2].items()})
    ANSWERS.mkdir(exist_ok=True)
    for model, a in answers.items():
        name = "threads-" + model.replace(", ", "-").replace(" ", "-")
        (ANSWERS / f"{name}.yaml").write_text(yaml.safe_dump({
            "forecaster": f"Threads of History: {model}",
            "method": "Country-year model from forecast/outcomes.py, trained only on years before the forecast year. "
                      + UNMAPPED,
            "answers": a}, sort_keys=False, allow_unicode=True, width=100), encoding="utf-8")
        print("wrote", name)


if __name__ == "__main__":
    main()
