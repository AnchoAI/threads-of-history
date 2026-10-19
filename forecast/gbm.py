"""Gradient boosting on everything we have: P(state in year t+h | conditions in t).

The logit models add conditions one family at a time and keep a family only if it helps.
This model takes the other route: give it every table and let it find the patterns, including
thresholds and interactions a logit can't express (for example "poor AND neighbours at war").
It uses LightGBM, fitted separately for each horizon, on:

  - every feature of LogitAll (state, democracy, income, growth, infant mortality, time in
    state, past conflict, neighbours, region-wide unrest, protest, economic shocks, violence),
  - plus liberal democracy and civil liberties, their 1- and 5-year changes, log population,
    the youth bulge and the V-Dem region code.

LightGBM handles missing values itself, so gaps stay gaps. `explain()` returns SHAP values
(LightGBM's built-in TreeSHAP): how much each feature pushed a forecast up or down.

Needs the optional libraries in forecast/requirements-ml.txt.
"""
from __future__ import annotations

import math

import numpy as np

from .logit import CONFLICT, TABLES as LOGIT_TABLES, _latest, features

TABLES = list(dict.fromkeys(LOGIT_TABLES + ["vdem-liberal-democracy", "vdem-civil-liberties", "maddison-population"]))
EXTRAS = ("neighbours", "youth", "region", "shocks", "violence", "mobilization")  # the order features() appends them

NAMES = {
    "base": ["electoral democracy", "log GDP per capita", "GDP growth (3 yr)", "log infant mortality",
             "years in current state", "conflict years (last 10)"],
    "neighbours": ["neighbours in conflict", "neighbour in civil war"],
    "youth": ["youth bulge"],
    "region": ["region in conflict", "region new conflicts"],
    "shocks": ["growth shock", "inflation"],
    "violence": ["log deaths (GED)", "log deaths Q4", "log non-state deaths", "months with violence", "deaths share in Q4"],
    "mobilization": ["mass protest", "protest change", "region protest"],
    "more": ["liberal democracy", "civil liberties", "democracy change (1 yr)", "democracy change (5 yr)",
             "civil liberties change (5 yr)", "log population", "V-Dem region"],
}


def feature_names(states):
    return [f"state: {s}" for s in states] + NAMES["base"] + [n for e in EXTRAS for n in NAMES[e]] + NAMES["more"]


def _more(iso, year, tables):
    get = lambda name, y: tables.get(name, {}).get((iso, y))
    diff = lambda a, b: a - b if a is not None and b is not None else None
    dem, civ = get("vdem-electoral-democracy", year), get("vdem-civil-liberties", year)
    pop = _latest(tables.get("maddison-population", {}), iso, year, 2)
    return [get("vdem-liberal-democracy", year), civ,
            diff(dem, get("vdem-electoral-democracy", year - 1)), diff(dem, get("vdem-electoral-democracy", year - 5)),
            diff(civ, get("vdem-civil-liberties", year - 5)),
            math.log(pop) if pop else None, get("vdem-region", year)]


def row(states, iso, year, seq, tables, world):
    oh, raw = features(states, iso, year, seq, tables, world, EXTRAS)
    return [float(v) if v is not None else np.nan for v in oh + raw + _more(iso, year, tables)]


class GBM:
    name = "gbm"
    params = dict(objective="multiclass", learning_rate=0.05, n_estimators=300, num_leaves=15,
                  min_child_samples=30, subsample=0.8, subsample_freq=1, colsample_bytree=0.8,
                  reg_lambda=1.0, random_state=1, verbose=-1, n_jobs=1)

    def __init__(self, states, **params):
        self.states = list(states)
        self.params = {**self.params, **params}

    def fit(self, seqs, before, tables=None, horizons=(1,), **_):
        import lightgbm as lgb

        self.tables, self.seqs = tables or {}, seqs
        self.models = {}
        for h in horizons:
            X, y = [], []
            for iso, seq in seqs.items():
                for t in seq:
                    out = seq.get(t + h)
                    if out is None or t + h >= before:
                        continue
                    X.append(row(self.states, iso, t, seq, self.tables, seqs))
                    y.append(self.states.index(out))
            y = np.array(y)
            present = sorted(set(y.tolist()))  # LightGBM needs every class seen; map to the ones present
            model = lgb.LGBMClassifier(num_class=len(present), **self.params) if len(present) > 2 else \
                lgb.LGBMClassifier(**{**self.params, "objective": "binary"})
            model.fit(np.array(X), np.searchsorted(present, y))
            self.models[h] = (model, present)
        return self

    def _x(self, state, iso, year):
        seq = self.seqs.get(iso, {})
        if iso is None or seq.get(year) != state:
            seq = {year: state}
        return np.array([row(self.states, iso, year, seq, self.tables, self.seqs)])

    def predict(self, state, h=1, iso=None, year=None):
        model, present = self.models[h]
        p = model.predict_proba(self._x(state, iso, year))[0]
        out = dict.fromkeys(self.states, 0.0)
        for k, c in enumerate(present):
            out[self.states[c]] = float(p[k])
        return out

    def explain(self, state, h=1, iso=None, year=None, target=CONFLICT):
        """SHAP values, in log-odds, for the summed probability of the `target` states:
        {feature: contribution}. Computed per class by TreeSHAP, then weighted by the class
        probabilities so the parts add up for a sum of classes."""
        model, present = self.models[h]
        x = self._x(state, iso, year)
        contrib = model.booster_.predict(x, pred_contrib=True)[0]
        k = len(present) if len(present) > 2 else 1
        contrib = np.array(contrib).reshape(k, -1)  # per class: features..., bias
        p = model.predict_proba(x)[0]
        idx = [i for i, c in enumerate(present) if self.states[c] in target]
        if k == 1:
            values = contrib[0, :-1] * (1 if idx == [1] else -1)
        else:
            # d log(sum_t p_t) / d z_c = (1[c in t] * p_c / sum_t p_t) - p_c
            pt = p[idx].sum() or 1e-12
            weights = np.array([(p[c] / pt if c in idx else 0.0) - p[c] for c in range(k)])
            values = weights @ contrib[:, :-1]
        return dict(zip(feature_names(self.states), values.tolist()))

    def importance(self, h=1):
        """Share of the total split gain per feature: a quick global view (SHAP is the better one)."""
        model, _ = self.models[h]
        gain = model.booster_.feature_importance(importance_type="gain")
        return dict(zip(feature_names(self.states), (gain / gain.sum()).tolist()))
