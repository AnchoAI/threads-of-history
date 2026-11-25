"""Check the models against conflicts on the map: would they have seen them coming?

  python -m forecast.cases [--out FILE]

For each case in forecast/cases.yaml (an event, its country and start year X), the models
are trained on what was known before X. The report gives, for that country:
  - its state in X-1 (if it was already at war, the forecast is mostly persistence),
  - the probability the model gave to armed conflict or civil war in X, and within 5 years,
  - its rank among all countries that year (1 = highest risk),
and, as a check on false alarms, the countries the model ranked highest that year.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from .logit import TABLES as LOGIT_TABLES, Logit, LogitUnrest
from .markov import Markov
from .panel import load_table
from .states import DEFAULT_REQUIRED, DEFAULT_RULES, FIRST_COVERED_YEAR, classify, sequences, states_of

ROOT = Path(__file__).resolve().parent.parent
CONFLICT = ("armed-conflict", "civil-war")
NAMES = ["vdem-electoral-democracy", "ucdp-intrastate-max-intensity", "ucdp-any-conflict"] + LOGIT_TABLES


MODEL = Logit


def risk_table(X, horizons=(1, 5)):
    """{h: {iso: (state in X-1, P(conflict at X-1+h))}} for every country, from both models."""
    tables = {n: load_table(n, known_before=X) for n in dict.fromkeys(NAMES)}
    seqs = sequences(classify(tables, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR))
    states = states_of(DEFAULT_RULES)
    models = [MODEL(states).fit(seqs, before=X, tables=tables, horizons=horizons),
              Markov(states).fit(seqs, before=X)]
    out = {m.name: {h: {} for h in horizons} for m in models}
    for iso, seq in seqs.items():
        start = seq.get(X - 1)
        if start is None:
            continue
        for m in models:
            for h in horizons:
                d = m.predict(start, h, iso=iso, year=X - 1)
                out[m.name][h][iso] = (start, sum(d[s] for s in CONFLICT))
    return out


def rank(table, iso, peaceful_only=False):
    keys = [k for k in table if not peaceful_only or table[k][0] not in CONFLICT]
    order = sorted(keys, key=lambda k: -table[k][1])
    return (order.index(iso) + 1 if iso in order else None), len(order)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out")
    ap.add_argument("--model", choices=["logit", "unrest"], default="logit",
                    help="covariate model to check: plain, or with neighbours, regional unrest and protest")
    args = ap.parse_args(argv)
    global MODEL
    MODEL = LogitUnrest if args.model == "unrest" else Logit
    cases = yaml.safe_load((Path(__file__).parent / "cases.yaml").read_text())
    titles = {}
    for c in cases:
        p = ROOT / "data" / "events" / f"{c['event']}.yaml"
        titles[c["event"]] = yaml.safe_load(p.read_text())["title"] if p.exists() else c["event"]
    cache = {}
    lines = ["# Case studies: conflicts on the map, seen from the year before", "",
             "For each conflict, the models were trained only on what was known before it started. "
             "\"Risk\" is the probability of armed conflict or civil war on that country's territory. "
             "Rank is among all countries that year (1 = highest).", "",
             "For a new war in a country at peace the year before, the fairer comparison is the last column: "
             "the rank among countries that were also at peace, since ongoing wars fill the top of the overall ranking.", "",
             "| Event | Country | State the year before | Covariate model: risk that year (rank) | within 5 years (rank) | Markov chain: risk that year (rank) | Rank among countries at peace |",
             "|---|---|---|---|---|---|---|"]
    flagged, onsets = 0, []
    for c in cases:
        X, iso = c["year"], c["iso"]
        if X not in cache:
            cache[X] = risk_table(X)
        r = cache[X]
        if iso not in r[MODEL.name][1]:
            lines.append(f"| {titles[c['event']]} ({X}) | {iso} | no data | | | |")
            continue
        start, p1 = r[MODEL.name][1][iso]
        k1, n = rank(r[MODEL.name][1], iso)
        _, p5 = r[MODEL.name][5][iso]
        k5, _ = rank(r[MODEL.name][5], iso)
        _, pm = r["markov"][1][iso]
        km, _ = rank(r["markov"][1], iso)
        flagged += k1 <= 20
        kp, npeace = rank(r[MODEL.name][1], iso, peaceful_only=True)
        peace = f"{kp} of {npeace}" if kp else "already in conflict"
        if kp:
            onsets.append(kp / npeace)
        lines.append(f"| {titles[c['event']]} ({X}) | {iso} | {start} | {p1:.0%} ({k1} of {n}) | {p5:.0%} ({k5}) | {pm:.0%} ({km}) | {peace} |")
    top_quarter = sum(1 for q in onsets if q <= 0.25)
    lines += ["", f"The covariate model ranked {flagged} of {len(cases)} cases among the 20 highest-risk countries in the year they started. "
              f"Of the {len(onsets)} wars that began in a country at peace, it placed {top_quarter} in the riskiest quarter of peaceful countries "
              f"(a random guess would place about {len(onsets) / 4:.0f}).", "",
              "## Who else was flagged: the false-alarm check", "",
              "The covariate model's ten highest-risk countries for the start year of each case, with what actually happened that year "
              "(state from the latest data). Countries that were already at war mostly stay at war, so the interesting entries are the peaceful ones near the top.", ""]
    latest = classify({n: load_table(n) for n in dict.fromkeys(NAMES)}, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR)
    for X in sorted(cache):
        top = sorted(cache[X][MODEL.name][1].items(), key=lambda kv: -kv[1][1])[:10]
        cells = []
        for iso, (start, p) in top:
            happened = latest.get((iso, X), "?")
            mark = "" if happened in CONFLICT else " **(no conflict)**"
            cells.append(f"{iso} {p:.0%}{mark}")
        lines.append(f"- **{X}:** " + ", ".join(cells))
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
