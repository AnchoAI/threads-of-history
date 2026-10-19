"""Honest backtests: stand at the start of a year, train on what was known, predict ahead, score.

  python -m forecast.backtest               real data (needs the importers' tables)
  python -m forecast.backtest --synthetic   a made-up world, to see how it works

For each cutoff year X:
  - states are rebuilt from tables as known before X (see panel.load_table),
  - every model is trained on transitions before X,
  - for each country, the state in X-1 is the starting point, and the forecast for
    X-1+h is compared with what actually happened (from the latest data).
"""
from __future__ import annotations

import argparse
import random
from collections import defaultdict

from .markov import BaseRate, Markov, Persistence
from .scoring import auc, brier, calibration, log_score
from .states import DEFAULT_REQUIRED, DEFAULT_RULES, FIRST_COVERED_YEAR, classify, sequences, states_of

MODELS = (Markov, BaseRate, Persistence)
CONFLICT_STATES = ("armed-conflict", "civil-war")
ONSET_FROM_EXCLUDED = CONFLICT_STATES  # onset scores only count countries at peace the year before


def run(states_known_before, truth, state_list, cutoffs, horizons=(1, 5), models=MODELS, tables_known_before=None):
    """states_known_before(X) -> {(iso, year): state} as knowable at X; truth likewise, from the latest data.
    tables_known_before(X) -> {name: table} for models that use conditions beyond the state.
    Returns {(model name, h): {"n", "brier", "log", "pairs"}}."""
    truth_seqs = sequences(truth)
    out = defaultdict(lambda: {"n": 0, "brier": 0.0, "log": 0.0, "pairs": defaultdict(list), "onset": []})
    for X in cutoffs:
        train = sequences(states_known_before(X))
        tables = tables_known_before(X) if tables_known_before else None
        fitted = [m(state_list).fit(train, before=X, tables=tables, horizons=horizons) for m in models]
        for iso, years in train.items():
            start = years.get(X - 1)
            if start is None:
                continue
            for h in horizons:
                outcome = truth_seqs.get(iso, {}).get(X - 1 + h)
                if outcome is None:
                    continue
                for m in fitted:
                    dist = m.predict(start, h, iso=iso, year=X - 1)
                    r = out[(m.name, h)]
                    r["n"] += 1
                    r["brier"] += brier(dist, outcome)
                    r["log"] += log_score(dist, outcome)
                    for s in state_list:
                        r["pairs"][s].append((dist[s], s == outcome))
                    if start not in ONSET_FROM_EXCLUDED:
                        r["onset"].append((sum(dist.get(s, 0) for s in CONFLICT_STATES), outcome in CONFLICT_STATES))
    for r in out.values():
        r["brier"] /= max(r["n"], 1)
        r["log"] /= max(r["n"], 1)
    return dict(out)


