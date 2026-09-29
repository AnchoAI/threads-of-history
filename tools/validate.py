#!/usr/bin/env python3
"""Check every file under data/ against the schema and the project's rules.

    python tools/validate.py            # errors fail, warnings are summarized
    python tools/validate.py --verbose  # print every warning
    python tools/validate.py --strict   # warnings fail too

The JSON Schema (schema/threads-of-history.schema.json) checks the shape of
each file on its own. This script adds the rules that need the whole dataset:
ids resolve, dates are in order, causes come before effects, Wikidata ids are
not reused, CSV tables are well formed, and the requirements that go with each
review status.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "schema" / "threads-of-history.schema.json"

# data/<folder>/ -> schema definition
KIND_DIRS = {
    "events": "event",
    "signals": "signal",
    "decisions": "decision",
    "actors": "actor",
    "series": "series",
    "links": "link",
    "scenarios": "scenario",
    "paths": "path",
    "datasets": "dataset",
}
ITEM_KINDS = ("event", "signal", "decision", "actor", "series", "scenario")
VOCABS = ("domains", "threads", "regions")
TABLES_DIR = "tables"  # data/tables/*.csv, referenced by series items
TABLE_COLUMNS = ("entity", "at", "value")
ISO3 = re.compile(r"^[A-Z]{3}$")
DATE = re.compile(r"^-?[0-9]{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12][0-9]|3[01]))?)?$")
PRECISION_PARTS = {"century": 1, "decade": 1, "year": 1, "month": 2, "day": 3, "hour": 4}
NEEDS_SOURCING = "needs sourcing"


# ---------------------------------------------------------------- YAML loading


class _Loader(yaml.SafeLoader):
    """SafeLoader that keeps dates as strings and rejects duplicate keys."""


# Drop the timestamp resolver so 1962-10-22 stays the string "1962-10-22".
_Loader.yaml_implicit_resolvers = {
    ch: [(tag, rx) for tag, rx in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for ch, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def _mapping(loader: _Loader, node: yaml.MappingNode) -> dict:
    seen = set()
    for key_node, _ in node.value:
        key = loader.construct_object(key_node)
        if key in seen:
            raise yaml.constructor.ConstructorError(
                None, None, f"duplicate key {key!r}", key_node.start_mark
            )
        seen.add(key)
    return loader.construct_mapping(node, deep=True)


_Loader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _mapping)


def load_file(path: Path):
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        return json.loads(text)
    return yaml.load(text, Loader=_Loader)


# ---------------------------------------------------------------- dates


def date_parts(value: str) -> tuple[int, ...]:
    """'1962-10-22T19:00' -> (1962, 10, 22, 19, 0). Time zone is ignored."""
    neg = value.startswith("-")
    body = value[1:] if neg else value
    date, _, time = body.partition("T")
    parts = [int(p) for p in date.split("-")]
    if neg:
        parts[0] = -parts[0]
    if time:
        parts += [int(p) for p in re.split(r"[Z+-]", time)[0].split(":")]
    return tuple(parts)


def compare_dates(a: str, b: str) -> int:
    """Compare at the coarser of the two precisions. 1962-10 equals 1962-10-22."""
    pa, pb = date_parts(a), date_parts(b)
    n = min(len(pa), len(pb))
    pa, pb = pa[:n], pb[:n]
    return (pa > pb) - (pa < pb)


# ---------------------------------------------------------------- dataset


@dataclass
class Record:
    kind: str
    path: Path
    data: dict

    @property
    def id(self) -> str:
        return self.data.get("id", "")


@dataclass
class Dataset:
    root: Path
    records: list[Record] = field(default_factory=list)
    vocabs: dict[str, list[dict]] = field(default_factory=dict)
    tables: dict[str, Path] = field(default_factory=dict)  # "tables/x.csv" -> file

    def of_kind(self, *kinds: str) -> list[Record]:
        return [r for r in self.records if r.kind in kinds]

    @property
    def items(self) -> dict[str, Record]:
        return {r.id: r for r in self.of_kind(*ITEM_KINDS)}


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    root: Path = ROOT

    def _where(self, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return f"{path.relative_to(self.root)}: "
        except ValueError:
            return f"{path}: "

    def error(self, path: Path | None, msg: str) -> None:
        self.errors.append(self._where(path) + msg)

    def warn(self, path: Path | None, msg: str) -> None:
        self.warnings.append(self._where(path) + msg)


def load_dataset(data_dir: Path, report: Report) -> Dataset:
    ds = Dataset(root=data_dir)
    if not data_dir.is_dir():
        report.error(None, f"data folder not found: {data_dir}")
        return ds
    for entry in sorted(data_dir.iterdir()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir() and entry.name == TABLES_DIR:
            for f in sorted(entry.iterdir()):
                if f.name.startswith(".") or f.name == "README.md":
                    continue
                if f.suffix != ".csv":
                    report.error(f, "data/tables/ holds only .csv files")
                    continue
                ds.tables[f"{TABLES_DIR}/{f.name}"] = f
        elif entry.is_dir():
            if entry.name not in KIND_DIRS:
                report.error(entry, f"unknown folder; expected one of {', '.join(KIND_DIRS)}")
                continue
            for f in sorted(entry.iterdir()):
                if f.name.startswith(".") or f.name == "README.md":
                    continue
                if f.suffix not in (".yaml", ".yml", ".json"):
                    report.error(f, "data files must be .yaml, .yml or .json")
                    continue
                try:
                    data = load_file(f)
                except (yaml.YAMLError, json.JSONDecodeError) as exc:
                    report.error(f, f"could not parse: {exc}")
                    continue
                ds.records.append(Record(KIND_DIRS[entry.name], f, data))
        elif entry.stem in VOCABS and entry.suffix in (".yaml", ".yml", ".json"):
            try:
                ds.vocabs[entry.stem] = load_file(entry)
            except (yaml.YAMLError, json.JSONDecodeError) as exc:
                report.error(entry, f"could not parse: {exc}")
        elif entry.name != "README.md":
            report.error(entry, "unexpected file in data/")
    for v in VOCABS:
        if v not in ds.vocabs:
            report.error(None, f"missing data/{v}.yaml")
    return ds


# ---------------------------------------------------------------- checks


def check_schema(ds: Dataset, schema: dict, report: Report) -> set[int]:
    """Validate each file on its own. Returns ids() of records that failed."""
    defs = schema["$defs"]
    validators = {
        k: Draft202012Validator({"$ref": f"#/$defs/{k}", "$defs": defs})
        for k in (*ITEM_KINDS, "link", "path", "dataset", "vocabulary")
    }
    bad = set()
    for r in ds.records:
        errs = sorted(validators[r.kind].iter_errors(r.data), key=lambda e: list(e.absolute_path))
        for e in errs:
            where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
            msg = e.message
            if isinstance(e.instance, int) and e.validator == "type" and "string" in str(e.validator_value):
                msg += ' (quote dates in YAML, e.g. "1962")'
            report.error(r.path, f"{where}: {msg}")
        if errs:
            bad.add(id(r))
    for name, vocab in ds.vocabs.items():
        for e in validators["vocabulary"].iter_errors(vocab):
            where = "/".join(str(p) for p in e.absolute_path) or "(top level)"
            report.error(ds.root / f"{name}.yaml", f"{where}: {e.message}")
    return bad


def spans_of(data: dict):
    """Yield (label, span) for every time span in an item."""
    if "occurred" in data:
        yield "occurred", data["occurred"]
    if "window" in data:
        yield "window", data["window"]
    known = data.get("known") or {}
    if "public" in known:
        yield "known.public", known["public"]
    for i, k in enumerate(known.get("by", [])):
        yield f"known.by/{i}", k["when"]


def all_sources(data: dict):
    """Yield (label, source) for every source anywhere in a record."""
    for i, s in enumerate(data.get("sources", [])):
        yield f"sources/{i}", s
    for i, k in enumerate((data.get("known") or {}).get("by", [])):
        for j, s in enumerate(k.get("sources", [])):
            yield f"known.by/{i}/sources/{j}", s
    for i, a in enumerate(data.get("alternatives", [])):
        for j, s in enumerate(a.get("sources", [])):
            yield f"alternatives/{i}/sources/{j}", s
    for i, p in enumerate(data.get("positions", [])):
        for j, s in enumerate(p.get("sources", [])):
            yield f"positions/{i}/sources/{j}", s


def check_dates(r: Record, report: Report) -> None:
    for label, span in spans_of(r.data):
        need = PRECISION_PARTS[span["precision"]]
        for key in ("start", "end"):
            if key in span and len(date_parts(span[key])[:4]) < need:
                report.error(r.path, f"{label}.{key} {span[key]!r} is coarser than precision {span['precision']!r}")
        if "end" in span and compare_dates(span["end"], span["start"]) < 0:
            report.error(r.path, f"{label} ends ({span['end']}) before it starts ({span['start']})")
        if "end" in span and span.get("ongoing"):
            report.error(r.path, f"{label} has an end date but is marked ongoing")
    occ = r.data.get("occurred")
    pub = (r.data.get("known") or {}).get("public")
    if occ and pub and compare_dates(pub["start"], occ["start"]) < 0:
        report.warn(r.path, f"known.public ({pub['start']}) is before occurred ({occ['start']}); announced in advance?")


def check_ids_and_refs(ds: Dataset, report: Report) -> None:
    domains = {t["id"] for t in ds.vocabs.get("domains", []) if isinstance(t, dict)}
    threads = {t["id"] for t in ds.vocabs.get("threads", []) if isinstance(t, dict)}
    regions = {t["id"] for t in ds.vocabs.get("regions", []) if isinstance(t, dict)}
    for name, vocab in ds.vocabs.items():
        if not isinstance(vocab, list):
            continue
        ids = [t.get("id") for t in vocab if isinstance(t, dict)]
        for dup in {i for i in ids if ids.count(i) > 1}:
            report.error(ds.root / f"{name}.yaml", f"duplicate id {dup!r}")
        for t in vocab:
            if not isinstance(t, dict):
                continue
            if name == "threads" and t.get("domain") not in domains:
                report.error(ds.root / "threads.yaml", f"thread {t.get('id')!r} needs a domain from data/domains.yaml")
            if name != "threads" and "domain" in t:
                report.error(ds.root / f"{name}.yaml", f"{t.get('id')!r}: only threads have a domain")

    seen: dict[tuple[str, str], Record] = {}
    for r in ds.records:
        if r.id != r.path.stem:
            report.error(r.path, f"id {r.id!r} must match the file name {r.path.stem!r}")
        ns = "item" if r.kind in ITEM_KINDS else r.kind
        if (ns, r.id) in seen:
            report.error(r.path, f"id {r.id!r} is already used by {seen[(ns, r.id)].path.relative_to(ds.root)}")
        seen[(ns, r.id)] = r

    items = ds.items
    actors = {i for i, r in items.items() if r.kind == "actor"}
    datasets = {r.id: r for r in ds.of_kind("dataset")}
    check_wikidata(ds, report)
    for r in ds.of_kind(*ITEM_KINDS):
        d = r.data
        for t in d.get("threads", []):
            if t not in threads:
                report.error(r.path, f"unknown thread {t!r} (add it to data/threads.yaml)")
        for g in d.get("regions", []):
            if g not in regions:
                report.error(r.path, f"unknown region {g!r} (add it to data/regions.yaml)")
        refs = [("actors", a) for a in d.get("actors", [])]
        refs += [("decided_by", a) for a in d.get("decided_by", [])]
        refs += [("known.by.actor", k["actor"]) for k in (d.get("known") or {}).get("by", []) if "actor" in k]
        for label, a in refs:
            if a not in actors:
                report.error(r.path, f"{label}: {a!r} is not an actor in data/actors/")
        if r.kind == "actor" and r.id in d.get("actors", []):
            report.error(r.path, "an actor cannot list itself in actors")
        if "resolves_to" in d:
            target = items.get(d["resolves_to"])
            if not target or target.kind != "event":
                report.error(r.path, f"resolves_to {d['resolves_to']!r} is not an event")
        if r.kind == "series":
            check_series(r, actors, datasets, ds, report)
        if r.kind == "scenario":
            check_scenario(r, items, report)

    for r in ds.of_kind("path"):
        for step in r.data["steps"]:
            if step not in items:
                report.error(r.path, f"step {step!r} is not an item")

    referenced = {r.data["table"] for r in ds.of_kind("series") if "table" in r.data}
    for rel, path in ds.tables.items():
        if rel not in referenced:
            report.warn(path, "no series item uses this table")


def check_wikidata(ds: Dataset, report: Report) -> None:
    """Wikidata ids are unique; likely duplicates without one get a warning."""
    by_qid: dict[str, Record] = {}
    by_title: dict[tuple[str, str], Record] = {}
    for r in ds.of_kind(*ITEM_KINDS):
        qid = r.data.get("wikidata")
        if qid and qid != "none":
            if qid in by_qid:
                report.error(r.path, f"wikidata {qid} is already used by {by_qid[qid].path.relative_to(ds.root)}; merge the two")
            by_qid[qid] = r
        elif not qid and r.kind in ("event", "actor"):
            report.warn(r.path, 'no wikidata id (add one, or "none" if Wikidata has no matching item)')
        occ = r.data.get("occurred")
        if r.kind == "event" and occ:
            key = (re.sub(r"[^a-z0-9]", "", r.data["title"].lower()), occ["start"][:4].lstrip("-"))
            if key in by_title:
                report.warn(r.path, f"same title and year as {by_title[key].path.relative_to(ds.root)}; is it a duplicate?")
            by_title[key] = r
    iso: dict[str, Record] = {}
    for r in ds.of_kind("actor"):
        code = r.data.get("iso3")
        if code and code in iso:
            report.error(r.path, f"iso3 {code} is already used by {iso[code].path.relative_to(ds.root)}")
        if code:
            iso[code] = r


def check_series(r: Record, actors: set[str], datasets: dict[str, Record], ds: Dataset, report: Report) -> None:
    d = r.data
    if "entity" in d and d["entity"] not in actors:
        report.error(r.path, f"entity {d['entity']!r} is not an actor")
    if "dataset" in d:
        dset = datasets.get(d["dataset"])
        if not dset:
            report.error(r.path, f"dataset {d['dataset']!r} is not registered in data/datasets/")
        elif dset.data["license"]["redistribution"] == "restricted":
            report.error(r.path, f"dataset {d['dataset']!r} does not allow redistribution")
        elif dset.data["license"]["redistribution"] == "unknown":
            report.warn(r.path, f"dataset {d['dataset']!r} has not had its licence checked")
    if "points" in d:
        pts = d["points"]
        for a, b in zip(pts, pts[1:]):
            if compare_dates(b["at"], a["at"]) <= 0:
                report.error(r.path, f"points must be in date order and not repeat ({a['at']} then {b['at']})")
        for p in pts:
            if "source" in p and p["source"] >= len(d["sources"]):
                report.error(r.path, f"point at {p['at']} cites sources[{p['source']}], which does not exist")
    if "table" in d:
        if "dataset" not in d:
            report.error(r.path, "a series with a table must name its dataset")
        if "entity" in d:
            report.error(r.path, "entity is for inline points; a table names entities in its rows")
        path = ds.tables.get(d["table"])
        if not path:
            report.error(r.path, f"table {d['table']!r} not found in data/tables/")
        else:
            check_table(path, report)


def read_table(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), list(reader)


def check_table(path: Path, report: Report) -> None:
    """A table is a long CSV: entity,at,value[,published]. One row per entity and date."""
    header, rows = read_table(path)
    if tuple(header[:3]) != TABLE_COLUMNS or not set(header[3:]) <= {"published"}:
        report.error(path, "columns must be entity,at,value and optionally published")
        return
    seen = set()
    for n, row in enumerate(rows, start=2):
        problems = []
        if not ISO3.match(row["entity"] or ""):
            problems.append(f"entity {row['entity']!r} is not an ISO3 code")
        if not DATE.match(row["at"] or ""):
            problems.append(f"at {row['at']!r} is not a date")
        try:
            float(row["value"])
        except (TypeError, ValueError):
            problems.append(f"value {row['value']!r} is not a number")
        if row.get("published") and not DATE.match(row["published"]):
            problems.append(f"published {row['published']!r} is not a date")
        if (row["entity"], row["at"]) in seen:
            problems.append(f"repeats {row['entity']} {row['at']}")
        seen.add((row["entity"], row["at"]))
        for p in problems:
            report.error(path, f"line {n}: {p}")
        if len(report.errors) > 200:
            report.error(path, "too many errors; stopping")
            return


def check_scenario(r: Record, items: dict[str, Record], report: Report) -> None:
    d = r.data
    for g in d.get("given", []):
        target = items.get(g)
        if not target or target.kind != "scenario":
            report.error(r.path, f"given {g!r} is not a scenario")
    if compare_dates(d["resolves_by"], d["forecast_on"]) < 0:
        report.error(r.path, "resolves_by is before forecast_on")
    res = d["resolution"]
    if res["outcome"] != "open" and "resolved_on" not in res:
        report.error(r.path, "a resolved scenario needs resolution.resolved_on")
    if "event" in res:
        target = items.get(res["event"])
        if not target or target.kind != "event":
            report.error(r.path, f"resolution.event {res['event']!r} is not an event")
    if res["outcome"] == "happened" and "event" not in res:
        report.warn(r.path, "happened, but resolution.event does not name the event that records it")


def check_scenario_loops(ds: Dataset, report: Report) -> None:
    given = {r.id: r.data.get("given", []) for r in ds.of_kind("scenario")}

    def visit(node: str, trail: list[str]) -> bool:
        for parent in given.get(node, []):
            if parent in trail:
                report.error(None, "scenarios depend on each other in a loop: " + " -> ".join(trail[trail.index(parent):] + [parent]))
                return True
            if visit(parent, trail + [parent]):
                return True
        return False

    for start in given:
        if visit(start, [start]):
            return


def check_links(ds: Dataset, report: Report) -> None:
    items = ds.items
    pairs: set[tuple[str, str, str]] = set()
    part_of: dict[str, list[str]] = {}
    for r in ds.of_kind("link"):
        d = r.data
        a, b, t = d["from"], d["to"], d["type"]
        expected = f"{a}--{t}--{b}"
        if d["id"] != expected:
            report.error(r.path, f"link id must be {expected!r}")
        if a == b:
            report.error(r.path, "a link cannot point to itself")
        missing = [x for x in (a, b) if x not in items]
        for x in missing:
            report.error(r.path, f"{x!r} is not an item")
        if missing:
            continue
        ra, rb = items[a], items[b]
        if "scenario" in (ra.kind, rb.kind):
            report.error(r.path, "scenarios cannot be linked; use `given` between scenarios, and resolution.event once one happens")
            continue
        if (a, b, t) in pairs:
            report.error(r.path, "duplicate link")
        pairs.add((a, b, t))
        oa, ob = ra.data.get("occurred"), rb.data.get("occurred")
        if t == "signal_of":
            if ra.kind != "signal":
                report.error(r.path, f"signal_of must start at a signal; {a!r} is a {ra.kind}")
        if t == "part_of":
            part_of.setdefault(a, []).append(b)
        if t in ("led_to", "revealed") and "actor" in (ra.kind, rb.kind):
            report.error(r.path, f"{t} links connect events, signals and decisions, not actors")
        if not (oa and ob):
            continue
        if t == "led_to" and compare_dates(oa["start"], ob["start"]) > 0:
            report.error(r.path, f"cause {a!r} ({oa['start']}) starts after its effect {b!r} ({ob['start']})")
        if t == "revealed" and compare_dates(oa["start"], ob["start"]) < 0:
            report.error(r.path, f"revealed points back in time, but {a!r} ({oa['start']}) is before {b!r} ({ob['start']})")
        if t == "part_of" and compare_dates(oa["start"], ob["start"]) < 0:
            report.warn(r.path, f"sub-event {a!r} starts before the event it is part of")

    # part_of must be a tree, never a loop
    def visit(node: str, trail: list[str]) -> None:
        for parent in part_of.get(node, []):
            if parent in trail:
                loop = " -> ".join(trail[trail.index(parent):] + [parent])
                report.error(None, f"part_of links form a loop: {loop}")
                return
            visit(parent, trail + [parent])

    for start in part_of:
        visit(start, [start])


def check_review(ds: Dataset, report: Report) -> dict[str, dict[str, int]]:
    """Apply the requirements of each review status. Returns counts by kind."""
    counts: dict[str, dict[str, int]] = {}
    for r in ds.of_kind(*ITEM_KINDS, "link"):
        d = r.data
        status = d["review"]["status"]
        counts.setdefault(r.kind, {}).setdefault(status, 0)
        counts[r.kind][status] += 1
        sources = list(all_sources(d))

        if r.kind == "link" and not d["sources"]:
            report.error(r.path, "every link needs at least one source")  # schema also enforces
        if status == "unverified":
            if not d["sources"] and r.kind != "scenario":
                report.warn(r.path, "unverified and has no sources yet")
            continue

        # sourced and reviewed
        if not d["sources"]:
            report.error(r.path, f"status {status!r} needs at least one source")
        for label, s in sources:
            if "quote" not in s:
                report.error(r.path, f"{label}: status {status!r} needs a quote showing the source makes the claim")
        for i, p in enumerate(d.get("positions", [])):
            if not p["sources"]:
                report.error(r.path, f"positions/{i}: status {status!r} needs a source for each position")
            if any(NEEDS_SOURCING in h.lower() for h in p["held_by"]):
                report.error(r.path, f"positions/{i}: held_by still says {NEEDS_SOURCING!r}")

        if status == "sourced":
            for label, s in sources:
                if "archive_url" not in s:
                    report.warn(r.path, f"{label}: no archive_url yet")
            continue

        # reviewed
        if "reviewed_by" not in d["review"]:
            report.error(r.path, "status 'reviewed' needs review.reviewed_by")
        for label, s in sources:
            for key in ("archive_url", "publisher", "date"):
                if key not in s:
                    report.error(r.path, f"{label}: status 'reviewed' needs {key}")
    for r in ds.of_kind("dataset"):
        importer = r.data.get("importer")
        if importer and not (ds.root.parent / importer).exists():
            report.warn(r.path, f"importer {importer} does not exist yet")
        status = r.data["review"]["status"]
        counts.setdefault("dataset", {}).setdefault(status, 0)
        counts["dataset"][status] += 1
        if status != "unverified" and r.data["license"]["redistribution"] == "unknown":
            report.error(r.path, f"status {status!r} needs the licence checked (redistribution is still 'unknown')")
        if status == "reviewed" and "url" not in r.data["license"]:
            report.error(r.path, "status 'reviewed' needs license.url")
    return counts


# ---------------------------------------------------------------- entry points


def validate(data_dir: Path = ROOT / "data", schema_path: Path = SCHEMA_PATH) -> tuple[Dataset, Report, dict]:
    report = Report(root=data_dir.parent)
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    ds = load_dataset(data_dir, report)
    bad = check_schema(ds, schema, report)
    # The cross-file checks assume each file has the right shape.
    ds.records = [r for r in ds.records if id(r) not in bad]
    for r in ds.of_kind(*ITEM_KINDS):
        check_dates(r, report)
    check_ids_and_refs(ds, report)
    check_scenario_loops(ds, report)
    check_links(ds, report)
    counts = check_review(ds, report)
    return ds, report, counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data", help="data folder (default: data/)")
    ap.add_argument("--strict", action="store_true", help="treat warnings as errors")
    ap.add_argument("--verbose", "-v", action="store_true", help="print every warning")
    args = ap.parse_args(argv)

    ds, report, counts = validate(args.data)

    for e in report.errors:
        print(f"ERROR   {e}")
    if args.verbose or args.strict:
        for w in report.warnings:
            print(f"WARNING {w}")

    print()
    for kind in (*ITEM_KINDS, "link", "dataset"):
        if kind in counts:
            c = counts[kind]
            detail = ", ".join(f"{c[s]} {s}" for s in ("reviewed", "sourced", "unverified") if c.get(s))
            print(f"{kind + 's':<10} {sum(c.values()):>4}  ({detail})")
    print(f"{'paths':<10} {len(ds.of_kind('path')):>4}")
    print()
    hidden = "" if args.verbose or args.strict else " (use --verbose to list them)"
    print(f"{len(report.errors)} error(s), {len(report.warnings)} warning(s){hidden}")

    if report.errors or (args.strict and report.warnings):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
