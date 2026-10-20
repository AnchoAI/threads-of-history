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

For each cutoff year X, models are trained on outcomes before X and forecast year X:
  - the base rate,
  - a logistic regression and gradient boosting (LightGBM) on the hand-built features
    (forecast/gbm.py's, plus coup history when the coup table is present),
  - the same two on every table, found automatically (forecast/alltables.py); the boosting
    one is recalibrated (Platt scaling) on its last 5 training years,
  - an ensemble: the mean of the plain logit and the all-tables boosting model.
The report gives AUC, the share of events in the riskiest 10% of countries, Brier, whether
the extra tables help (with bootstrap intervals), calibration, and the main patterns the
boosting model found (SHAP). --forward adds a look at the year after the last data.

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

from . import alltables
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
    country, wld = alltables.discover()
    for n in country + wld:
        if n not in tables:
            tables[n] = load_table(n)
    states = states_of(DEFAULT_RULES)
    world = sequences(classify(tables, DEFAULT_RULES, DEFAULT_REQUIRED, since=FIRST_COVERED_YEAR))
    rows, future = [], []
    for iso, seq in world.items():
        for X in sorted(seq):
            if X - 1 not in seq:
                continue
            ys = {o: outcome(o, iso, X, tables, seq) for o in OUTCOMES}
            x = row(states, iso, X - 1, seq, tables, world) + (coup_features(iso, X - 1, tables) if coups else [])
            rows.append((iso, X, (x, alltables.row(iso, X - 1, tables, country, wld)), ys))
    # the forward look: features from each country's last year, outcome unknown. Tables that end
    # earlier are extended at each country's recent trend, or the model would read "missing" as it
    # did in training, where missing income mostly meant small states with nothing happening.
    # Eligibility is judged on the real tables only.
    ftables = carried_forward(tables, max(y for seq in world.values() for y in seq))
    for iso, seq in world.items():
        last = max(seq)
        x = row(states, iso, last, seq, ftables, world) + (coup_features(iso, last, ftables) if coups else [])
        x = (x, alltables.row(iso, last, ftables, country, wld))
        future.append((iso, last + 1, x, {o: in_condition(o, iso, last, tables, seq) is False for o in OUTCOMES}))
    base = names(states, coups)
    return rows, future, {"base": base, "all": base + alltables.feature_names(country, wld)}, coups


CARRY = ("maddison-gdp-per-capita", "maddison-population")


def carried_forward(tables, year, trend_years=3):
    """A copy of tables where each CARRY table is extended to `year` at the country's average
    growth over its last `trend_years` known years (flat if that can't be computed), so growth
    features read as "as before" rather than as a sudden stop."""
    out = dict(tables)
    for name in CARRY:
        t = dict(tables.get(name, {}))
        last = {}
        for (iso, y) in t:
            last[iso] = max(last.get(iso, y), y)
        for iso, y0 in last.items():
            a, b = t.get((iso, y0 - trend_years)), t[(iso, y0)]
            g = (b / a) ** (1 / trend_years) if a and b else 1.0
            for y in range(y0 + 1, year + 1):
                t[(iso, y)] = b * g ** (y - y0)
        out[name] = t
    return out


# ---------------------------------------------------------------- models for one yes/no outcome

class BaseRate:
    name = "base rate"
    features = "base"

    def fit(self, X, y, years=None):
        self.p = y.mean()
        return self

    def predict(self, X):
        return np.full(len(X), self.p)


class BinaryLogit:
    name = "logit"
    features = "base"

    def fit(self, X, y, years=None):
        self.m = Logit(["no", "yes"], iters=300)
        self.W, self.stats = self.m._train(np.ones((len(X), 1)), X.tolist(), y.astype(int))
        return self

    def predict(self, X):
        D, _ = self.m._design(np.ones((len(X), 1)), X.tolist(), self.stats)
        return _softmax(D @ self.W)[:, 1]


class BinaryGBM:
    name = "gbm"
    features = "base"
    params = dict(objective="binary", learning_rate=0.05, n_estimators=200, num_leaves=15, min_child_samples=30,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, random_state=1,
                  verbose=-1, n_jobs=1)

    def fit(self, X, y, years=None):
        import lightgbm as lgb
        self.m = lgb.LGBMClassifier(**self.params).fit(X, y.astype(int))
        return self

    def predict(self, X):
        return self.m.predict_proba(X)[:, 1]

    def shap(self, X):
        return self.m.booster_.predict(X, pred_contrib=True)[:, :-1]


class BinaryLogitAll(BinaryLogit):
    name = "logit, all tables"
    features = "all"


class BinaryGBMAll(BinaryGBM):
    """Gradient boosting on every table, with its probabilities recalibrated (Platt scaling).
    Calibration is fitted on the last CALIB_YEARS training years, forecast by a model trained
    on the years before them, so it never sees the test year."""
    name = "gbm, all tables"
    features = "all"
    params = {**BinaryGBM.params, "colsample_bytree": 0.5}
    CALIB_YEARS = 5

    def fit(self, X, y, years=None):
        super().fit(X, y)
        self.a, self.b = 1.0, 0.0
        if years is not None:
            cut = years.max() - self.CALIB_YEARS + 1
            early, late = years < cut, years >= cut
            if y[early].sum() >= 10 and y[late].sum() >= 3:
                z = _logit(BinaryGBM().fit(X[early], y[early]).predict(X[late]))
                self.a, self.b = _platt(z, y[late])
        return self

    def predict(self, X):
        return 1 / (1 + np.exp(-np.clip(self.a * _logit(super().predict(X)) + self.b, -30, 30)))


def _logit(p):
    p = np.clip(p, 1e-6, 1 - 1e-6)
    return np.log(p / (1 - p))


def _platt(z, y, iters=100):
    """Fit P(y) = sigmoid(a z + b) by Newton's method with step halving, with a little shrinkage
    towards a=1, b=0 (no change)."""
    y = np.asarray(y, dtype=float)

    def loss(a, b):
        t = a * z + b
        return np.sum(np.logaddexp(0, t) - y * t) + 0.5 * ((a - 1) ** 2 + b ** 2)

    a, b = 1.0, 0.0
    cur = loss(a, b)
    for _ in range(iters):
        p = 1 / (1 + np.exp(-np.clip(a * z + b, -30, 30)))
        g = np.array([np.sum((p - y) * z) + (a - 1), np.sum(p - y) + b])
        w = p * (1 - p)
        H = np.array([[np.sum(w * z * z) + 1, np.sum(w * z)], [np.sum(w * z), np.sum(w) + 1]])
        step = np.linalg.solve(H, g)
        t = 1.0
        while loss(a - t * step[0], b - t * step[1]) > cur and t > 1e-6:
            t /= 2
        a, b = a - t * step[0], b - t * step[1]
        new = loss(a, b)
        if cur - new < 1e-9:
            break
        cur = new
    return float(a), float(b)


ENSEMBLE = ("logit", "gbm, all tables")  # the all-tables logit has too many features to do well


def _models():
    try:
        import lightgbm  # noqa: F401
        return [BaseRate, BinaryLogit, BinaryGBM, BinaryLogitAll, BinaryGBMAll]
    except ImportError:
        return [BaseRate, BinaryLogit, BinaryLogitAll]


def backtest(rows, outcome_name, cutoffs, models=None):
    """Rolling backtest for one outcome: train on years < X, forecast X. Returns per-model pairs
    (probability, happened), per-year cases (iso, X, p_by_model, happened) and SHAP values of the
    all-tables boosting model. "ensemble" is the mean of the ENSEMBLE models' probabilities."""
    models = models or _models()
    data = [(iso, X, x, ys[outcome_name]) for iso, X, x, ys in rows if ys[outcome_name] is not None]
    if not data:
        return None
    Xs = {"base": np.array([d[2][0] for d in data], dtype=float)}
    Xs["all"] = np.hstack([Xs["base"], np.array([d[2][1] for d in data], dtype=float)])
    yall = np.array([d[3] for d in data], dtype=bool)
    years = np.array([d[1] for d in data])
    names = [m.name for m in models] + (["ensemble"] if all(e in [m.name for m in models] for e in ENSEMBLE) else [])
    pairs = {n: [] for n in names}
    cases, shap_rows = [], []
    for X in cutoffs:
        train, test = years < X, years == X
        if test.sum() == 0 or yall[train].sum() < 10:
            continue
        preds = {}
        for M in models:
            F = Xs[M.features]
            m = M().fit(F[train], yall[train], years[train])
            preds[M.name] = m.predict(F[test])
            if M is BinaryGBMAll:
                shap_rows.append(m.shap(F[test]))
        if "ensemble" in pairs:
            preds["ensemble"] = np.mean([preds[e] for e in ENSEMBLE], axis=0)
        for n in names:
            pairs[n] += list(zip(preds[n].tolist(), yall[test].tolist()))
        idx = np.where(test)[0]
        for j, i in enumerate(idx):
            cases.append((data[i][0], X, {k: float(v[j]) for k, v in preds.items()}, bool(yall[i])))
    return {"pairs": pairs, "cases": cases, "shap": np.vstack(shap_rows) if shap_rows else None}


def forward(rows, future, outcome_name, models=None):
    """Train on every known year and forecast the year after each country's last data, for
    countries eligible then, with the last model in the list."""
    M = (models or _models())[-1]
    known = [(x, ys[outcome_name], X_) for _, X_, x, ys in rows if ys[outcome_name] is not None]
    if not known:
        return None, []
    pick = lambda x: x[0] if M.features == "base" else x[0] + x[1]
    X = np.array([pick(k[0]) for k in known], dtype=float)
    y = np.array([k[1] for k in known], dtype=bool)
    year = max(f[1] for f in future)
    target = [(iso, x) for iso, X_, x, ok in future if X_ == year and ok[outcome_name]]
    best = M().fit(X, y, np.array([k[2] for k in known]))
    p = best.predict(np.array([pick(t[1]) for t in target], dtype=float)) if target else []
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

    models = next(list(r["pairs"]) for r in results.values() if r)
    cell = lambda v, f="{:.3f}": f.format(v) if v is not None else "–"
    lines = [f"# Many outcomes: rolling backtest {first}-{last}", "",
             "Each row asks whether an event happens in a country in year X, forecast from data up to X-1, by models "
             "trained only on years before X. `logit` and `gbm` use the hand-built features "
             f"({len(feat_names['base'])}); the \"all tables\" models add every table automatically "
             f"({len(feat_names['all'])} features in all, see forecast/alltables.py). The all-tables boosting model is "
             "recalibrated on recent training years; `ensemble` is the mean of the plain logit and the all-tables "
             "boosting model. The base rate's AUC isn't exactly 0.5 because it changes from year to year.", ""]
    if not coups:
        lines += ["Coup outcomes are missing: their table is private (tools/importers/powell_thyne.py).", ""]

    def table(title, intro, value, fmt):
        out = [f"## {title}", "", intro, "", "| outcome | country-years | events | " + " | ".join(models) + " |",
               "|---|---|---|" + "---|" * len(models)]
        for o, r in results.items():
            if not r or not r["pairs"].get("logit"):
                continue
            n, k = len(r["pairs"]["logit"]), sum(h for _, h in r["pairs"]["logit"])
            vals = {m: value(r, m) for m in models}
            best = max((v for v in vals.values() if v is not None), default=None) if title != "Brier score" else \
                min((v for v in vals.values() if v is not None), default=None)
            cells = [(f"**{cell(v, fmt)}**" if v is not None and v == best else cell(v, fmt)) for v in vals.values()]
            out.append(f"| {LABELS[o]} | {n} | {k} | " + " | ".join(cells) + " |")
        return out + [""]

    lines += table("AUC", "The chance that a country where it happened was rated riskier than one where it didn't "
                   "(0.5 is a coin flip). Best in bold.", lambda r, m: auc(r["pairs"][m]), "{:.3f}")
    lines += table("Riskiest 10%", "The share of events that fell in the riskiest tenth of countries that year.",
                   lambda r, m: top_share(None, by_year=_by_year(r["cases"], m)), "{:.0%}")
    lines += table("Brier score", "Lower is better; it rewards well-calibrated probabilities, not just ranking.",
                   lambda r, m: sum((p - h) ** 2 for p, h in r["pairs"][m]) / len(r["pairs"][m]), "{:.4f}")
    lines += ["## Does more data help?", "",
              "Change in AUC from adding every table, on the same forecasts, with a 95% interval from 500 bootstrap "
              "resamples. An interval that includes 0 means the gain could be luck.", "",
              "| outcome | gbm: all tables − hand-built | logit: all tables − hand-built | ensemble − logit |", "|---|---|---|---|"]
    for o, r in results.items():
        if not r or "gbm, all tables" not in r["pairs"]:
            continue
        def d(a, b):
            v, lo, hi = auc_difference(r["pairs"][a], r["pairs"][b], reps=500)
            return f"{v:+.3f} ({lo:+.3f} to {hi:+.3f})"
        lines.append(f"| {LABELS[o]} | {d('gbm, all tables', 'gbm')} | {d('logit, all tables', 'logit')} | {d('ensemble', 'logit')} |")
    lines += ["", "## Calibration of the ensemble", "", "When it said about p, how often did it happen? (all outcomes pooled)", ""]
    pooled = [pr for r in results.values() if r and "ensemble" in r["pairs"] for pr in r["pairs"]["ensemble"]]
    for lo, hi in ((0, .02), (.02, .05), (.05, .1), (.1, .2), (.2, .4), (.4, 1.01)):
        b = [(p, h) for p, h in pooled if lo <= p < hi]
        if b:
            lines.append(f"- said {lo:.0%}–{min(hi, 1):.0%} (mean {sum(p for p, _ in b) / len(b):.1%}): happened "
                         f"{sum(h for _, h in b) / len(b):.1%} (n={len(b)})")
    lines += ["", "## What the all-tables boosting model relies on", "",
              "The features with the largest average effect (mean |SHAP|, in log-odds) on its forecasts in the test years. "
              "These are patterns in the data, not causes.", ""]
    for o, r in results.items():
        if r and r["shap"] is not None:
            imp = np.abs(r["shap"]).mean(axis=0)
            top = np.argsort(-imp)[:8]
            lines.append(f"- **{LABELS[o]}:** " + ", ".join(f"{feat_names['all'][i]} ({imp[i]:.2f})" for i in top))
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
             "Onset outcomes leave out countries already in that condition. Tables that end earlier are extended at each "
             "country's trend over its last 3 years: Maddison GDP and population end in 2022, so 2023-2025 are estimates, "
             "and economic collapse, which needs real growth figures to say who is eligible, isn't ranked.", ""]
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
    ap.add_argument("--forward", action="store_true", help="also forecast the year after the last data")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    rows, future, feat_names, coups = build()
    print(f"{len(rows)} country-years, {len(feat_names['all'])} features, coup table {'found' if coups else 'missing'}", flush=True)
    results, fwd = {}, {}
    for o in args.outcomes.split(","):
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            results[o] = backtest(rows, o, range(args.first, args.last + 1))
            if args.forward:
                fwd[o] = forward(rows, future, o)
        r = results[o]
        print(o, "AUC", {k: round(auc(v) or 0, 3) for k, v in r["pairs"].items()} if r else "no data", flush=True)
    text = report(results, feat_names, coups, args.first, args.last) + (forward_report(fwd) if fwd else "")
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
