# Threads of History

An open-source, zoomable map of history that shows **how events connect**. Think of Wikipedia, but for cause and effect.

Events, dates and places already exist in Wikipedia and Wikidata. What this project adds is the **links**: typed, sourced, confidence-rated connections between events, and the evidence behind them.

**The data is the product.** The 3D viewer is one way to look at it. A 2D timeline, a map or a classroom path can use the same data.

> **Status:** early. The dataset was ported from a prototype, and **none of it has been checked against sources yet**. Every item is marked `review.status: unverified`. See [Review status](#review-status).

## Principles

These rules decide what goes into the data. Pull requests that break them will not be merged.

1. **Every link cites a source that itself makes the claim.** You may not connect two events because the connection seems obvious to you. This is Wikipedia's "no original research" rule applied to links. It is what keeps the project from becoming a conspiracy board.
2. **Contested means contested.** Where serious people disagree, mark the link `contested` and record who argues each side. The project does not pick winners on disputed causation.
3. **Two kinds of time.** Everything has *when it happened* (`occurred`) and *when it became known* (`known`). "What was knowable on date X?" must be something the data can answer.
4. **Include the false alarms.** Signals that led nowhere belong in the data. Without them, everything looks obvious in hindsight.
5. **Archive every source when you add it.** Save a Wayback Machine or archive.today snapshot in `archive_url`. Tweets, Telegram posts and articles disappear or get edited.
6. **Store links and short quotes, never full article text.** This keeps the data light and avoids copyright problems.
7. **Use plain, neutral wording.** Say what happened and who claims what.

## Repository layout

```
data/
  domains.yaml        top-level areas: politics, economy, society, science, culture, sports
  threads.yaml        storylines, in display order; each belongs to a domain
  regions.yaml        regions, in display order
  events/             one file per item, named <id>.yaml
  signals/
  decisions/
  actors/
  series/
  scenarios/          possible futures with probabilities (never facts)
  links/              one file per link, named <from>--<type>--<to>.yaml
  paths/              guided paths: ordered lists of item ids
  datasets/           external datasets we import from, with their licences
  tables/             CSV tables produced by importers, used by series
staging/              candidate pools (e.g. Wikidata events) waiting to be curated; not part of the data
schema/
  threads-of-history.schema.json   the format of every file
tools/
  validate.py         checks the data (runs in CI)
  build.py            compiles data/ into dist/graph.json
  importers/          one script per external dataset
tests/                tests for the tools
docs/tasks/           written handoffs for larger pieces of work
prototype/index.html  the original single-file three.js prototype (reference only)
CLAUDE.md             design decisions and roadmap (AGENTS.md points here)
```

Keeping one file per item keeps pull requests small and easy to review.

## Quick start

```sh
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt

python tools/validate.py            # check the data
python tools/validate.py --verbose  # also list every warning
python tools/build.py               # write dist/graph.json
python -m pytest -q                 # test the tools
```

`validate.py` exits with an error code if any rule is broken. With `--strict`, warnings fail too.

### Archiving sources

```sh
python tools/archive.py --dry-run
python tools/archive.py --path data/events
python tools/archive.py
```

The archiver finds missing or empty `archive_url` fields in nested `sources`,
including positions, alternatives and `known.by`. It asks the Wayback Availability
API for the nearest successful snapshot to the source's `date` (UTC today if
absent). Partial dates use the first day of that year or month. Timestamps are
converted to UTC, assuming UTC when no offset is supplied. It accepts the
nearest available snapshot without an age cutoff; its timestamp remains visible
in the URL. If none is available, it submits a Save Page Now request and waits
for confirmation. A queued job is not an archive URL.

Only `archive_url` is inserted or replaced; existing formatting, comments and
review status are preserved. `--dry-run` makes no network requests or writes.
Repeat `--path` to select files or directories under `data/`. Requests are spaced
at least five seconds apart by default, with bounded retries and exponential
backoff for transient failures. `--interval`, `--retries` and `--timeout` control
these limits. `--ca-bundle` accepts a trusted CA bundle when the system certificate
store is incomplete; certificate verification is always enabled.

