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
from .scoring import brier, calibration, log_score
from .states import DEFAULT_REQUIRED, DEFAULT_RULES, classify, sequences, states_of

MODELS = (Markov, BaseRate, Persistence)


def run(states_known_before, truth, state_list, cutoffs, horizons=(1, 5), models=MODELS):
    """states_known_before(X) -> {(iso, year): state} as knowable at X; truth likewise, from the latest data.
    Returns {(model name, h): {"n", "brier", "log", "pairs"}}."""
    truth_seqs = sequences(truth)
    out = defaultdict(lambda: {"n": 0, "brier": 0.0, "log": 0.0, "pairs": defaultdict(list)})
    for X in cutoffs:
        train = sequences(states_known_before(X))
        fitted = [m(state_list).fit(train, before=X) for m in models]
        for iso, years in train.items():
            start = years.get(X - 1)
            if start is None:
                continue
            for h in horizons:
                outcome = truth_seqs.get(iso, {}).get(X - 1 + h)
                if outcome is None:
                    continue
                for m in fitted:
                    dist = m.predict(start, h)
                    r = out[(m.name, h)]
                    r["n"] += 1
                    r["brier"] += brier(dist, outcome)
                    r["log"] += log_score(dist, outcome)
                    for s in state_list:
                        r["pairs"][s].append((dist[s], s == outcome))
    for r in out.values():
        r["brier"] /= max(r["n"], 1)
        r["log"] /= max(r["n"], 1)
    return dict(out)


def report(results, state_list, horizons, title="Backtest") -> str:
    lines = [f"# {title}", "", "Lower is better. A model is only useful if it beats both baselines.", ""]
    for h in horizons:
        lines += [f"## {h} year{'s' if h > 1 else ''} ahead", "", "| model | forecasts | Brier | log score |", "|---|---|---|---|"]
        for (name, hh), r in sorted(results.items(), key=lambda kv: kv[1]["brier"]):
            if hh == h:
                lines.append(f"| {name} | {r['n']} | {r['brier']:.4f} | {r['log']:.4f} |")
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
    args = ap.parse_args(argv)
    horizons = (1, 5)
    cutoffs = range(args.first, args.last + 1)
    if args.synthetic:
        world = synthetic()
        known = lambda X: {k: v for k, v in world.items() if k[1] < X}
        results = run(known, world, SYNTH_STATES, cutoffs, horizons)
        text = report(results, SYNTH_STATES, horizons, "Backtest on a made-up world")
    else:
        from .panel import load_table
        names = ["vdem-electoral-democracy", "ucdp-intrastate-max-intensity", "ucdp-any-conflict",
                 "powell-thyne-successful-coups"]
        try:
            tables = lambda X=None: {n: load_table(n, known_before=X) for n in names}
            latest = classify(tables(), DEFAULT_RULES, DEFAULT_REQUIRED)
        except FileNotFoundError as e:
            raise SystemExit(f"{e}\nThe real backtest needs the importers (docs/forecasting.md, step 2). "
                             "Try --synthetic to see how it works.")
        known = lambda X: classify(tables(X), DEFAULT_RULES, DEFAULT_REQUIRED)
        state_list = states_of(DEFAULT_RULES)
        results = run(known, latest, state_list, cutoffs, horizons)
        text = report(results, state_list, horizons)
    if args.out:
        open(args.out, "w", encoding="utf-8").write(text)
    print(text)


if __name__ == "__main__":
    main()
