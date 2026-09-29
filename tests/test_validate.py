"""Tests for tools/validate.py and tools/build.py.

Each test writes a small data/ folder into a temp directory, so the rules can
be checked without touching the real dataset.
"""
import copy
import json
from pathlib import Path

import pytest
import yaml

import build
import validate

ROOT = Path(__file__).resolve().parent.parent

SRC = {"url": "https://example.org/a", "title": "A source", "type": "news"}
FULL_SRC = {**SRC, "archive_url": "https://web.archive.org/web/2024/https://example.org/a",
            "publisher": "Example", "date": "2022-02-11", "quote": "The example says so."}


def event(id_, start, **extra):
    return {"id": id_, "title": id_, "summary": "Something happened.",
            "occurred": {"start": start, "precision": "month"},
            "threads": ["ukraine"], "regions": ["europe"], "importance": 3,
            "sources": [SRC], "review": {"status": "unverified"}, **extra}


def link(a, t, b, **extra):
    return {"id": f"{a}--{t}--{b}", "from": a, "to": b, "type": t, "confidence": "documented",
            "note": "A note.", "sources": [SRC], "review": {"status": "unverified"}, **extra}


BASE = {
    "events": [event("buildup-2021", "2021-03"), event("invasion-2022", "2022-02")],
    "signals": [{
        "id": "satellite-imagery-2021", "title": "Satellite imagery of a buildup", "summary": "Images show troops.",
        "occurred": {"start": "2021-11-01", "precision": "day"},
        "known": {"public": {"start": "2021-11-02", "precision": "day"}},
        "threads": ["ukraine"], "regions": ["europe"], "importance": 2, "sources": [SRC],
        "review": {"status": "unverified"},
        "source_credibility": "high", "outcome": "confirmed", "resolves_to": "invasion-2022",
    }],
    "decisions": [{
        "id": "appointment-1933", "title": "Hindenburg appoints Hitler", "summary": "A choice.",
        "occurred": {"start": "1933-01-30", "precision": "day"},
        "threads": ["ukraine"], "regions": ["europe"], "importance": 4, "sources": [SRC],
        "review": {"status": "unverified"},
        "decided_by": ["hindenburg"], "alternatives": [{"option": "Keep Schleicher"}],
    }],
    "actors": [{
        "id": "hindenburg", "title": "Paul von Hindenburg", "actor_type": "person", "summary": "A person.",
        "occurred": {"start": "1847", "end": "1934", "precision": "year"},
        "threads": [], "regions": ["europe"], "importance": 3, "sources": [SRC],
        "review": {"status": "unverified"},
    }],
    "series": [{
        "id": "unemployment-germany", "title": "Unemployment", "summary": "Numbers.",
        "occurred": {"start": "1928", "end": "1934", "precision": "year"},
        "threads": ["ukraine"], "regions": ["europe"], "importance": 3, "sources": [SRC],
        "review": {"status": "unverified"}, "unit": "percent",
        "points": [{"at": "1928", "value": 7.0}, {"at": "1932", "value": 30.1, "source": 0}],
    }],
    "links": [
        link("buildup-2021", "led_to", "invasion-2022"),
        link("satellite-imagery-2021", "signal_of", "invasion-2022"),
    ],
    "scenarios": [{
        "id": "ceasefire-2027", "title": "Ceasefire agreed", "summary": "A possible ceasefire.",
        "window": {"start": "2027", "precision": "year"}, "probability": 0.3,
        "forecast_by": "Example forecaster", "forecast_on": "2026-09-01", "resolves_by": "2027-12-31",
        "resolution": {"outcome": "open"},
        "threads": ["ukraine"], "regions": ["europe"], "importance": 3, "sources": [],
        "review": {"status": "unverified"},
    }, {
        "id": "elections-2028", "title": "Elections held", "summary": "Depends on the ceasefire.",
        "window": {"start": "2028", "precision": "year"}, "probability": 0.6, "given": ["ceasefire-2027"],
        "forecast_by": "Example forecaster", "forecast_on": "2026-09-01", "resolves_by": "2028-12-31",
        "resolution": {"outcome": "open"},
        "threads": ["ukraine"], "regions": ["europe"], "importance": 2, "sources": [],
        "review": {"status": "unverified"},
    }],
    "datasets": [{
        "id": "example-data", "title": "Example data", "publisher": "Example", "url": "https://example.org/data",
        "version": "1", "license": {"name": "CC BY 4.0", "redistribution": "allowed"}, "citation": "Example (2024).",
        "unit_of_analysis": "country-year", "coverage": {"start": "1900", "end": "2020", "precision": "year"},
        "review": {"status": "unverified"},
    }],
    "paths": [{"id": "tour", "title": "Tour", "steps": ["buildup-2021", "invasion-2022"]}],
}
TABLE = "entity,at,value\nDEU,1928,7.0\nDEU,1932,30.1\nFRA,1932,4.5\n"
TABLE_SERIES = {
    "id": "gdp-example", "title": "GDP per person", "summary": "Numbers.",
    "occurred": {"start": "1928", "end": "1932", "precision": "year"},
    "threads": ["ukraine"], "regions": ["europe"], "importance": 3, "sources": [SRC],
    "review": {"status": "unverified"}, "unit": "USD", "dataset": "example-data",
    "indicator": "gdppc", "table": "tables/gdp-example.csv",
}


