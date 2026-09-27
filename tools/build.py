#!/usr/bin/env python3
"""Compile data/ into one dist/graph.json for the viewer.

    python tools/build.py              # writes dist/graph.json
    python tools/build.py --out x.json

The build runs the validator first and stops if there are errors. The output
is deterministic (sorted, no timestamps), so rebuilding unchanged data gives
an identical file.

Added for the viewer's convenience:
- every item gets `kind`;
- `known.public` defaults to `occurred` when not given;
- every time span gets `range: [start, end]` in decimal years, where end is
  the end of the last period the span covers (1962-10 -> 1962.75..1962.833),
  or null when the span is ongoing.
"""
from __future__ import annotations

import argparse
import calendar
import copy
import json
import sys
from pathlib import Path

from validate import ITEM_KINDS, ROOT, date_parts, validate

FORMAT_VERSION = 1


def _decimal(parts: tuple[int, ...]) -> float:
    y = parts[0]
    m = parts[1] if len(parts) > 1 else 1
    d = parts[2] if len(parts) > 2 else 1
    h = parts[3] if len(parts) > 3 else 0
    mi = parts[4] if len(parts) > 4 else 0
    days = 366 if calendar.isleap(y) else 365
    doy = sum(calendar.monthrange(y, i)[1] for i in range(1, m)) + d - 1
    return y + (doy + (h + mi / 60) / 24) / days


def start_year(value: str) -> float:
    return round(_decimal(date_parts(value)), 5)


def end_year(value: str, precision: str) -> float:
    """Decimal year at the end of the period `value` names."""
    p = date_parts(value)
    y = p[0]
    if precision == "century" or (precision == "decade" and len(p) == 1):
        width = 100 if precision == "century" else 10
        return float(y - y % width + width)
    if len(p) == 1:
        return float(y + 1)
    if len(p) == 2:
        return round(_decimal((y + 1, 1)) if p[1] == 12 else _decimal((y, p[1] + 1)), 5)
    if len(p) == 3:
        return round(_decimal(p) + 1 / (366 if calendar.isleap(y) else 365), 5)
    return round(_decimal(p) + 1 / 24 / (366 if calendar.isleap(y) else 365), 5)


def with_range(span: dict) -> dict:
    span = dict(span)
    start = start_year(span["start"])
    if span.get("ongoing"):
        end = None
    else:
        end = end_year(span.get("end", span["start"]), span["precision"])
    if span["precision"] in ("century", "decade") and "end" not in span:
        width = 100 if span["precision"] == "century" else 10
        y = date_parts(span["start"])[0]
        start = float(y - y % width)
    span["range"] = [start, end]
    return span


def compile_graph(data_dir: Path = ROOT / "data") -> tuple[dict | None, list[str]]:
    ds, report, counts = validate(data_dir)
    if report.errors:
        return None, report.errors

    items = []
    for r in ds.of_kind(*ITEM_KINDS):
        d = copy.deepcopy(r.data)
        out = {"kind": r.kind, **d}
        if "occurred" in d:
            out["occurred"] = with_range(d["occurred"])
            known = d.get("known") or {}
            out["known"] = {**known, "public": with_range(known.get("public", d["occurred"]))}
            if "by" in known:
                out["known"]["by"] = [{**k, "when": with_range(k["when"])} for k in known["by"]]
        items.append(out)

    def sort_key(item: dict):
        occ = item.get("occurred")
        return (occ is None, occ["range"][0] if occ else 0, item["id"])

    items.sort(key=sort_key)
    links = sorted((copy.deepcopy(r.data) for r in ds.of_kind("link")), key=lambda d: d["id"])
    paths = sorted((copy.deepcopy(r.data) for r in ds.of_kind("path")), key=lambda d: d["id"])

    graph = {
        "format_version": FORMAT_VERSION,
        "threads": ds.vocabs["threads"],
        "regions": ds.vocabs["regions"],
        "items": items,
        "links": links,
        "paths": paths,
        "stats": {k: dict(sorted(v.items())) for k, v in sorted(counts.items())},
    }
    return graph, []


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", type=Path, default=ROOT / "data")
    ap.add_argument("--out", type=Path, default=ROOT / "dist" / "graph.json")
    args = ap.parse_args(argv)

    graph, errors = compile_graph(args.data)
    if graph is None:
        for e in errors:
            print(f"ERROR   {e}")
        print(f"\nBuild stopped: {len(errors)} validation error(s). Run tools/validate.py for details.")
        return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(graph, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    n_items = len(graph["items"])
    print(f"Wrote {args.out} ({n_items} items, {len(graph['links'])} links, {len(graph['paths'])} paths)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
