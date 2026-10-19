"""Forecast many kinds of event, not just war: one yes/no question per country-year.

  python -m forecast.outcomes [--from 1975] [--to 2024] [--out FILE]

Each outcome asks "does this happen in country C in year X?", using only data up to X-1.
Most are onsets: a country counts only if it wasn't already in that condition in X-1.

  conflict-onset          armed conflict or civil war starts (UCDP/PRIO), after a year of peace
  coup-attempt            any coup attempt, successful or not (Powell & Thyne; private table)
  coup-success            a successful coup (Powell & Thyne; private table)
  democratic-breakdown    a democracy (V-Dem electoral democracy >= 0.5) falls below 0.5
  democratisation         an autocracy rises to 0.5 or more
  mass-protest            V-Dem mass mobilization reaches 1.5 or more (about the top 7% of
                          country-years) after a year below it
  economic-collapse       GDP per capita falls 5% or more in a year (Maddison), after a year without
  high-inflation          consumer prices rise 40% or more (World Bank), after a year below 40%
  mass-violence           1,000 or more deaths from one-sided and non-state violence (UCDP GED,
                          from 1989), after a year below 1,000. A rough proxy for mass killing.

For each cutoff year X, three models are trained on outcomes before X and forecast year X:
the base rate, a logistic regression and gradient boosting (LightGBM), all on the same
features (forecast/gbm.py's, plus coup history when the coup table is present). The report
gives AUC, Brier, how many events fell in the riskiest 10% of countries, the main patterns
the boosting model found (SHAP), and a forward look at the next year.

Thresholds are fixed round numbers chosen before looking at results; change them here, not
per run. No table carries publication dates yet, so features are computed once from the
latest tables (each from data up to X-1 only); if a table gains a `published` column, this
must switch to rebuilding per cutoff, and build() refuses to run.
"""
from __future__ import annotations

import argparse
import math
import warnings
from pathlib import Path

import numpy as np

from .gbm import TABLES as GBM_TABLES, feature_names, row
from .logit import CONFLICT, Logit, _softmax
from .panel import PRIVATE, TABLES as TABLE_DIR, has_table, load_table
from .scoring import auc
from .states import DEFAULT_REQUIRED, DEFAULT_RULES, FIRST_COVERED_YEAR, classify, sequences, states_of

COUP_TABLES = ["pt-coup-attempts", "pt-coup-successes"]
NAMES = list(dict.fromkeys(["vdem-electoral-democracy", "ucdp-intrastate-max-intensity", "ucdp-any-conflict"] + GBM_TABLES))
PROTEST, COLLAPSE, INFLATION, MASS_VIOLENCE = 1.5, -0.05, 40.0, 1000.0
GED_FIRST_YEAR, COUP_FIRST_YEAR, SINCE_CAP = 1989, 1950, 25


def _onset(now, before, test):
    """Onset of a condition: None if unknown or already in it last year, else whether it holds now."""
    if now is None or before is None:
        return None
    return None if test(before) else test(now)


def outcome(name, iso, X, tables, seq):
    """True/False for an eligible country-year, None if not eligible or unknown."""
    get = lambda t, y: tables.get(t, {}).get((iso, y))
    if name == "conflict-onset":
        return _onset(seq.get(X), seq.get(X - 1), lambda s: s in CONFLICT)
    if name in ("coup-attempt", "coup-success"):
        v = get("pt-coup-attempts" if name == "coup-attempt" else "pt-coup-successes", X)
        return None if v is None else v > 0
    if name == "democratic-breakdown":
        now, before = get("vdem-electoral-democracy", X), get("vdem-electoral-democracy", X - 1)
        return None if now is None or before is None or before < 0.5 else now < 0.5
    if name == "democratisation":
        now, before = get("vdem-electoral-democracy", X), get("vdem-electoral-democracy", X - 1)
        return None if now is None or before is None or before >= 0.5 else now >= 0.5
    if name == "mass-protest":
        return _onset(get("vdem-mass-mobilization", X), get("vdem-mass-mobilization", X - 1), lambda v: v >= PROTEST)
    if name == "economic-collapse":
        g = [get("maddison-gdp-per-capita", y) for y in (X - 2, X - 1, X)]
        if not all(g):
            return None
        return _onset(math.log(g[2] / g[1]), math.log(g[1] / g[0]), lambda v: v <= math.log(1 + COLLAPSE))
    if name == "high-inflation":
        return _onset(get("wdi-inflation", X), get("wdi-inflation", X - 1), lambda v: v >= INFLATION)
    if name == "mass-violence":
        if X - 1 < GED_FIRST_YEAR or X > _last_year(tables, "ucdp-ged-deaths"):
            return None
        v = lambda y: tables.get("ucdp-ged-deaths-nonstate", {}).get((iso, y), 0.0)
        return _onset(v(X), v(X - 1), lambda d: d >= MASS_VIOLENCE)
    raise ValueError(name)


