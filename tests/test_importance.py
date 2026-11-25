"""Tests for tools/importance.py (no network)."""
import importance as m


def _items(n):
    return {f"e{i}": {"path": None, "wikidata": f"Q{i}", "importance": 3, "title": f"E{i}"} for i in range(n)}


def test_pyramid_follows_targets():
    items = _items(100)
    degree = {k: i for i, k in enumerate(items)}
    sitelinks = {f"Q{i}": i for i in range(100)}
    p = m.propose(items, degree, sitelinks)
    counts = {lvl: sum(1 for v, _ in p.values() if v == lvl) for lvl in range(1, 6)}
    assert counts[5] == 4 and counts[4] == 14 and counts[1] == 14
    # the best-covered, best-connected item comes out on top
    assert p["e99"][0] == 5 and p["e0"][0] == 1


def test_moves_are_capped():
    items = _items(50)
    for k in items:
        items[k]["importance"] = 5
    items["e0"]["importance"] = 5
    p = m.propose(items, {k: 0 for k in items}, {})
    assert all(v >= 5 - m.MAX_MOVE for v, _ in p.values())


def test_apply_touches_only_the_importance_line(tmp_path):
    f = tmp_path / "a.yaml"
    f.write_text("id: a\ntitle: A\nimportance: 4\nregions:\n- x\n", encoding="utf-8")
    items = {"a": {"path": f, "wikidata": None, "importance": 4, "title": "A"}}
    assert m.apply(items, {"a": (2, 0.1)}) == 1
    assert f.read_text(encoding="utf-8") == "id: a\ntitle: A\nimportance: 2\nregions:\n- x\n"