Successful results and pending save jobs are persisted in the ignored
`.cache/archives.json` (override with `--cache`). Rerunning skips filled sources,
reuses saved results and resumes pending jobs. Failed sources are left untouched
and reported on stdout; any failure makes the command exit nonzero. Save Page Now
may refuse unauthenticated requests; the script reports that failure rather than
claiming a capture exists. Archiving does not verify a historical claim or supply
its supporting quote; that is a separate curation task.

After exhausting retries on HTTP 429, the run stops making network requests and
continues applying confirmed cached results. Rerun later to retry the remaining
sources. `--offline` applies only cached results without making network requests.

## The data format

The full format is in [`schema/threads-of-history.schema.json`](schema/threads-of-history.schema.json). The rest of this section is a summary.

### Items

There are six kinds of item. Each lives in its own folder.

| Kind | Folder | What it is |
|---|---|---|
| event | `data/events/` | Something that happened |
| signal | `data/signals/` | A claim or observation about something uncertain or upcoming. Adds `source_credibility`, `outcome` (`confirmed`, `false` or `unresolved`) and optionally `resolves_to` |
| decision | `data/decisions/` | A choice by specific people. Adds `decided_by` (actor ids) and `alternatives` |
| actor | `data/actors/` | A person, organization or state. Adds `actor_type`. `occurred` is its lifespan and is optional |
| series | `data/series/` | Numbers over time. Adds `unit` and either inline `points` (for one `entity`) or a `table` from a registered `dataset` |
| scenario | `data/scenarios/` | A possible future with a `probability`. See [Scenarios](#scenarios) |

All items share these fields:

```yaml
id: cuban-missile-crisis-1962        # must match the file name
title: Cuban Missile Crisis
summary: Soviet missiles are found in Cuba ...
occurred:                            # when it happened
  start: 1962-10                     # 1962, 1962-10, 1962-10-22 or 1962-10-22T19:00-04:00
  end: 1962-11                       # optional; or `ongoing: true`
  precision: month                   # century | decade | year | month | day | hour
  approximate: true                  # optional: the date itself is uncertain
known:                               # optional; defaults to `occurred`
  public: {start: 1962-10, precision: month}
  by:
    - party: US government
      actor: united-states           # optional actor id
      when: {start: 1962-10-15, precision: day}
threads: [cuba, nuclear, usru]       # ids from data/threads.yaml
regions: [americas]                  # ids from data/regions.yaml
actors: [john-f-kennedy, nikita-khrushchev]
importance: 5                        # 1-5; decides what shows at each zoom level
wikidata: Q128160                    # the Wikidata id, or "none" if Wikidata has no match
sources:
  - url: https://...
    archive_url: https://web.archive.org/...
    title: ...
    publisher: ...
    date: 1962-10-23
    quote: A short excerpt that makes the claim.
    type: news                       # primary | news | scholarly | osint | reference
review:
  status: unverified                 # unverified | sourced | reviewed
  notes: [Anything that still needs checking.]
```

`wikidata` is how the project avoids duplicates: two items may not share an id, and the checker warns about events and actors that don't have one yet. It also warns when two events share a title and year.

Every thread belongs to a **domain** (`data/domains.yaml`), so items get their domains from their threads. Sports and pop culture are domains like any other: add a domain, add threads under it, and the viewer can group or filter by them.

In YAML, **put a bare year in quotes** (`start: "1962"`). Otherwise it is read as a number and the validator will say so.

### Links

```yaml
id: bucharest-summit-2008--led_to--russia-annexes-crimea-2014
from: bucharest-summit-2008
to: russia-annexes-crimea-2014
type: led_to          # led_to | revealed | echo | signal_of | part_of
confidence: contested # documented | contested
note: One sentence.
sources: [...]        # at least one, always
positions:            # required when contested: at least two
  - claim: NATO's expansion provoked Russia.
    held_by: [Russian government, John Mearsheimer]
    sources: [...]
review: {status: unverified}
```

| Type | Meaning | Direction rule the validator checks |
|---|---|---|
| `led_to` | cause | `from` cannot start after `to` |
| `revealed` | a later disclosure sheds light on an earlier item | `from` cannot start before `to` |
| `echo` | a parallel with no causal link | none |
| `signal_of` | a signal pointing to an event | `from` must be a signal |
| `part_of` | a sub-event inside a larger event (how zooming in works) | no loops |

### Scenarios

A scenario is a possible future, recorded as a forecast:

```yaml
id: ceasefire-2027
title: Ceasefire agreed
summary: ...
window: {start: "2027", precision: year}   # when it would happen
probability: 0.3                           # assuming everything in `given` happens
given: [talks-resume-2026]                 # other scenarios it depends on (a tree of futures)
forecast_by: Example forecaster
forecast_on: 2026-09-01
resolves_by: 2027-12-31
resolution: {outcome: open}                # open | happened | did_not_happen | ambiguous
```

Scenarios are never facts. No link may point to or from one. When a scenario happens, its `resolution.event` names the event that records it. Forecasts can then be scored against outcomes.

### Datasets and tables

Numbers from outside sources (GDP, democracy scores, conflict counts) are imported, not typed in:

1. The source is registered in `data/datasets/<id>.yaml` with its URL, pinned version, citation and licence. `license.redistribution` is `allowed`, `restricted` or `unknown`. Tables from a `restricted` dataset are refused, and `unknown` gives a warning until someone checks.
2. An importer in `tools/importers/` downloads that version and writes a long CSV to `data/tables/`, with columns `entity,at,value` and optionally `published`. `entity` is an ISO 3166 alpha-3 country code; state actors carry the same code in `iso3`. `published` records when a figure first came out, since figures like GDP get revised.
3. A series item points to the table and the dataset.

The build writes each table to `dist/series/<id>.json` so viewers load it only when needed.

### Review status

Every item and link has `review.status`. The validator's requirements get stricter at each level:

| Status | Meaning | Validator requires |
|---|---|---|
| `unverified` | Not checked. Sources may be placeholders. | Only the basic format |
| `sourced` | Every source has a `quote` that makes the claim, but no person has checked it yet. Use this for AI-proposed links. | A `quote` on every source; a source for every contested position. A missing `archive_url` is a warning |
| `reviewed` | A person checked the sources, quotes and archive links. | All of the above plus `archive_url`, `publisher` and `date` on every source, and `review.reviewed_by` |

Nothing produced by a script or an AI goes above `sourced` without a person checking it.

### Importance

`importance` runs from 1 to 5. It decides what the viewer shows at each zoom level. The values in the ported data are editorial first guesses. Later they could come from Wikipedia pageviews or link counts.

## dist/graph.json

`tools/build.py` runs the validator, then writes one JSON file for viewers:

```json
{
  "format_version": 1,
  "threads": [...], "regions": [...],
  "items": [{"kind": "event", "id": "...", "occurred": {"start": "1962-10", "precision": "month", "range": [1962.748, 1962.833]}, ...}],
  "links": [...], "paths": [...],
  "stats": {"event": {"unverified": 75}, ...}
}
```

The build adds `kind` and `domains` to every item and fills `known.public` from `occurred` when it is missing. It also adds `range` to every time span: the start and end in decimal years, so a viewer can place items without parsing dates. `end` is `null` for ongoing spans. The output is deterministic: rebuilding unchanged data gives an identical file. `dist/` is not committed; CI uploads the built file as an artifact.

## Contributing

1. Add or edit files under `data/`.
2. Run `python tools/validate.py` and fix any errors.
3. Open a pull request. CI runs the same checks.

For now the most useful work is checking the ported data. Pick an item or link, find a source that makes the claim, and add its `quote` and `archive_url`. Then raise its status to `sourced`, or to `reviewed` if you are the one checking it. Items with open questions list them in `review.notes`.

## License

Not decided yet. The options are CC BY-SA, which would match Wikipedia, or CC0, which would match Wikidata. See the open questions in [CLAUDE.md](CLAUDE.md).