def auc_difference(a_pairs, b_pairs, reps=1000, seed=1):
    """AUC(a) - AUC(b) on the same cases, with a paired bootstrap 95% interval."""
    import numpy as np

    pa = np.array([p for p, _ in a_pairs])
    pb = np.array([p for p, _ in b_pairs])
    y = np.array([hit for _, hit in a_pairs], dtype=bool)

    def rank_auc(p, y):
        order = np.argsort(p, kind="mergesort")
        ranks = np.empty(len(p))
        sp = p[order]
        i = 0
        while i < len(sp):  # average ranks for ties
            j = i
            while j + 1 < len(sp) and sp[j + 1] == sp[i]:
                j += 1
            ranks[order[i:j + 1]] = (i + j) / 2 + 1
            i = j + 1
        n1, n0 = y.sum(), (~y).sum()
        return (ranks[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0) if n1 and n0 else np.nan

    d = rank_auc(pa, y) - rank_auc(pb, y)
    rng = np.random.default_rng(seed)
    diffs = []
    for _ in range(reps):
        i = rng.integers(0, len(y), len(y))
        diffs.append(rank_auc(pa[i], y[i]) - rank_auc(pb[i], y[i]))
    lo, hi = np.nanpercentile(diffs, [2.5, 97.5])
    return float(d), float(lo), float(hi)


def report(results, state_list, horizons, title="Backtest") -> str:
    lines = [f"# {title}", "", "Lower is better. A model is only useful if it beats both baselines.", ""]
    for h in horizons:
        lines += [f"## {h} year{'s' if h > 1 else ''} ahead", "", "| model | forecasts | Brier | log score |", "|---|---|---|---|"]
        for (name, hh), r in sorted(results.items(), key=lambda kv: kv[1]["brier"]):
            if hh == h:
                lines.append(f"| {name} | {r['n']} | {r['brier']:.4f} | {r['log']:.4f} |")
        lines.append("")
    lines += ["## New conflicts: countries at peace the year before", "",
              "Only countries not in armed conflict or civil war at the start. The question is whether a new conflict "
              "breaks out by the horizon. Brier is for that yes/no forecast. AUC is the chance that a country where conflict "
              "did break out was rated riskier than one where it didn't (0.5 is a coin flip, 1.0 perfect).", ""]
    for h in horizons:
        lines += [f"### {h} year{'s' if h > 1 else ''} ahead", "", "| model | forecasts | new conflicts | Brier | AUC |", "|---|---|---|---|---|"]
        rows = []
        for (name, hh), r in results.items():
            if hh != h or not r["onset"]:
                continue
            o = r["onset"]
            b = sum((p - hit) ** 2 for p, hit in o) / len(o)
            a = auc(o)
            rows.append((-(a or 0), name, len(o), sum(hit for _, hit in o), b, a))
        for _, name, n, k, b, a in sorted(rows):
            lines.append(f"| {name} | {n} | {k} | {b:.4f} | {a:.3f} |" if a is not None else f"| {name} | {n} | {k} | {b:.4f} | – |")
        lines.append("")
        ref = results.get(("logit", h), {}).get("onset")
        if ref:
            lines += ["Each variant against the plain covariate model (`logit`), on the same forecasts: the change in AUC, "
                      "with a 95% interval from 1,000 bootstrap resamples. An interval that includes 0 means the gain could be luck.", ""]
            for (name, hh), r in sorted(results.items()):
                if hh == h and name.startswith("logit+") and len(r["onset"]) == len(ref) and r["onset"]:
                    d, lo, hi = auc_difference(r["onset"], ref)
                    lines.append(f"- {name}: {d:+.3f} ({lo:+.3f} to {hi:+.3f})")
            lines.append("")
    lines += ["## Calibration of the Markov model, 1 year ahead", "",
              "When the model said about p, how often did it happen?", ""]
    pairs = results.get(("markov", horizons[0]), {}).get("pairs", {})
    for s in state_list:
        rows = calibration(pairs.get(s, []), bins=5)
        cells = ", ".join(f"said {p:.0%} → happened {o:.0%} (n={n})" for p, o, n in rows)
        lines.append(f"- **{s}:** {cells}")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- a made-up world

SYNTH_STATES = ["democracy", "autocracy", "coup", "armed-conflict", "civil-war"]
SYNTH_P = {  # yearly transition chances in the made-up world
    "democracy":      {"democracy": .95, "autocracy": .03, "coup": .01, "armed-conflict": .01, "civil-war": .00},
    "autocracy":      {"democracy": .03, "autocracy": .89, "coup": .03, "armed-conflict": .04, "civil-war": .01},
    "coup":           {"democracy": .10, "autocracy": .70, "coup": .05, "armed-conflict": .10, "civil-war": .05},
    "armed-conflict": {"democracy": .03, "autocracy": .17, "coup": .03, "armed-conflict": .65, "civil-war": .12},
    "civil-war":      {"democracy": .01, "autocracy": .09, "coup": .02, "armed-conflict": .18, "civil-war": .70},
}


def synthetic(countries=150, start=1900, end=2024, seed=7):
    rng = random.Random(seed)
    out = {}
    for c in range(countries):
        iso = "".join(chr(65 + (c // 26 ** k) % 26) for k in (2, 1, 0))
        s = rng.choices(SYNTH_STATES, weights=[.3, .5, .05, .1, .05])[0]
        for y in range(start, end + 1):
            out[(iso, y)] = s
            s = rng.choices(SYNTH_STATES, weights=[SYNTH_P[s][t] for t in SYNTH_STATES])[0]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--synthetic", action="store_true", help="use a made-up world instead of real data")
    ap.add_argument("--from", dest="first", type=int, default=1960)
    ap.add_argument("--to", dest="last", type=int, default=2014)
    ap.add_argument("--out", help="write the report to this file")
    ap.add_argument("--horizons", default="1,5", help="years ahead to score, e.g. 1 or 1,5")
    ap.add_argument("--models", default="current",
                    help="'current' (baselines, logit, unrest, shocks, violence, all) or 'all' (every variant)")
    args = ap.parse_args(argv)
    horizons = tuple(int(h) for h in args.horizons.split(","))
    cutoffs = range(args.first, args.last + 1)
    if args.synthetic:
        world = synthetic()
        known = lambda X: {k: v for k, v in world.items() if k[1] < X}
        results = run(known, world, SYNTH_STATES, cutoffs, horizons)
        text = report(results, SYNTH_STATES, horizons, "Backtest on a made-up world")
    else:
        from .panel import load_table
        from .logit import TABLES as LOGIT_TABLES, Logit, LogitMobilization, LogitNeighbours, LogitRegion, LogitRegionMobilization, LogitUnrest, LogitYouth, LogitShocks, LogitViolence, LogitAll
        names = ["vdem-electoral-democracy", "ucdp-intrastate-max-intensity", "ucdp-any-conflict"]
        names += [n for n in LOGIT_TABLES if n not in names]
        try:
            tables = lambda X=None: {n: load_table(n, known_before=X) for n in names}
            latest = classify(tables(), DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR)
        except FileNotFoundError as e:
            raise SystemExit(f"{e}\nThe real backtest needs the importers (docs/forecasting.md, step 2). "
                             "Try --synthetic to see how it works.")
        state_list = states_of(DEFAULT_RULES)
        cache = {}
        def tables_at(X):
            if X not in cache:
                cache.clear()
                cache[X] = tables(X)
            return cache[X]
        known = lambda X: classify(tables_at(X), DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR)
        results = run(known, latest, state_list, cutoffs, horizons, models=MODELS + ((Logit, LogitUnrest, LogitShocks, LogitViolence, LogitAll) if args.models == "current" else
                                         (Logit, LogitNeighbours, LogitYouth, LogitRegion, LogitMobilization,
                                          LogitRegionMobilization, LogitUnrest, LogitShocks, LogitViolence, LogitAll)), tables_known_before=tables_at)
        text = report(results, state_list, horizons,
                      f"Backtest on real data ({FIRST_COVERED_YEAR}-{max(y for _, y in latest)}), cutoffs {args.first}-{args.last}")
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