def write(tmp_path: Path, data: dict) -> Path:
    d = tmp_path / "data"
    d.mkdir()
    (d / "domains.yaml").write_text(yaml.safe_dump([{"id": "politics", "name": "Politics"}]))
    (d / "threads.yaml").write_text(yaml.safe_dump([{"id": "ukraine", "name": "Ukraine", "domain": "politics"}]))
    (d / "regions.yaml").write_text(yaml.safe_dump([{"id": "europe", "name": "Europe"}]))
    for folder, records in data.items():
        (d / folder).mkdir()
        for r in records:
            if folder == "tables":
                (d / folder / r["name"]).write_text(r["text"])
            else:
                (d / folder / f"{r['id']}.yaml").write_text(yaml.safe_dump(r, sort_keys=False))
    return d


def with_table(data, text=TABLE, series=None):
    data["tables"] = [{"name": "gdp-example.csv", "text": text}]
    data["series"].append(series or copy.deepcopy(TABLE_SERIES))
    return data


def run(tmp_path, data):
    _, report, _ = validate.validate(write(tmp_path, data))
    return report


def with_changes(fn):
    data = copy.deepcopy(BASE)
    fn(data)
    return data


def assert_error(report, text):
    assert any(text in e for e in report.errors), f"expected an error containing {text!r}, got {report.errors}"


# ------------------------------------------------------------------ happy paths


def test_real_dataset_is_valid():
    _, report, _ = validate.validate(ROOT / "data")
    assert report.errors == []


def test_all_kinds_valid(tmp_path):
    report = run(tmp_path, BASE)
    assert report.errors == []


def test_build_is_deterministic_and_fills_defaults(tmp_path):
    d = write(tmp_path, BASE)
    g1, errs, _ = build.compile_graph(d)
    g2, _, _ = build.compile_graph(d)
    assert errs == [] and json.dumps(g1) == json.dumps(g2)
    items = {i["id"]: i for i in g1["items"]}
    inv = items["invasion-2022"]
    assert inv["kind"] == "event"
    assert inv["known"]["public"]["start"] == "2022-02"  # defaulted from occurred
    start, end = inv["occurred"]["range"]
    assert 2022.08 < start < end < 2022.17
    assert items["hindenburg"]["occurred"]["range"] == [1847.0, 1935.0]


def test_build_refuses_invalid_data(tmp_path):
    data = with_changes(lambda d: d["links"].append(link("invasion-2022", "led_to", "nowhere")))
    graph, errs, _ = build.compile_graph(write(tmp_path, data))
    assert graph is None and errs


def test_bare_year_date_gets_a_hint(tmp_path):
    d = write(tmp_path, BASE)
    f = d / "events" / "buildup-2021.yaml"
    f.write_text(f.read_text().replace("start: 2021-03", "start: 2021"))
    _, report, _ = validate.validate(d)
    assert_error(report, 'quote dates in YAML')


def test_full_dates_stay_strings(tmp_path):
    d = write(tmp_path, BASE)
    loaded = validate.load_file(d / "signals" / "satellite-imagery-2021.yaml")
    assert loaded["occurred"]["start"] == "2021-11-01"


# ------------------------------------------------------------------ rule violations


