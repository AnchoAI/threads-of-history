"""A transition model with covariates: P(state in year t+h | state in t, conditions in t).

It's a multinomial logistic regression, fitted separately for each horizon h (a "direct"
forecast). With only the current state as input it reduces to the Markov chain, so any
gain over the chain comes from the extra conditions:

  - V-Dem electoral democracy score (the number, not just above or below 0.5)
  - log GDP per capita and its average growth over the last 3 years (Maddison)
  - log infant mortality (World Bank, from 1960)
  - how long the country has been in its current state (history has memory)
  - years of armed conflict or civil war in the last 10 years

The variant LogitNeighbours also uses the share of land neighbours in armed conflict or civil
war that year, and whether any neighbour was in civil war (see forecast/neighbours.py). In the
October 2026 backtest it did not improve on Logit, so it is reported alongside, not used by default.
LogitYouth adds the youth bulge (share of 15-24 year olds among adults, wdi-youth-bulge).
LogitRegion adds region-wide unrest: the share of other countries in the same V-Dem region
in conflict, and the share with a new conflict this year or last. LogitMobilization adds
mass protest: the country's own level and change, and its region's average.

Missing values become 0 after standardising, with a flag saying they were missing, so
gaps in the data don't drop countries. Everything is computed from tables as known before
the cutoff year, so nothing leaks from the test years.
"""
from __future__ import annotations

import math
import warnings

import numpy as np

from .neighbours import neighbours

CONFLICT = {"armed-conflict", "civil-war"}
TABLES = ["vdem-electoral-democracy", "maddison-gdp-per-capita", "wdi-infant-mortality", "wdi-youth-bulge",
          "vdem-region", "vdem-mass-mobilization"]


def _latest(table, iso, year, max_back):
    for y in range(year, year - max_back - 1, -1):
        v = table.get((iso, y))
        if v is not None:
            return v
    return None


def features(states, iso, year, seq, tables, world=None, extras=()):
    """Feature vector for one country-year. `seq` is {year: state} for the country;
    `world` is {iso: {year: state}} for every country, for neighbour effects."""
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
    near = [world[n][year] for n in neighbours(iso, year) if world and year in world.get(n, {})] if iso and "neighbours" in extras else []
    near_conflict = sum(s2 in CONFLICT for s2 in near) / len(near) if near else None
    near_civil_war = float(any(s2 == "civil-war" for s2 in near)) if near else None
    raw = [
        dem,
        math.log(gdp) if gdp else None,
        growth,
        math.log(imr) if imr else None,
        math.log1p(run),
        conflict10 / 10,
    ]
    if "neighbours" in extras:
        raw += [near_conflict, near_civil_war]
    if "youth" in extras:
        raw.append(_latest(tables.get("wdi-youth-bulge", {}), iso, year, 5))
    if "region" in extras:
        raw += _region_features(iso, year, tables, world)
    if "mobilization" in extras:
        mob = tables.get("vdem-mass-mobilization", {})
        own, before = mob.get((iso, year)), mob.get((iso, year - 1))
        raw += [own, own - before if own is not None and before is not None else None,
                _regional(tables, world, iso, year)["mobilization"]]
    return one_hot, raw


# ---------------------------------------------------------------- region-wide unrest

_REGION_CACHE: dict = {}


def _regional(tables, world, iso, year):
    """Averages over the other countries in iso's V-Dem region that year: share in conflict,
    share with a new conflict in this year or the last, and mean mass mobilization.
    Cached per (tables, world) pair, since a backtest asks for every country in turn."""
    key = (id(tables), id(world))
    if _REGION_CACHE.get("key") != key:
        _REGION_CACHE.clear()
        _REGION_CACHE["key"] = key
        members = {}
        for (c, y), r in tables.get("vdem-region", {}).items():
            members.setdefault((r, y), []).append(c)
        _REGION_CACHE["members"] = members
    region = tables.get("vdem-region", {}).get((iso, year))
    if region is None:
        return {"conflict": None, "onsets": None, "mobilization": None}
    cache_key = ("r", iso, year)
    if cache_key in _REGION_CACHE:
        return _REGION_CACHE[cache_key]
    others = [c for c in _REGION_CACHE["members"].get((region, year), []) if c != iso]
    w = world or {}
    states = [w.get(c, {}).get(year) for c in others]
    known = [s for s in states if s is not None]

    def onset(c, y):
        seq = w.get(c, {})
        return seq.get(y) in CONFLICT and seq.get(y - 1) not in CONFLICT and seq.get(y - 1) is not None

    mob = [tables.get("vdem-mass-mobilization", {}).get((c, year)) for c in others]
    mob = [m for m in mob if m is not None]
    out = {
        "conflict": sum(s in CONFLICT for s in known) / len(known) if known else None,
        "onsets": sum(onset(c, year) or onset(c, year - 1) for c in others) / len(others) if others else None,
        "mobilization": sum(mob) / len(mob) if mob else None,
    }
    _REGION_CACHE[cache_key] = out
    return out


def _region_features(iso, year, tables, world):
    r = _regional(tables, world, iso, year)
    return [r["conflict"], r["onsets"]]


class Logit:
    name = "logit"
    extras: tuple[str, ...] = ()

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
                    oh, raw = features(self.states, iso, t, seq, self.tables, seqs, self.extras)
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
        oh, raw = features(self.states, iso, year, seq, self.tables, self.seqs, self.extras)
        X, _ = self._design(np.array([oh]), [raw], stats)
        p = _softmax(X @ W)[0]
        return dict(zip(self.states, p.tolist()))


class LogitNeighbours(Logit):
    name = "logit+neighbours"
    extras = ("neighbours",)


class LogitYouth(Logit):
    name = "logit+youth"
    extras = ("youth",)


class LogitRegion(Logit):
    name = "logit+region"
    extras = ("region",)


class LogitMobilization(Logit):
    name = "logit+protest"
    extras = ("mobilization",)


class LogitRegionMobilization(Logit):
    name = "logit+region+protest"
    extras = ("region", "mobilization")


class LogitUnrest(Logit):
    """Neighbours, region-wide unrest and protest together."""
    name = "logit+unrest"
    extras = ("neighbours", "region", "mobilization")


def _softmax(Z):
    Z = Z - Z.max(axis=1, keepdims=True)
    E = np.exp(Z)
    return E / E.sum(axis=1, keepdims=True)
