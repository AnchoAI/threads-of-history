"""Propose `importance` values (1-5) for timeline items, so they form a pyramid.

Importance decides what the viewer draws when zoomed out. When most items are 4 or 5 it stops
telling turning points from detail. This script ranks every event, decision and signal by:

  - how widely Wikipedia covers it: the number of Wikidata sitelinks (language editions),
  - how connected it is here: its number of links in data/links/,
  - its current importance, as a weaker prior (it records someone's judgement).

Each is turned into a percentile and blended. Items are then given importance by rank so the
counts follow TARGET (about 4% at 5, 14% at 4, 34% at 3, 34% at 2, 14% at 1), but no item
moves more than MAX_MOVE levels in one pass, so a single run can't overturn a judgement.

  python tools/importance.py                 report only (writes nothing)
  python tools/importance.py --report F.md   also write the report to a file
  python tools/importance.py --apply         rewrite `importance:` lines in data/

Sitelinks come from the Wikidata query service and are cached in .cache/sitelinks.json.
--offline uses only the cache. Only the `importance:` line of each file is touched.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
KINDS = ("events", "decisions", "signals")
CACHE = ROOT / ".cache" / "sitelinks.json"
SPARQL = "https://query.wikidata.org/sparql"
UA = "threads-of-history/0.1 (https://github.com/AnchoAI/threads-of-history)"

# Share of items at each importance, from the top.
TARGET = [(5, 0.04), (4, 0.14), (3, 0.34), (2, 0.34), (1, 0.14)]
WEIGHTS = {"sitelinks": 0.40, "links": 0.25, "current": 0.35}
MAX_MOVE = 2  # never move an item more than this many levels in one pass


def load(root: Path = ROOT) -> tuple[dict, dict]:
    """Timeline items by id (with their path), and link counts by item id."""
    items = {}
    for kind in KINDS:
        for path in sorted((root / "data" / kind).glob("*.yaml")):
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
            items[d["id"]] = {"path": path, "wikidata": d.get("wikidata"), "importance": d.get("importance", 3),
                              "title": d.get("title", d["id"])}
    degree = {i: 0 for i in items}
    for path in (root / "data" / "links").glob("*.yaml"):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        for end in (d["from"], d["to"]):
            if end in degree:
                degree[end] += 1
    return items, degree


def fetch_sitelinks(qids: list[str], cache: dict, offline: bool = False) -> dict:
    """Sitelink counts for Wikidata ids, using and filling the cache."""
    missing = [q for q in qids if q not in cache]
    if offline or not missing:
        return cache
    for i in range(0, len(missing), 150):
        chunk = missing[i:i + 150]
        q = "SELECT ?item ?n WHERE { VALUES ?item { %s } ?item wikibase:sitelinks ?n }" % " ".join(f"wd:{x}" for x in chunk)
        req = urllib.request.Request(SPARQL, data=urllib.parse.urlencode({"query": q}).encode(),
                                     headers={"Accept": "application/sparql-results+json", "User-Agent": UA})
        for attempt in range(4):
            try:
                rows = json.load(urllib.request.urlopen(req, timeout=60))["results"]["bindings"]
                break
            except Exception:
                time.sleep(5 * (attempt + 1))
        else:
            print(f"warning: could not fetch sitelinks for {len(chunk)} ids", file=sys.stderr)
            continue
        for r in rows:
            cache[r["item"]["value"].rsplit("/", 1)[1]] = int(r["n"]["value"])
        for x in chunk:
            cache.setdefault(x, 0)
        time.sleep(1)
    return cache


def percentiles(values: dict) -> dict:
    """Map each key to the share of values strictly below its value (0..1), ties averaged."""
    ordered = sorted(values.values())
    n = len(ordered)
    out = {}
    for k, v in values.items():
        below = sum(1 for x in ordered if x < v)
        equal = sum(1 for x in ordered if x == v)
        out[k] = (below + (equal - 1) / 2) / max(n - 1, 1)
    return out


def propose(items: dict, degree: dict, sitelinks: dict) -> dict:
    """Proposed importance for every item, plus the blended score."""
    has_sl = {i: sitelinks.get(v["wikidata"]) for i, v in items.items()
              if v["wikidata"] and re.fullmatch(r"Q\d+", str(v["wikidata"])) and sitelinks.get(v["wikidata"]) is not None}
    p_sl = percentiles(has_sl) if has_sl else {}
    p_deg = percentiles(degree)
    p_cur = percentiles({i: v["importance"] for i, v in items.items()})
    score = {}
    for i in items:
        parts = {"links": p_deg[i], "current": p_cur[i]}
        if i in p_sl:
            parts["sitelinks"] = p_sl[i]
        w = sum(WEIGHTS[k] for k in parts)
        score[i] = sum(WEIGHTS[k] * v for k, v in parts.items()) / w
    ranked = sorted(items, key=lambda i: (-score[i], i))
    out, start = {}, 0
    for level, share in TARGET:
        count = round(share * len(ranked)) if level != 1 else len(ranked) - start
        for i in ranked[start:start + count]:
            out[i] = level
        start += count
    clamp = lambda i: max(items[i]["importance"] - MAX_MOVE, min(items[i]["importance"] + MAX_MOVE, out[i]))
    return {i: (clamp(i), score[i]) for i in items}


def apply(items: dict, proposal: dict) -> int:
    changed = 0
    for i, (level, _) in proposal.items():
        if level == items[i]["importance"]:
            continue
        path = items[i]["path"]
        text = path.read_text(encoding="utf-8")
        new, n = re.subn(r"^importance: \d+$", f"importance: {level}", text, count=1, flags=re.M)
        if n == 0:
            new = re.sub(r"^(regions:)", f"importance: {level}\n\\1", text, count=1, flags=re.M)
        path.write_text(new, encoding="utf-8")
        changed += 1
    return changed


def report(items: dict, degree: dict, sitelinks: dict, proposal: dict) -> str:
    from collections import Counter
    before = Counter(v["importance"] for v in items.values())
    after = Counter(level for level, _ in proposal.values())
    lines = ["# Proposed importance", "",
             f"{len(items)} timeline items. Counts by importance, now → proposed:", ""]
    for level in (5, 4, 3, 2, 1):
        lines.append(f"- {level}: {before.get(level, 0)} → {after.get(level, 0)}")
    moved = [(i, items[i]["importance"], proposal[i][0]) for i in items if proposal[i][0] != items[i]["importance"]]
    lines += ["", f"{len(moved)} items change.", "", "## Proposed importance 5", ""]
    for i in sorted((i for i in items if proposal[i][0] == 5), key=lambda i: -proposal[i][1]):
        sl = sitelinks.get(items[i]["wikidata"], "–")
        lines.append(f"- {items[i]['title']} (`{i}`): links {degree[i]}, sitelinks {sl}, was {items[i]['importance']}")
    lines += ["", "## Biggest moves", ""]
    for i, a, b in sorted(moved, key=lambda m: -abs(m[2] - m[1]))[:40]:
        lines.append(f"- {items[i]['title']} (`{i}`): {a} → {b}")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="rewrite importance in data/")
    ap.add_argument("--report", type=Path, help="write the report to this file")
    ap.add_argument("--offline", action="store_true", help="use cached sitelinks only")
    args = ap.parse_args(argv)
    items, degree = load()
    cache = json.loads(CACHE.read_text()) if CACHE.exists() else {}
    qids = sorted({str(v["wikidata"]) for v in items.values() if v["wikidata"] and re.fullmatch(r"Q\d+", str(v["wikidata"]))})
    cache = fetch_sitelinks(qids, cache, args.offline)
    CACHE.parent.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps(cache, sort_keys=True, indent=0))
    proposal = propose(items, degree, cache)
    text = report(items, degree, cache, proposal)
    if args.report:
        args.report.write_text(text, encoding="utf-8")
    print(text if not args.report else f"Report written to {args.report}")
    if args.apply:
        print(f"Changed {apply(items, proposal)} files.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
