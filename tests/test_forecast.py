"""Tests for forecast/ (no real data needed)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from forecast.backtest import SYNTH_P, SYNTH_STATES, run, synthetic  # noqa: E402
from forecast.markov import BaseRate, Markov, Persistence  # noqa: E402
from forecast.panel import load_table  # noqa: E402
from forecast.scoring import brier, calibration, log_score  # noqa: E402
from forecast.states import classify, sequences  # noqa: E402


def test_markov_recovers_the_true_transition_chances():
    world = synthetic(countries=200, start=1900, end=2020)
    m = Markov(SYNTH_STATES).fit(sequences(world), before=3000)
    for a in ("democracy", "autocracy", "civil-war"):
        for b in SYNTH_STATES:
            assert abs(m.P[a][b] - SYNTH_P[a][b]) < 0.02, (a, b)
    two = m.predict("civil-war", 2)
    assert abs(sum(two.values()) - 1) < 1e-9


def test_training_never_sees_the_test_years():
    # A country that is a democracy until 1999, then permanently at civil war.
    seqs = {"AAA": {y: ("democracy" if y < 2000 else "civil-war") for y in range(1950, 2020)}}
    m = Markov(["democracy", "civil-war"]).fit(seqs, before=2000)
    assert m.P["democracy"]["civil-war"] < 0.05  # the 1999→2000 switch is after the cutoff
    b = BaseRate(["democracy", "civil-war"]).fit(seqs, before=2000)
    assert b.dist["civil-war"] < 0.05


def test_markov_beats_both_baselines_on_a_markov_world():
    world = synthetic(countries=120, start=1900, end=2024)
    known = lambda X: {k: v for k, v in world.items() if k[1] < X}
    res = run(known, world, SYNTH_STATES, range(1980, 2000), horizons=(1,))
    assert res[("markov", 1)]["brier"] < res[("persistence", 1)]["brier"] < res[("base-rate", 1)]["brier"]


def test_scores():
    assert brier({"a": 1.0, "b": 0.0}, "a") == 0
    assert brier({"a": 1.0, "b": 0.0}, "b") == 2
    assert abs(brier({"a": .5, "b": .5}, "a") - .5) < 1e-12
    assert log_score({"a": 1.0}, "a") == 0
    cal = calibration([(0.1, False)] * 9 + [(0.1, True)], bins=10)
    (p, o, n), = cal
    assert abs(p - 0.1) < 1e-9 and abs(o - 0.1) < 1e-9 and n == 10
    assert Persistence(["a", "b", "c"]).predict("a")["a"] == 0.95


def test_load_table_hides_figures_published_later(tmp_path):
    (tmp_path / "gdp.csv").write_text(
        "entity,at,value,published\nAAA,1990,1.0,1991-04-01\nAAA,1991,2.0,1992-04-01\nAAA,1992,3.0,\n", encoding="utf-8")
    assert load_table("gdp", tables=tmp_path) == {("AAA", 1990): 1.0, ("AAA", 1991): 2.0, ("AAA", 1992): 3.0}
    # Standing at the start of 1992, the 1991 figure (published April 1992) is not yet known.
    assert load_table("gdp", known_before=1992, tables=tmp_path) == {("AAA", 1990): 1.0}
    # At the start of 1993 the 1991 figure is out, and the 1992 one (no published date)
    # counts as known because 1992 is over.
    assert len(load_table("gdp", known_before=1993, tables=tmp_path)) == 3
    assert ("AAA", 1992) not in load_table("gdp", known_before=1992, tables=tmp_path)


def test_classify_uses_the_first_matching_rule_and_skips_gaps():
    tables = {"dem": {("AAA", 2000): 0.8, ("BBB", 2000): 0.2},
              "war": {("AAA", 2000): 1}}
    rules = [("war", lambda v: (v("war") or 0) >= 1), ("democracy", lambda v: v("dem") >= 0.5), ("autocracy", lambda v: True)]
    got = classify(tables, rules, required=["dem"])
    assert got == {("AAA", 2000): "war", ("BBB", 2000): "autocracy"}
    assert classify({"dem": {}, "war": {("CCC", 2000): 1}}, rules, required=["dem"]) == {}


def test_logit_uses_conditions_the_markov_chain_cannot_see():
    import random
    from forecast.logit import Logit
    rng = random.Random(3)
    states = ["democracy", "autocracy", "civil-war"]
    world, dem = {}, {}
    for c in range(80):
        iso = f"C{c:02d}"
        score = rng.random()  # fixed per country: low scores make civil war far likelier
        s = "democracy" if score > 0.5 else "autocracy"
        for y in range(1950, 2011):
            world[(iso, y)] = s
            dem[(iso, y)] = score
            war = 0.02 + 0.25 * (1 - score) ** 3
            s = "civil-war" if rng.random() < war else ("democracy" if score > 0.5 else "autocracy")
    known = lambda X: {k: v for k, v in world.items() if k[1] < X}
    tables = lambda X: {"vdem-electoral-democracy": {k: v for k, v in dem.items() if k[1] < X}}
    res = run(known, world, states, range(1990, 2000), horizons=(1,), models=(Markov, Logit), tables_known_before=tables)
    assert res[("logit", 1)]["log"] < res[("markov", 1)]["log"]


def test_neighbours_rebuild_federations():
    from forecast.neighbours import neighbours
    assert "RUS" in neighbours("UKR", 2020)
    ussr = neighbours("RUS", 1980)
    assert "AFG" in ussr and "IRN" in ussr and "UKR" not in ussr  # via Turkmenistan etc.; members excluded
    assert "AFG" not in neighbours("RUS", 2000)
    assert neighbours("DDR", 1970) == {"DEU", "POL", "CZE"}
