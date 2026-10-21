"""Score recorded forecasts (scenario items) once they have resolved.

  python -m forecast.benchmark [--by "CIA"] [--out FILE]

Every scenario in data/scenarios/ with a resolution of `happened` or `did_not_happen` is a scored
forecast: its `probability` against what happened. Grouped by `forecast_by`, the report gives
the number of forecasts, the Brier score, the Brier score of a no-skill forecaster who always
says the group's own hit rate (so a lower number than that means real skill), and a
calibration table.

The first use is historical intelligence estimates (US National Intelligence Estimates and
the like), whose words ("probably", "unlikely") are turned into numbers with Sherman Kent's
scale and recorded in `stated_as` and `probability_basis`. The same scenarios can later be
put to our models and to AI models given only what was knowable on `forecast_on`.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SCENARIOS = ROOT / "data" / "scenarios"
SCORED = {"happened": True, "did_not_happen": False}


def load(folder: Path = SCENARIOS):
    out = []
    for path in sorted(folder.glob("*.yaml")):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        outcome = SCORED.get((d.get("resolution") or {}).get("outcome"))
        if outcome is not None:
            out.append({"id": d["id"], "by": d["forecast_by"], "on": str(d["forecast_on"]),
                        "p": float(d["probability"]), "hit": outcome, "title": d.get("title", d["id"])})
    return out


def brier(rows):
    return sum((r["p"] - r["hit"]) ** 2 for r in rows) / len(rows)


def no_skill(rows):
    """Brier of always forecasting the group's own hit rate (which uses hindsight, so it's a high bar)."""
    rate = sum(r["hit"] for r in rows) / len(rows)
    return sum((rate - r["hit"]) ** 2 for r in rows) / len(rows)


def calibration(rows, edges=(0, .15, .4, .6, .85, 1.0001)):
    out = []
    for lo, hi in zip(edges, edges[1:]):
        b = [r for r in rows if lo <= r["p"] < hi]
        if b:
            out.append((lo, min(hi, 1), sum(r["p"] for r in b) / len(b), sum(r["hit"] for r in b) / len(b), len(b)))
    return out


def report(rows) -> str:
    groups = defaultdict(list)
    for r in rows:
        groups[r["by"]].append(r)
    lines = ["# Recorded forecasts, scored", "",
             "Brier: the mean squared gap between the probability and what happened (0 is perfect, 0.25 is always "
             "saying 50%). No-skill: the Brier of always saying the group's own hit rate. Lower than no-skill means "
             "the forecasts told likely from unlikely.", "",
             "| forecaster | forecasts | happened | Brier | no-skill |", "|---|---|---|---|---|"]
    for by, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines.append(f"| {by} | {len(rs)} | {sum(r['hit'] for r in rs)} | {brier(rs):.3f} | {no_skill(rs):.3f} |")
    for by, rs in sorted(groups.items(), key=lambda kv: -len(kv[1])):
        lines += ["", f"## {by}", "", "Calibration: when it said about p, how often did it happen?", ""]
        for lo, hi, p, hit, n in calibration(rs):
            lines.append(f"- said {lo:.0%}–{hi:.0%} (mean {p:.0%}): happened {hit:.0%} (n={n})")
        lines += ["", "Most confident misses:", ""]
        for r in sorted(rs, key=lambda r: -(r["p"] - r["hit"]) ** 2)[:5]:
            lines.append(f"- {r['title']} ({r['on']}): said {r['p']:.0%}, {'happened' if r['hit'] else 'did not happen'}")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--by", help="only forecasts whose forecast_by contains this text")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    rows = [r for r in load() if not args.by or args.by.lower() in r["by"].lower()]
    if not rows:
        raise SystemExit("no resolved scenarios found in data/scenarios/")
    text = report(rows)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
