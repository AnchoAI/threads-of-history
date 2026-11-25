"""A Markov chain over country states, and the two baselines every model must beat.

Every model has fit(seqs, before) and predict(state, h) -> {state: probability}.
`seqs` is {iso3: {year: state}}; fit() uses only transitions whose second year is
before `before`, so nothing from the test years leaks in.
"""
from __future__ import annotations


def _transitions(seqs, before):
    for years in seqs.values():
        for y, s in years.items():
            nxt = years.get(y + 1)
            if nxt is not None and y + 1 < before:
                yield s, nxt


class Markov:
    """P(next state | this state), counted from history, with add-alpha smoothing so
    a transition never seen in training still gets a small chance."""

    name = "markov"

    def __init__(self, states, alpha: float = 0.5):
        self.states, self.alpha = list(states), alpha

    def fit(self, seqs, before, **_):
        counts = {a: {b: self.alpha for b in self.states} for a in self.states}
        for a, b in _transitions(seqs, before):
            counts[a][b] += 1
        self.P = {a: {b: c / sum(row.values()) for b, c in row.items()} for a, row in counts.items()}
        return self

    def predict(self, state, h=1, **_):
        dist = {s: float(s == state) for s in self.states}
        for _ in range(h):
            dist = {b: sum(dist[a] * self.P[a][b] for a in self.states) for b in self.states}
        return dist


class BaseRate:
    """Ignore the current state: forecast the share of each state across training years."""

    name = "base-rate"

    def __init__(self, states, alpha: float = 0.5):
        self.states, self.alpha = list(states), alpha

    def fit(self, seqs, before, **_):
        counts = {s: self.alpha for s in self.states}
        for years in seqs.values():
            for y, s in years.items():
                if y < before:
                    counts[s] += 1
        total = sum(counts.values())
        self.dist = {s: c / total for s, c in counts.items()}
        return self

    def predict(self, state, h=1, **_):
        return dict(self.dist)


class Persistence:
    """'Next year looks like this year': almost all the probability on the current state.
    `keep` is set below 1 so one surprise doesn't give an infinite log score."""

    name = "persistence"

    def __init__(self, states, keep: float = 0.95):
        self.states, self.keep = list(states), keep

    def fit(self, seqs, before, **_):
        return self

    def predict(self, state, h=1, **_):
        rest = (1 - self.keep) / (len(self.states) - 1)
        return {s: self.keep if s == state else rest for s in self.states}
