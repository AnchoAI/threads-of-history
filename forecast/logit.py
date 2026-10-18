"""A transition model with covariates: P(state in year t+h | state in t, conditions in t).

It's a multinomial logistic regression, fitted separately for each horizon h (a "direct"
forecast). With only the current state as input it reduces to the Markov chain, so any
gain over the chain comes from the extra conditions:

  - V-Dem electoral democracy score (the number, not just above or below 0.5)
  - log GDP per capita and its average growth over the last 3 years (Maddison)
  - log infant mortality (World Bank, from 1960)
  - how long the country has been in its current state (history has memory)
  - years of armed conflict or civil war in the last 10 years

Missing values become 0 after standardising, with a flag saying they were missing, so
gaps in the data don't drop countries. Everything is computed from tables as known before
the cutoff year, so nothing leaks from the test years.
"""
from __future__ import annotations

import math
import warnings

import numpy as np

CONFLICT = {"armed-conflict", "civil-war"}
TABLES = ["vdem-electoral-democracy", "maddison-gdp-per-capita", "wdi-infant-mortality"]


def _latest(table, iso, year, max_back):
    for y in range(year, year - max_back - 1, -1):
        v = table.get((iso, y))
        if v is not None:
            return v
    return None


def features(states, iso, year, seq, tables):
    """Feature vector for one country-year. `seq` is {year: state} for the country."""
    s = seq[year]
    one_hot = [float(s == x) for x in states]
    dem = tables.get("vdem-electoral-democracy", {}).get((iso, year))
    gdp_t = tables.get("maddison-gdp-per-capita", {})
    gdp = _latest(gdp_t, iso, year, 2)
    gdp3 = _latest(gdp_t, iso, year - 3, 2)
    imr = _latest(tables.get("wdi-infant-mortality", {}), iso, year, 5)
    run = 0
    while seq.get(year - run) == s:
        run += 1
    conflict10 = sum(1 for y in range(year - 9, year + 1) if seq.get(y) in CONFLICT)
    growth = (math.log(gdp) - math.log(gdp3)) / 3 if gdp and gdp3 else None
    raw = [
        dem,
        math.log(gdp) if gdp else None,
        growth,
        math.log(imr) if imr else None,
        math.log1p(run),
        conflict10 / 10,
    ]
    return one_hot, raw


class Logit:
    name = "logit"

    def __init__(self, states, l2: float = 1.0, iters: int = 400, lr: float = 0.5):
        self.states, self.l2, self.iters, self.lr = list(states), l2, iters, lr

    def fit(self, seqs, before, tables=None, horizons=(1,), **_):
        self.tables, self.seqs = tables or {}, seqs
        self.models = {}
        for h in horizons:
            X_oh, X_raw, y = [], [], []
            for iso, seq in seqs.items():
                for t, s in seq.items():
                    out = seq.get(t + h)
                    if out is None or t + h >= before:
                        continue
                    oh, raw = features(self.states, iso, t, seq, self.tables)
                    X_oh.append(oh)
                    X_raw.append(raw)
                    y.append(self.states.index(out))
            self.models[h] = self._train(np.array(X_oh), X_raw, np.array(y))
        return self

    def _design(self, X_oh, X_raw, stats=None):
        raw = np.array([[np.nan if v is None else v for v in r] for r in X_raw], dtype=float)
        missing = np.isnan(raw)
        if stats is None:
            with warnings.catch_warnings():  # a column can be all missing, e.g. infant mortality before 1960
                warnings.simplefilter("ignore", RuntimeWarning)
                mean = np.nanmean(raw, axis=0)
                std = np.nanstd(raw, axis=0)
            stats = (np.nan_to_num(mean), np.where(np.nan_to_num(std) > 0, np.nan_to_num(std), 1.0))
        z = np.where(missing, 0.0, (raw - stats[0]) / stats[1])
        return np.hstack([X_oh, z, missing.astype(float)]), stats

    def _train(self, X_oh, X_raw, y):
        X, stats = self._design(X_oh, X_raw)
        n, d = X.shape
        k = len(self.states)
        W = np.zeros((d, k))
        Y = np.eye(k)[y]
        # Adam on the mean cross-entropy plus an L2 penalty: a convex problem, so plain and stable.
        m = np.zeros_like(W)
        v = np.zeros_like(W)
        for i in range(1, self.iters + 1):
            P = _softmax(X @ W)
            g = X.T @ (P - Y) / n + self.l2 * W / n
            m = 0.9 * m + 0.1 * g
            v = 0.999 * v + 0.001 * g * g
            W -= self.lr * 0.1 * (m / (1 - 0.9 ** i)) / (np.sqrt(v / (1 - 0.999 ** i)) + 1e-8)
        return W, stats

    def predict(self, state, h=1, iso=None, year=None):
        W, stats = self.models[h]
        seq = self.seqs.get(iso, {})
        if iso is None or seq.get(year) != state:
            seq = {year: state}
        oh, raw = features(self.states, iso, year, seq, self.tables)
        X, _ = self._design(np.array([oh]), [raw], stats)
        p = _softmax(X @ W)[0]
        return dict(zip(self.states, p.tolist()))


def _softmax(Z):
    Z = Z - Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(axis=1, keepdims=True)