@pytest.mark.parametrize("change, message", [
    (lambda d: d["events"][0].update(threads=["nope"]), "unknown thread"),
    (lambda d: d["events"][0].update(actors=["nobody"]), "is not an actor"),
    (lambda d: d["events"][0].update(occurred={"start": "2021", "precision": "day"}), "coarser than precision"),
    (lambda d: d["events"][0].update(occurred={"start": "2021-03", "end": "2020-01", "precision": "month"}), "ends"),
    (lambda d: d["events"][0].update(importance=9), "importance"),
    (lambda d: d["events"][0].pop("summary"), "'summary' is a required property"),
    (lambda d: d["events"][0].update(colour="red"), "colour"),
    (lambda d: d["signals"][0].update(resolves_to="hindenburg"), "resolves_to"),
    (lambda d: d["decisions"][0].update(decided_by=["buildup-2021"]), "is not an actor"),
    (lambda d: d["series"][0]["points"].reverse(), "date order"),
    (lambda d: d["series"][0]["points"][1].update(source=5), "does not exist"),
    (lambda d: d["paths"][0]["steps"].append("missing"), "is not an item"),
    (lambda d: d["links"].append(link("invasion-2022", "led_to", "buildup-2021")), "starts after its effect"),
    (lambda d: d["links"].append(link("buildup-2021", "revealed", "invasion-2022")), "points back in time"),
    (lambda d: d["links"].append(link("buildup-2021", "signal_of", "invasion-2022")), "must start at a signal"),
    (lambda d: d["links"].append(link("buildup-2021", "led_to", "buildup-2021")), "cannot point to itself"),
    (lambda d: d["links"].append(link("buildup-2021", "led_to", "ghost")), "'ghost' is not an item"),
    (lambda d: d["links"].append({**link("buildup-2021", "echo", "invasion-2022"), "sources": []}), "should be non-empty"),
    (lambda d: d["links"].append({**link("buildup-2021", "echo", "invasion-2022"), "confidence": "contested"}),
     "'positions' is a required property"),
    (lambda d: d["links"].extend([link("buildup-2021", "part_of", "invasion-2022"),
                                  link("invasion-2022", "part_of", "buildup-2021")]), "form a loop"),
    # Wikidata ids
    (lambda d: [e.update(wikidata="Q1") for e in d["events"]], "already used by"),
    (lambda d: d["events"][0].update(wikidata="1234"), "wikidata"),
    # scenarios
    (lambda d: d["scenarios"][0].update(probability=1.5), "probability"),
    (lambda d: d["scenarios"][1].update(given=["invasion-2022"]), "is not a scenario"),
    (lambda d: d["scenarios"][0].update(given=["elections-2028"]), "in a loop"),
    (lambda d: d["scenarios"][0].update(resolves_by="2020-01-01"), "resolves_by is before"),
    (lambda d: d["scenarios"][0].update(resolution={"outcome": "happened"}), "needs resolution.resolved_on"),
    (lambda d: d["links"].append(link("invasion-2022", "led_to", "ceasefire-2027")), "scenarios cannot be linked"),
    # series and datasets
    (lambda d: d["series"][0].update(entity="nobody"), "is not an actor"),
    (lambda d: d["series"][0].pop("points"), "is not valid under any of the given schemas"),
    (lambda d: with_table(d, series={**TABLE_SERIES, "dataset": "missing"}), "is not registered"),
    (lambda d: with_table(d, series={k: v for k, v in TABLE_SERIES.items() if k != "dataset"}), "must name its dataset"),
    (lambda d: with_table(d, series={**TABLE_SERIES, "table": "tables/other.csv"}), "not found in data/tables/"),
    (lambda d: with_table(d, text="country,year,value\nDEU,1928,1\n"), "columns must be"),
    (lambda d: with_table(d, text="entity,at,value\nGermany,1928,x\n"), "is not an ISO3 code"),
    (lambda d: with_table(d, text="entity,at,value\nDEU,1928,x\n"), "is not a number"),
    (lambda d: with_table(d, text="entity,at,value\nDEU,1928,1\nDEU,1928,2\n"), "repeats DEU 1928"),
    (lambda d: with_table(d) and d["datasets"][0]["license"].update(redistribution="restricted"),
     "does not allow redistribution"),
    (lambda d: d["datasets"][0].update(review={"status": "sourced"}) or
     d["datasets"][0]["license"].update(redistribution="unknown"), "needs the licence checked"),
    (lambda d: d["actors"].append({**d["actors"][0], "id": "other"}) or
     [a.update(iso3="DEU") for a in d["actors"]], "iso3 DEU is already used"),
])
def test_rule(tmp_path, change, message):
    assert_error(run(tmp_path, with_changes(change)), message)


def test_id_must_match_file_name(tmp_path):
    d = write(tmp_path, BASE)
    (d / "events" / "buildup-2021.yaml").rename(d / "events" / "other-name.yaml")
    _, report, _ = validate.validate(d)
    assert_error(report, "must match the file name")