def in_condition(name, iso, year, tables, seq):
    """Whether the country is already in the outcome's condition in `year` (so it can't have an
    onset the year after). None if unknown. Coups have no condition: every year counts."""
    get = lambda t, y: tables.get(t, {}).get((iso, y))
    if name == "conflict-onset":
        return None if seq.get(year) is None else seq[year] in CONFLICT
    if name in ("coup-attempt", "coup-success"):
        return False
    if name in ("democratic-breakdown", "democratisation"):
        d = get("vdem-electoral-democracy", year)
        return None if d is None else (d < 0.5) == (name == "democratic-breakdown")
    if name == "mass-protest":
        v = get("vdem-mass-mobilization", year)
        return None if v is None else v >= PROTEST
    if name == "economic-collapse":
        a, b = get("maddison-gdp-per-capita", year - 1), get("maddison-gdp-per-capita", year)
        return None if not a or not b else math.log(b / a) <= math.log(1 + COLLAPSE)
    if name == "high-inflation":
        v = get("wdi-inflation", year)
        return None if v is None else v >= INFLATION
    if name == "mass-violence":
        return None if year < GED_FIRST_YEAR else tables.get("ucdp-ged-deaths-nonstate", {}).get((iso, year), 0.0) >= MASS_VIOLENCE
    raise ValueError(name)


OUTCOMES = ["conflict-onset", "coup-attempt", "coup-success", "democratic-breakdown", "democratisation",
            "mass-protest", "economic-collapse", "high-inflation", "mass-violence"]
_LAST: dict = {}


def _last_year(tables, name):
    key = (id(tables), name)
    if key not in _LAST:
        _LAST[key] = max((y for _, y in tables.get(name, {})), default=0)
    return _LAST[key]


def coup_features(iso, year, tables):
    """Coup attempts in the last 10 years, successful ones, and log years since the last attempt,
    capped at SINCE_CAP so that "no coup since 1950" doesn't quietly encode the calendar year."""
    att, suc = tables.get("pt-coup-attempts"), tables.get("pt-coup-successes")
    if not att or (iso, year) not in att:
        return [np.nan] * 3
    a10 = sum(att.get((iso, y), 0) for y in range(year - 9, year + 1))
    s10 = sum(suc.get((iso, y), 0) for y in range(year - 9, year + 1))
    since = next((year - y for y in range(year, COUP_FIRST_YEAR - 1, -1) if att.get((iso, y))), None)
    return [a10, s10, math.log1p(min(since if since is not None else SINCE_CAP, SINCE_CAP))]


def names(states, coups):
    return feature_names(states) + (["coup attempts (last 10)", "successful coups (last 10)", "years since last coup"] if coups else [])


def build():
    """Feature rows for every country-year t-1 and outcomes in t, from the latest tables; and, for
    the forward look, each country's last year with which outcomes it is eligible for next."""
    for n in NAMES + COUP_TABLES:
        for d in (TABLE_DIR, PRIVATE):
            p = d / f"{n}.csv"
            if p.exists() and "published" in p.open(encoding="utf-8").readline():
                raise SystemExit(f"{p} has publication dates: features must be rebuilt per cutoff (see the docstring)")
    tables = {n: load_table(n) for n in NAMES}
    coups = all(has_table(n) for n in COUP_TABLES)
    if coups:
        tables.update({n: load_table(n) for n in COUP_TABLES})
    states = states_of(DEFAULT_RULES)
    world = sequences(classify(tables, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR))
    rows, future = [], []
    for iso, seq in world.items():
        for X in sorted(seq):
            if X - 1 not in seq:
                continue
            ys = {o: outcome(o, iso, X, tables, seq) for o in OUTCOMES}
            x = row(states, iso, X - 1, seq, tables, world) + (coup_features(iso, X - 1, tables) if coups else [])
            rows.append((iso, X, x, ys))
        # the forward look: features from the last year, outcome unknown
        last = max(seq)
        x = row(states, iso, last, seq, tables, world) + (coup_features(iso, last, tables) if coups else [])
        future.append((iso, last + 1, x, {o: in_condition(o, iso, last, tables, seq) is False for o in OUTCOMES}))
    return rows, future, names(states, coups), coups


