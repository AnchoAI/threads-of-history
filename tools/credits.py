"""Write CREDITS.md: who to credit for the outside data this project uses, and on what terms.

  python tools/credits.py          rewrite CREDITS.md
  python tools/credits.py --check  exit 1 if CREDITS.md is out of date (the tests run this)

The project's own data is CC0 (LICENSE). Tables imported from outside datasets keep their
publishers' licences; this file lists them from data/datasets/, for every dataset whose tables
or series are committed in data/, plus Wikidata (ids) and Natural Earth (land borders).
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ALWAYS = ["wikidata", "natural-earth"]  # used outside data/series: item ids, forecast/data/neighbours.json
# Datasets reached through another one: WDI's youth bulge comes from UN World Population Prospects.
VIA = {"world-bank-wdi": ["un-world-population-prospects"]}


def used(root: Path = ROOT) -> list[str]:
    ids = {yaml.safe_load(p.read_text(encoding="utf-8")).get("dataset") for p in (root / "data" / "series").glob("*.yaml")}
    ids = {i for i in ids if i}
    for i in list(ids):
        ids.update(VIA.get(i, []))
    return sorted(ids) + [i for i in ALWAYS if i not in ids]


def render(root: Path = ROOT) -> str:
    lines = ["# Credits", "",
             "Threads of History's own data (events, links, actors, paths, scenarios and the rest of `data/`) is "
             "dedicated to the public domain under CC0 1.0 (see `LICENSE`); the code is under the MIT licence "
             "(`LICENSE-CODE`). Two kinds of material are not ours to dedicate, and keep their own terms:", "",
             "- **Quotes.** The `quote` fields in `sources` are short excerpts from the cited works, included to show "
             "what each source says. They remain the property of their authors and publishers.",
             "- **Imported tables** in `data/tables/` and the series that describe them come from the datasets below, "
             "under the licences shown. Credit them as given here when you use their tables. In particular, tables "
             "from V-Dem (`vdem-*`) are under CC BY-SA 4.0: anything shared that is built from them must use the same "
             "licence. Tables kept outside git for licence reasons (`.cache/private-tables/`) are not distributed.", "",
             "This file is generated from `data/datasets/` by `python tools/credits.py`.", ""]
    for i in used(root):
        d = yaml.safe_load((root / "data" / "datasets" / f"{i}.yaml").read_text(encoding="utf-8"))
        lic = d["license"]
        lines += [f"## {d['title']}", "",
                  f"- Publisher: {d['publisher']}",
                  f"- Website: {d['url']}",
                  f"- Licence: {lic['name']}" + (f" ({lic['url']})" if lic.get("url") else "")]
        if lic.get("attribution"):
            lines.append(f"- How to credit: {' '.join(str(lic['attribution']).split())}")
        if d.get("citation"):
            lines.append(f"- Citation: {' '.join(str(d['citation']).split())}")
        lines.append("")
    return "\n".join(lines)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    text = render()
    path = ROOT / "CREDITS.md"
    if "--check" in argv:
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            print("CREDITS.md is out of date: run python tools/credits.py")
            return 1
        return 0
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