def test_duplicate_yaml_key(tmp_path):
    d = write(tmp_path, BASE)
    f = d / "events" / "buildup-2021.yaml"
    f.write_text(f.read_text() + "importance: 2\n")
    _, report, _ = validate.validate(d)
    assert_error(report, "duplicate key")


# ------------------------------------------------------------------ review status


def test_sourced_needs_quotes(tmp_path):
    report = run(tmp_path, with_changes(lambda d: d["events"][0].update(review={"status": "sourced"})))
    assert_error(report, "needs a quote")


def test_sourced_with_quote_only_warns_about_archive(tmp_path):
    src = {**SRC, "quote": "It says so."}
    report = run(tmp_path, with_changes(lambda d: d["events"][0].update(review={"status": "sourced"}, sources=[src])))
    assert report.errors == []
    assert any("archive_url" in w for w in report.warnings)


def test_reviewed_needs_everything(tmp_path):
    report = run(tmp_path, with_changes(lambda d: d["events"][0].update(
        review={"status": "reviewed"}, sources=[{**SRC, "quote": "It says so."}])))
    assert_error(report, "needs review.reviewed_by")
    assert_error(report, "needs archive_url")


def test_reviewed_complete_passes(tmp_path):
    report = run(tmp_path, with_changes(lambda d: d["events"][0].update(
        review={"status": "reviewed", "reviewed_by": "michael"}, sources=[FULL_SRC])))
    assert report.errors == []


def test_contested_positions_need_sources_once_sourced(tmp_path):
    contested = {**link("buildup-2021", "echo", "invasion-2022"), "confidence": "contested",
                 "sources": [{**SRC, "quote": "q"}], "review": {"status": "sourced"},
                 "positions": [{"claim": "Yes", "held_by": ["A"], "sources": []},
                               {"claim": "No", "held_by": ["(needs sourcing)"], "sources": []}]}
    report = run(tmp_path, with_changes(lambda d: d["links"].append(contested)))
    assert_error(report, "needs a source for each position")
    assert_error(report, "held_by still says")


# ------------------------------------------------------------------ domains, wikidata, tables


def test_thread_needs_domain(tmp_path):
    d = write(tmp_path, BASE)
    (d / "threads.yaml").write_text(yaml.safe_dump([{"id": "ukraine", "name": "Ukraine"}]))
    _, report, _ = validate.validate(d)
    assert_error(report, "needs a domain")


def test_missing_wikidata_and_likely_duplicates_warn(tmp_path):
    data = with_changes(lambda d: d["events"].append({**event("buildup-2021-copy", "2021-05"), "title": "buildup-2021"}))
    report = run(tmp_path, data)
    assert report.errors == []
    assert any("no wikidata id" in w for w in report.warnings)
    assert any("same title and year" in w for w in report.warnings)


def test_wikidata_none_is_allowed(tmp_path):
    report = run(tmp_path, with_changes(lambda d: d["events"][0].update(wikidata="none")))
    assert report.errors == []


def test_table_series_builds_to_json(tmp_path):
    d = write(tmp_path, with_table(copy.deepcopy(BASE)))
    graph, errs, tables = build.compile_graph(d)
    assert errs == []
    item = next(i for i in graph["items"] if i["id"] == "gdp-example")
    assert item["table_json"] == "series/gdp-example.json"
    assert item["domains"] == ["politics"]
    assert tables["gdp-example"] == {"DEU": [["1928", 7.0], ["1932", 30.1]], "FRA": [["1932", 4.5]]}
    scen = next(i for i in graph["items"] if i["id"] == "ceasefire-2027")
    assert scen["window"]["range"] == [2027.0, 2028.0]


def test_unused_table_warns(tmp_path):
    data = copy.deepcopy(BASE)
    data["tables"] = [{"name": "orphan.csv", "text": TABLE}]
    report = run(tmp_path, data)
    assert report.errors == []
    assert any("no series item uses this table" in w for w in report.warnings)


def test_importer_helper_writes_clean_sorted_table(tmp_path, monkeypatch):
    from importers import common
    monkeypatch.setattr(common, "DATA", tmp_path)
    path = common.write_table("demo", [("FRA", "1932", 4.5), ("DEU", "1932", 30.1),
                                       ("DEU", "1928", 7.0), ("DEU", "1930", float("nan"))])
    assert path.read_text() == "entity,at,value\nDEU,1928,7\nDEU,1932,30.1\nFRA,1932,4.5\n"
    with pytest.raises(ValueError):
        common.write_table("bad", [("Germany", "1928", 1.0)])