# ---------------------------------------------------------------- models for one yes/no outcome

class BaseRate:
    name = "base rate"

    def fit(self, X, y):
        self.p = y.mean()
        return self

    def predict(self, X):
        return np.full(len(X), self.p)


class BinaryLogit:
    name = "logit"

    def fit(self, X, y):
        self.m = Logit(["no", "yes"], iters=300)
        self.W, self.stats = self.m._train(np.ones((len(X), 1)), X.tolist(), y.astype(int))
        return self

    def predict(self, X):
        D, _ = self.m._design(np.ones((len(X), 1)), X.tolist(), self.stats)
        return _softmax(D @ self.W)[:, 1]


class BinaryGBM:
    name = "gbm"
    params = dict(objective="binary", learning_rate=0.05, n_estimators=200, num_leaves=15, min_child_samples=30,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=1,
                  verbose=-1, n_jobs=1)

    def fit(self, X, y):
        import lightgbm as lgb
        self.m = lgb.LGBMClassifier(**self.params).fit(X, y.astype(int))
        return self

    def predict(self, X):
        return self.m.predict_proba(X)[:, 1]

    def shap(self, X):
        return self.m.booster_.predict(X, pred_contrib=True)[:, :-1]


def _models():
    try:
        import lightgbm  # noqa: F401
        return [BaseRate, BinaryLogit, BinaryGBM]
    except ImportError:
        return [BaseRate, BinaryLogit]


def backtest(rows, outcome_name, cutoffs, models=None):
    """Rolling backtest for one outcome: train on years < X, forecast X. Returns per-model pairs
    (probability, happened), per-year (iso, X, p_by_model, happened), and the last fitted models."""
    models = models or _models()
    data = [(iso, X, x, ys[outcome_name]) for iso, X, x, ys in rows if ys[outcome_name] is not None]
    if not data:
        return None
    Xall = np.array([d[2] for d in data], dtype=float)
    yall = np.array([d[3] for d in data], dtype=bool)
    years = np.array([d[1] for d in data])
    pairs = {m.name: [] for m in models}
    cases, shap_rows, fitted = [], [], {}
    for X in cutoffs:
        train, test = years < X, years == X
        if test.sum() == 0 or yall[train].sum() < 10:
            continue
        preds = {}
        for M in models:
            m = M().fit(Xall[train], yall[train])
            preds[M.name] = m.predict(Xall[test])
            pairs[M.name] += list(zip(preds[M.name].tolist(), yall[test].tolist()))
            fitted[M.name] = m
            if M is BinaryGBM:
                shap_rows.append(m.shap(Xall[test]))
        idx = np.where(test)[0]
        for j, i in enumerate(idx):
            cases.append((data[i][0], X, {k: float(v[j]) for k, v in preds.items()}, bool(yall[i])))
    return {"pairs": pairs, "cases": cases, "shap": np.vstack(shap_rows) if shap_rows else None,
            "data": (Xall, yall, years), "rows": data}


def forward(rows, future, outcome_name, models=None):
    """Train on every known year and forecast the year after each country's last data, for
    countries eligible then. Only countries whose last data is the latest year are ranked."""
    models = models or _models()
    known = [(x, ys[outcome_name]) for _, _, x, ys in rows if ys[outcome_name] is not None]
    if not known:
        return None, []
    X = np.array([k[0] for k in known], dtype=float)
    y = np.array([k[1] for k in known], dtype=bool)
    year = max(f[1] for f in future)
    target = [(iso, x) for iso, X_, x, ok in future if X_ == year and ok[outcome_name]]
    best = models[-1]().fit(X, y)
    p = best.predict(np.array([t[1] for t in target], dtype=float)) if target else []
    return year, sorted(zip([t[0] for t in target], np.asarray(p).tolist()), key=lambda kv: -kv[1])


# ---------------------------------------------------------------- report

LABELS = {
    "conflict-onset": "New armed conflict", "coup-attempt": "Coup attempt", "coup-success": "Successful coup",
    "democratic-breakdown": "Democratic breakdown", "democratisation": "Democratisation",
    "mass-protest": "Mass protest wave", "economic-collapse": "Economic collapse (GDP per head -5%)",
    "high-inflation": "High inflation (40%+)", "mass-violence": "Mass violence (1,000+ one-sided/non-state deaths)",
}


def top_share(pairs, frac=0.1, by_year=None):
    """Share of events that fell in the riskiest `frac` of forecasts made in the same year."""
    if by_year is None:
        return None
    hits = total = 0
    for year, items in by_year.items():
        items = sorted(items, key=lambda kv: -kv[0])
        k = max(1, round(frac * len(items)))
        hits += sum(h for _, h in items[:k])
        total += sum(h for _, h in items)
    return hits / total if total else None


