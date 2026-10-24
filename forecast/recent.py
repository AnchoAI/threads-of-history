"""How the models do on recent years: every new conflict from FIRST to LAST, seen from the year before.

  python -m forecast.recent [--from 2015] [--to 2025] [--out FILE]

For each year X, every model is trained on what was known before X and forecasts X for each
country that was at peace in X-1. The report gives:
  - AUC and Brier for those forecasts, per model, over the whole period,
  - every new conflict that actually happened, with its probability and its rank among
    the countries at peace that year (by the model chosen with --rank-by),
  - each year's highest-ranked countries that stayed at peace: the false alarms.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .logit import TABLES as LOGIT_TABLES, Logit, LogitAll, LogitUnrest
from .markov import Markov
from .panel import load_table
from .scoring import auc
from .states import DEFAULT_REQUIRED, DEFAULT_RULES, FIRST_COVERED_YEAR, classify, sequences, states_of

CONFLICT = ("armed-conflict", "civil-war")
NAMES = list(dict.fromkeys(["vdem-electoral-democracy", "ucdp-intrastate-max-intensity", "ucdp-any-conflict"] + LOGIT_TABLES))
MODELS = {"markov": Markov, "logit": Logit, "logit+unrest": LogitUnrest, "logit+all": LogitAll}
try:  # the gradient-boosting model needs the optional libraries in requirements-ml.txt
    from .gbm import GBM, TABLES as GBM_TABLES
    import lightgbm  # noqa: F401
    MODELS["gbm"] = GBM
    NAMES = list(dict.fromkeys(NAMES + GBM_TABLES))
except ImportError:
    pass


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="first", type=int, default=2015)
    ap.add_argument("--to", dest="last", type=int, default=2025)
    ap.add_argument("--rank-by", default="logit+all", choices=list(MODELS))
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    states = states_of(DEFAULT_RULES)
    latest = classify({n: load_table(n) for n in NAMES}, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR)
    pairs = {m: [] for m in MODELS}
    onsets, alarms = [], {}
    for X in range(args.first, args.last + 1):
        tables = {n: load_table(n, known_before=X) for n in NAMES}
        seqs = sequences(classify(tables, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR))
        fitted = {name: cls(states).fit(seqs, before=X, tables=tables, horizons=(1,)) for name, cls in MODELS.items()}
        risk = {name: {} for name in MODELS}
        for iso, seq in seqs.items():
            start, outcome = seq.get(X - 1), latest.get((iso, X))
            if start is None or start in CONFLICT or outcome is None:
                continue
            for name, m in fitted.items():
                d = m.predict(start, 1, iso=iso, year=X - 1)
                p = sum(d[s] for s in CONFLICT)
                risk[name][iso] = p
                pairs[name].append((p, outcome in CONFLICT))
        order = sorted(risk[args.rank_by], key=lambda k: -risk[args.rank_by][k])
        for iso in order:
            if latest.get((iso, X)) in CONFLICT:
                recurrence = any(latest.get((iso, y)) in CONFLICT for y in range(X - 10, X - 1))
                onsets.append((X, iso, latest[(iso, X)], risk[args.rank_by][iso], order.index(iso) + 1, len(order), recurrence))
        alarms[X] = [(iso, risk[args.rank_by][iso], latest.get((iso, X)) in CONFLICT) for iso in order[:10]]
        print(f"{X}: {len(order)} countries at peace, {sum(1 for o in onsets if o[0] == X)} new conflicts", flush=True)

    lines = [f"# Recent years: new conflicts {args.first}-{args.last}, seen from the year before", "",
             "Each year the models were trained on what was known before it, then forecast, for every country at peace the year "
             "before, the chance of armed conflict or civil war that year. Conflicts are UCDP state-based conflicts on the "
             "country's territory (25 or more battle deaths), so a small insurgency counts as much as a large war.", "",
             "## Scores over the period", "", "| model | forecasts | new conflicts | Brier | AUC |", "|---|---|---|---|---|"]
    for name in sorted(MODELS, key=lambda n: -(auc(pairs[n]) or 0)):
        pr = pairs[name]
        b = sum((p - hit) ** 2 for p, hit in pr) / len(pr)
        lines.append(f"| {name} | {len(pr)} | {sum(h for _, h in pr)} | {b:.4f} | {auc(pr):.3f} |")
    top_q = sum(1 for o in onsets if o[4] <= o[5] / 4)
    top10 = sum(1 for o in onsets if o[4] <= 10)
    fresh = [o for o in onsets if not o[6]]
    fresh_q = sum(1 for o in fresh if o[4] <= o[5] / 4)
    fresh10 = sum(1 for o in fresh if o[4] <= 10)
    lines += ["", f"## Every new conflict, ranked by `{args.rank_by}`", "",
              f"{len(onsets)} new conflicts. {top10} were in that year's top 10 of {onsets[0][5] if onsets else 0}-odd peaceful countries, "
              f"and {top_q} in the riskiest quarter (about {len(onsets) / 4:.0f} expected by chance).", "",
              f"Most of these are **recurrences**: the country had conflict at some point in the 10 years before. Those are easier. "
              f"Of the {len(fresh)} **fresh** conflicts (none in the previous 10 years), {fresh10} were in the top 10 and {fresh_q} in the riskiest quarter "
              f"(about {len(fresh) / 4:.0f} expected by chance).", "",
              "Some entries reflect how UCDP locates interstate conflicts: it lists the countries of the governments involved, so "
              "for example the US and UK appear in 2024 because of their strikes on the Houthis, and Russia in 2022 because of its war with Ukraine.", "",
              "| Year | Country | What happened | Kind | Probability | Rank among countries at peace |", "|---|---|---|---|---|---|"]
    for X, iso, st, p, k, n, rec in onsets:
        lines.append(f"| {X} | {iso} | {st} | {'recurrence' if rec else '**fresh**'} | {p:.0%} | {k} of {n} |")
    lines += ["", "## False-alarm check: each year's ten highest-ranked countries at peace", "",
              "**Bold** marks those where conflict did break out.", ""]
    for X, top in alarms.items():
        lines.append(f"- **{X}:** " + ", ".join(f"**{iso} {p:.0%}**" if hit else f"{iso} {p:.0%}" for iso, p, hit in top))
    text = "\n".join(lines) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
