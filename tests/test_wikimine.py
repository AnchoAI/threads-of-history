"""Tests for tools/wikimine.py that need no network."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import wikimine as wm  # noqa: E402


def test_norm_title():
    assert wm.norm_title("treaty_of_Versailles#Terms") == "Treaty of Versailles"
    assert wm.norm_title("Russian%20Revolution") == "Russian Revolution"


def test_split_sentences_keeps_link_positions_and_abbreviations():
    text = "The U.S. Senate rejected the Treaty of Versailles. Gen. Pershing went home. No links here at all."
    start = text.index("Treaty")
    links = [(start, start + len("Treaty of Versailles"), "Treaty of Versailles")]
    out = wm.split_sentences("Aftermath", text, links)
    assert len(out) == 1
    s = out[0]
    assert s["text"] == "The U.S. Senate rejected the Treaty of Versailles."
    a, b, t = s["links"][0]
    assert s["text"][a:b] == "Treaty of Versailles" and t == "Treaty of Versailles"


def test_html_sentences_skip_references():
    page = ('<html><body><section><h2>Background</h2><p>The assassination of '
            '<a rel="mw:WikiLink" href="./Archduke_Franz_Ferdinand" title="x">Franz Ferdinand</a> led to the '
            '<a rel="mw:WikiLink" href="./July_Crisis">July Crisis</a>.<sup class="mw-ref reference"><a href="#c">[1]</a></sup> '
            'It spread.</p><table><tr><td><a rel="mw:WikiLink" href="./Nope">Nope</a></td></tr></table></section></body></html>')
    out = list(wm.html_sentences(page))
    assert [s["text"] for s in out] == ["The assassination of Franz Ferdinand led to the July Crisis."]
    s = out[0]
    assert s["section"] == "Background"
    assert [s["text"][a:b] for a, b, _ in s["links"]] == ["Franz Ferdinand", "July Crisis"]
    assert [t for _, _, t in s["links"]] == ["Archduke Franz Ferdinand", "July Crisis"]


def test_wikitext_sentences():
    pytest.importorskip("mwparserfromhell")
    text = ("{{Infobox military conflict|name=X}}\n'''The July Crisis''' was a crisis.<ref>Book</ref> "
            "It led to [[World War I|the First World War]] in 1914.\n\n== Aftermath ==\n"
            "* A list item with [[Treaty of Versailles]].\n\n"
            "The [[treaty of Versailles]] was signed in [[Paris]].\n[[Category:Crises]]")
    out = wm.wikitext_sentences(text)
    texts = [s["text"] for s in out]
    assert "It led to the First World War in 1914." in texts
    s = next(s for s in out if s["text"].startswith("It led"))
    a, b, t = s["links"][0]
    assert s["text"][a:b] == "the First World War" and t == "World War I"
    s2 = next(s for s in out if s["text"].startswith("The Treaty") or s["text"].startswith("The treaty"))
    assert s2["section"] == "Aftermath"
    assert not any("list item" in x for x in texts)


def row(text, me, links):
    out = []
    for label, target in links:
        a = text.index(label)
        out.append([a, a + len(label), target])
    return {"text": text, "qid": me, "links": out, "section": "", "article": "A"}


def test_candidates_directions():
    q = {"July Crisis": "Q2", "World War I": "Q3", "Treaty of Versailles": "Q4", "Western Front": "Q5"}
    r = row("The July Crisis led to World War I.", "Q1", [("July Crisis", "July Crisis"), ("World War I", "World War I")])
    assert [(c["from"], c["to"], c["type"]) for c in wm.sentence_candidates(r, q)] == [("Q2", "Q3", "led_to")]
    # No event before the phrase: the article itself is the subject.
    r = row("It led to World War I.", "Q1", [("World War I", "World War I")])
    assert [(c["from"], c["to"], c["subject"]) for c in wm.sentence_candidates(r, q)] == [("Q1", "Q3", "article")]
    # Backward phrase: the event after it is the cause.
    r = row("The treaty was signed in response to World War I.", "Q4", [("World War I", "World War I")])
    assert [(c["from"], c["to"]) for c in wm.sentence_candidates(r, q)] == [("Q3", "Q4")]
    r = row("The front was part of World War I.", "Q5", [("World War I", "World War I")])
    assert [(c["from"], c["to"], c["type"]) for c in wm.sentence_candidates(r, q)] == [("Q5", "Q3", "part_of")]
    r = row("It was inspired by the July Crisis.", "Q1", [("July Crisis", "July Crisis")])
    assert [(c["from"], c["to"], c["type"]) for c in wm.sentence_candidates(r, q)] == [("Q2", "Q1", "influenced")]


def test_candidates_negation_and_hedging():
    q = {"World War I": "Q3"}
    r = row("It did not lead to World War I.", "Q1", [("World War I", "World War I")])
    assert wm.sentence_candidates(r, q) == []
    r = row("Some historians argue it may have led to World War I.", "Q1", [("World War I", "World War I")])
    assert wm.sentence_candidates(r, q)[0]["hedged"]


def test_date_ok():
    a, b = {"start": "1914-07-28"}, {"start": "1919-06-28", "end": None}
    assert wm.date_ok("led_to", a, b) and not wm.date_ok("led_to", b, a)
    assert wm.date_ok("part_of", {"start": "1916"}, {"start": "1914", "end": "1918"})
    assert not wm.date_ok("part_of", {"start": "1930"}, {"start": "1914", "end": "1918"})


def test_slugify_matches_schema():
    import re
    for title, start in [("Treaty of Versailles", "1919-06-28"), ("Battle of the Somme (1916)", "1916-07-01"),
                         ("Révolution française", "1789"), ("Siege of Alesia", "-0052")]:
        assert re.fullmatch(r"[a-z0-9]+(-[a-z0-9]+)*", wm.slugify(title, start))
    assert wm.slugify("Siege of Alesia", "-0052") == "siege-of-alesia-52-bce"
    assert wm.slugify("1912 Ottoman coup d'état", "1912-07") == "1912-ottoman-coup-d-etat"


def test_write_produces_valid_links(tmp_path):
    """End to end from candidates: the link files pass the schema."""
    import jsonschema
    import yaml
    root = Path(__file__).resolve().parent.parent
    out = tmp_path / "wm"
    out.mkdir()
    events = [{"qid": "Q1", "title": "July Crisis", "start": "1914-06-28", "end": "1914-08-04", "sitelinks": 9, "classes": []},
              {"qid": "Q2", "title": "Neverheard War", "start": "1915-01-01", "end": None, "sitelinks": 9, "classes": []}]
    wm.write_jsonl(out / "events.jsonl", events)
    cand = {"from": "Q1", "to": "Q2", "type": "led_to", "from_title": "July Crisis", "to_title": "Neverheard War",
            "from_id": None, "to_id": None, "date_ok": True, "wikidata_agrees": False, "in_data": False,
            "hedged": False, "score": 3,
            "evidence": [{"article": "July Crisis", "section": "", "sentence": "The July Crisis led to the Neverheard War.",
                          "cue": "led to", "hedged": False, "subject": "named", "url": wm.wiki_url("July Crisis")}]}
    wm.write_jsonl(out / "candidates.jsonl", [cand])
    wm.main(["--out", str(out), "--root", str(tmp_path), "write"])
    schema = json.loads((root / "schema" / "threads-of-history.schema.json").read_text())
    link_schema = {"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": "#/$defs/link"}
    files = list((out / "links").glob("*.yaml"))
    assert len(files) == 1
    d = yaml.safe_load(files[0].read_text())
    jsonschema.validate(d, link_schema)
    assert d["review"]["status"] == "unverified"
    assert d["id"] == "july-crisis-1914--led_to--neverheard-war-1915"
    assert len(list((out / "events").glob("*.yaml"))) == 2


def test_candidates_subject_and_object():
    q = {"World War I": "Q3", "October Revolution": "Q6"}
    # The sentence's subject is something else, not the article's event.
    r = row("The failures of the Provisional Government led to the October Revolution.", "Q1",
            [("Provisional Government", "Russian Provisional Government"), ("October Revolution", "October Revolution")])
    assert [c["subject"] for c in wm.sentence_candidates(r, q)] == ["unclear"]
    # The object is the first link after the phrase; here it is not an event, so nothing.
    r = row("The battle led to the fall of Paris during World War I.", "Q1", [("Paris", "Paris"), ("World War I", "World War I")])
    assert wm.sentence_candidates(r, q) == []
    # "part of" needs the event right after it.
    r = row("They defended the last unoccupied part of Belgium until the end of World War I.", "Q1",
            [("Belgium", "Belgium"), ("World War I", "World War I")])
    assert wm.sentence_candidates(r, q) == []


def test_article_subject():
    assert wm.article_is_subject("The battle ", "Battle of the Marne", ["battle"])
    assert wm.article_is_subject("This ", "Battle of the Marne", ["battle"])
    assert wm.article_is_subject("The conflict ", "Polish–Soviet War", ["war"])
    assert not wm.article_is_subject("The war on land ", "Battle of Heligoland Bight", ["battle"])
    assert not wm.article_is_subject("These weaknesses ", "World War I", ["war"])
    assert not wm.article_is_subject("The conflict ", "Treaty of Poti", ["treaty"])


def test_infobox_part_of():
    pytest.importorskip("mwparserfromhell")
    text = ("{{Infobox military conflict\n| conflict = Battle of the Somme\n"
            "| partof = the [[Western Front (World War I)|Western Front]] of [[World War I]]\n| date = 1916\n}}\n"
            "The '''Battle of the Somme''' was a battle.")
    rows = wm.wikitext_infobox(text)
    assert rows[0]["text"] == "Part of the Western Front of World War I"
    assert [t for _, _, t in rows[0]["links"]] == ["Western Front (World War I)", "World War I"]
    q = {"World War I": "Q3"}
    r = dict(rows[0], qid="Q1", article="Battle of the Somme")
    assert [(c["from"], c["to"], c["type"]) for c in wm.sentence_candidates(r, q)] == [("Q1", "Q3", "part_of")]


def test_list_of_objects():
    q = {"Treaty of Versailles": "Q4", "World War I": "Q3", "October Revolution": "Q6"}
    r = row("The war led to the October Revolution and the Treaty of Versailles.", "Q3",
            [("October Revolution", "October Revolution"), ("Treaty of Versailles", "Treaty of Versailles")])
    r["classes"] = ["war"]
    assert {(c["from"], c["to"]) for c in wm.sentence_candidates(r, q)} == {("Q3", "Q6"), ("Q3", "Q4")}


def test_tighter_subject_and_object():
    q = {"World War I": "Q3", "Bogotazo": "Q7", "Battle B": "Q8", "Battle A": "Q9"}
    # "which" points at something else, so the article is not the subject.
    r = row("The demonstration took place two months before the assassination, which triggered the Bogotazo.", "Q1",
            [("Bogotazo", "Bogotazo")])
    r["article"], r["classes"] = "March of Silence", ["demonstration"]
    assert [c["subject"] for c in wm.sentence_candidates(r, q)] == ["unclear"]
    # A named event joined by "and" is an object of the earlier verb, not the subject.
    r = row("The offensive included the Battle A and culminated in the Battle B.", "Q1",
            [("Battle A", "Battle A"), ("Battle B", "Battle B")])
    assert [c["subject"] for c in wm.sentence_candidates(r, q)] == ["unclear"]
    # The object must follow the phrase closely, not after "before".
    r = row("It ended in victory, leading to months of silence before the Battle B.", "Q1", [("Battle B", "Battle B")])
    assert wm.sentence_candidates(r, q) == []
    # Hyphenated forms are adjectives, not statements.
    r = row("It was a Gen Z-inspired vote after World War I.", "Q1", [("World War I", "World War I")])
    assert wm.sentence_candidates(r, q) == []
    # "in front of" is not "a front of".
    r = row("They stood in front of World War I memorials.", "Q1", [("World War I", "World War I")])
    assert wm.sentence_candidates(r, q) == []


def test_article_subject_modifiers_must_fit():
    assert not wm.article_is_subject("The Balkan Wars in 1912 were conflicts that ", "European theatre of World War I", ["war"])
    assert wm.article_is_subject("The 2021 coup ", "2021 Myanmar coup d'état", ["coup d'etat"])


def test_batches_and_scoring():
    base = {"type": "led_to", "date_ok": True, "hedged": False, "movement_only": False,
            "evidence": [{"cue": "led to", "subject": "article", "hedged": False}]}
    assert wm.batch(base) == "led_to"
    assert wm.batch(dict(base, date_ok=False)) is None
    assert wm.batch(dict(base, movement_only=True)) is None
    assert wm.batch(dict(base, evidence=[{"cue": "led to", "subject": "unclear", "hedged": False}])) is None
    ib = dict(base, type="part_of", evidence=[{"cue": "infobox: part of", "subject": "article", "hedged": False}])
    assert wm.batch(ib) == "part_of-infobox"
    named = dict(base, type="part_of", evidence=[{"cue": "part of", "subject": "named", "hedged": False}])
    assert wm.batch(named) is None
    lo, hi = wm.wilson(29, 30)
    assert 0.8 < lo < 0.85 and hi > 0.99
    out = wm.score_marks([("a", "correct")] * 19 + [("a", "wrong type"), ("b", "correct")], 0.95)
    assert out[0].startswith("a: 19/20 correct (95%") and "clears" in out[0] and "wrong type 1" in out[0]