def report(results, feat_names, coups, first, last) -> str:
    from .backtest import auc_difference

    lines = [f"# Many outcomes: rolling backtest {first}-{last}", "",
             "Each row asks whether an event happens in a country in year X, forecast from data up to X-1, by models "
             "trained only on years before X. AUC: the chance that a country where it happened was rated riskier than one "
             "where it didn't (0.5 is a coin flip). Top 10%: the share of events that fell in the riskiest tenth of "
             "countries that year. Brier: lower is better.", ""]
    if not coups:
        lines += ["Coup outcomes are missing: their table is private (tools/importers/powell_thyne.py).", ""]
    lines += ["| outcome | country-years | events | base rate | AUC logit | AUC gbm | gbm − logit (95% interval) | top 10% logit | top 10% gbm | Brier logit | Brier gbm |",
              "|---|---|---|---|---|---|---|---|---|---|---|"]
    for o, r in results.items():
        if not r or not r["pairs"].get("logit"):
            continue
        n = len(r["pairs"]["logit"])
        k = sum(h for _, h in r["pairs"]["logit"])
        by = lambda name: _by_year(r["cases"], name)
        brier = lambda name: sum((p - h) ** 2 for p, h in r["pairs"][name]) / n
        cell = lambda v, f="{:.3f}": f.format(v) if v is not None else "–"
        g = r["pairs"].get("gbm")
        diff = "–"
        if g:
            d, lo, hi = auc_difference(g, r["pairs"]["logit"], reps=500)
            diff = f"{d:+.3f} ({lo:+.3f} to {hi:+.3f})"
        lines.append(f"| {LABELS[o]} | {n} | {k} | {k / n:.3f} | {cell(auc(r['pairs']['logit']))} | "
                     f"{cell(auc(g) if g else None)} | {diff} | {cell(top_share(None, by_year=by('logit')), '{:.0%}')} | "
                     f"{cell(top_share(None, by_year=by('gbm')) if g else None, '{:.0%}')} | {brier('logit'):.4f} | "
                     f"{cell(brier('gbm') if g else None, '{:.4f}')} |")
    lines += ["", "## What the boosting model relies on", "",
              "The features with the largest average effect (mean |SHAP|, in log-odds) on its forecasts in the test years. "
              "These are patterns in the data, not causes.", ""]
    for o, r in results.items():
        if r and r["shap"] is not None:
            imp = np.abs(r["shap"]).mean(axis=0)
            top = np.argsort(-imp)[:6]
            lines.append(f"- **{LABELS[o]}:** " + ", ".join(f"{feat_names[i]} ({imp[i]:.2f})" for i in top))
    return "\n".join(lines) + "\n"


def _by_year(cases, name):
    out = {}
    for iso, X, p, hit in cases:
        if name in p:
            out.setdefault(X, []).append((p[name], hit))
    return out


def forward_report(fwd) -> str:
    lines = ["", "## Forward look", "",
             "Trained on every known year, forecasting the year after each outcome's last data. Highest-risk countries "
             "by the boosting model, with its probability. A probability, not a prediction: most of these will not happen. "
             "Onset outcomes leave out countries already in that condition. Features come from each table's latest year, "
             "so a table that ends earlier (Maddison GDP ends in 2022) counts as missing.", ""]
    for o, (year, ranked) in fwd.items():
        if not ranked:
            continue
        rate = f"{year}: " + ", ".join(f"{iso} {p:.0%}" for iso, p in ranked[:12])
        lines.append(f"- **{LABELS[o]}**, {rate}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="first", type=int, default=1975)
    ap.add_argument("--to", dest="last", type=int, default=2024)
    ap.add_argument("--outcomes", default=",".join(OUTCOMES))
    ap.add_argument("--no-forward", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    rows, future, feat_names, coups = build()
    print(f"{len(rows)} country-years, {len(feat_names)} features, coup table {'found' if coups else 'missing'}", flush=True)
    results, fwd = {}, {}
    for o in args.outcomes.split(","):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results[o] = backtest(rows, o, range(args.first, args.last + 1))
            if not args.no_forward:
                fwd[o] = forward(rows, future, o)
        r = results[o]
        print(o, "AUC", {k: round(auc(v) or 0, 3) for k, v in r["pairs"].items()} if r else "no data", flush=True)
    text = report(results, feat_names, coups, args.first, args.last) + (forward_report(fwd) if fwd else "")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
