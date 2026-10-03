# Threads of History: project handoff

Paste this into a new Claude Code session to start the project. Keep it in the repo as `CLAUDE.md` or `DESIGN.md`. It is the source of truth for decisions made so far.

The file `prototype/index.html` (attached alongside this handoff) is a working single-file three.js prototype. It has about 75 events, about 81 links and three guided paths. Treat it as a reference for look and feel, not as the architecture.

## Working in this repo

- `python tools/validate.py` checks `data/` against `schema/threads-of-history.schema.json` and the cross-file rules. `python tools/build.py` writes `dist/graph.json`. `python -m pytest -q` tests both. CI (`.github/workflows/validate.yml`) runs all three.
- Every item and link has `review.status`: `unverified`, then `sourced` (quotes attached, no person has checked them yet), then `reviewed` (a person checked it). Never raise anything to `reviewed` yourself; that needs a person. AI-proposed content goes in as `unverified` or `sourced`.
- Put open questions about an item in its `review.notes`, not in the summary.
- Contested positions whose attribution is a guess say `(needs sourcing)` in `held_by`. The validator refuses that once an item is `sourced`.
- Rules for coding agents are in `AGENTS.md`. Larger handoffs are in `docs/tasks/`.

### Progress

- Milestone 1 (repo, schema, validator, build, CI, README): done.
- Milestone 2 (port the prototype's data): done, but everything is `unverified`. The port ran in a sandbox with no access to Wikipedia or archive.org, so no quotes or archive links were added. Items and links carry notes on what to check. Actors were added, and `known` dates were added where they differ from `occurred` (Sykes–Picot, RDS-1, the Cuban Missile Crisis).
- Schema extended for the decisions below: domains, Wikidata ids with a duplicate check, scenarios, a dataset registry, and table-backed series.
- Handoff for populating 1900 to the present: `docs/tasks/populate-1900-present.md`, given to Codex.
- Milestone 3 (the viewer loading `graph.json`): done in `viewer/`. It matches the prototype's features and adds lanes by domain, review status and open questions in the side panel, shapes by kind (event, signal, decision), and links to items in the URL. Playwright tests run in CI.
- Viewer lanes scale: in thread mode each domain gets a slice of the circle, threads are ordered so related ones sit together, and above 16 threads (raised from 12 when the 1900–1945 batches added six threads) each domain collapses to one lane that opens on click. A fake 40-thread fixture (`viewer/tests/fixtures/`) tests this. Lane zooming by time period is still to do and belongs with time zooming.
- Viewer zooming: time zooms by changing the window (from the whole timeline down to six hours) with a histogram strip along the bottom; the 120 most important items in the window are drawn and about 30 labelled; `part_of` sub-events appear once their parent fills a quarter of the window; lanes for threads with nothing in view drop away. A 3D/2D toggle adds a flat subway-map view. The rules live in `viewer/src/timescale.js` and `viewer/src/visibility.js`, with Node unit tests.
- "Knowable on" slider: done. Shows only items known by a date, to the public or to a named party from `known.by`; links, the side panel and search follow the same rule, so nothing leaks from hindsight. Rules in `viewer/src/visibility.js` (`knownSince`, `isKnown`). It needs data with real `known` dates to shine; deep dive A is the natural test.
- 1900–1945, first batches (Task 5, batch 1): 174 sourced timeline items (163 events, 3 decisions, 8 signals), 86 actors and 158 links, covering the First World War and its origins, Russia and the Ottoman collapse, the interwar years and the Depression, China and Japan, the Second World War, and South Asia, Africa, Latin America and South-East Asia. Six threads were added (`ww1`, `russia`, `interwar`, `ww2`, `china`, `econ-crises`) and two regions (`sub-saharan-africa`, `south-east-asia`). Every quote was checked word for word against the fetched page. Most sources are Wikipedia (`reference`); many have no `archive_url` because Save Page Now is unreachable from the sandbox and no snapshot existed. Four items are `unverified`, with notes.
- Next for the viewer: series as bands, era zones, and "why did this happen?".

## Decisions since the handoff

These came out of planning conversations with Michael and extend sections 3–7 below.

- **Scope for now: 1900 to the present.** Earlier background items are fine but not a priority.
- **Forecasting is a goal.** The project should eventually support scored, testable forecasts, not just explanation. What makes this possible is the two kinds of time: a model can be tested on only what was knowable at a date. Plan, in order: the viewer and the deep dives; country-year data with the date each figure was published; a backtesting setup that matches one published model (for example the Political Instability Task Force's); a forecasting test for AI models and a public leaderboard; then partners and funding.
- **The unit for numbers is country-year,** with country-month added later for conflict work. Tables use ISO 3166-1 alpha-3 codes (ISO 3166-3 former codes for states that no longer exist).
- **External data is registered, not typed in.** Every source dataset has a file in `data/datasets/` with its version, citation and licence, and an importer in `tools/importers/`. Tables from datasets that restrict redistribution are refused. First datasets: Wikidata, Maddison Project, V-Dem, UCDP/PRIO, Powell & Thyne. ACLED and GDELT are deliberately left out for now: ACLED for licence reasons, GDELT for noise.
- **Wikidata is the skeleton, curated in batches.** Wikidata events go into a candidate pool in `staging/`, and batches promote them into `data/` with sources and links. Items carry their `wikidata` id, and the validator refuses duplicate ids.
- **Domains sit above threads:** politics, economy, society, science, culture, sports. The data has no fixed axes; the viewer chooses which labels (time, domain, thread, region, actor) to map to space. New domains such as sports need no format change.
- **Branching futures are `scenario` items:** a probability, a `given` list of other scenarios (forming a tree), a resolution date and an outcome. They are never facts and cannot be linked to facts; when one happens it points to the event. In the viewer, the past is one spine that fans out at "today" into branches whose thickness shows their probability.
- **Not decided yet:** the licence (CC0, CC BY or CC BY-SA), and whether the project is a nonprofit or a business (grants and donations, or paid API access and a paid AI forecasting test). Ads are ruled out. Before accepting outside contributions, decide the licence and whether contributors must sign an agreement.
- **Community:** if a community is built, centre it on scored forecasts and contributions, not a general social feed. Moderation of contested topics stays with people, not an autonomous agent.

---

## 1. What this is

An open-source, visual, zoomable map of history that shows **how events connect**. The closest comparison is Wikipedia, but for cause and effect.

- Events, dates and places already exist in Wikipedia and Wikidata. **The new thing is the links**: typed, sourced, confidence-rated connections between events, plus the evidence behind them.
- It must go from very broad to very deep. Zoomed out, you see centuries of turning points. Zoomed in, you see day-by-day troop movements and online chatter before an invasion.
- Long-term goal: a public dataset plus a viewer that anyone can contribute to. **The data is the product. The 3D viewer is one lens on it**, and other views (2D, maps, classroom paths) should be able to use the same data.

Owner: Michael, a Python developer who knows git and Playwright. He is new to three.js and front-end work.

## 2. Core principles (do not break these)

1. **Every link cites a source that itself makes the claim.** Contributors may not connect two events because the connection seems obvious to them. This is Wikipedia's "no original research" rule applied to links, and it is what keeps the project from becoming a conspiracy board.
2. **Contested means contested.** Where serious people disagree, the link is marked `contested` and records who argues which side. The project does not pick winners on disputed causation.
3. **Two kinds of time.** Everything has *when it happened* and *when it became known*. "What was knowable on date X?" must be a real query.
4. **Include the false alarms.** Signals that did not lead anywhere, such as Russia's spring 2021 buildup and pullback, belong in the data. Without them, everything looks obvious in hindsight.
5. **Archive every source when it is added.** Save a Wayback Machine or archive.today snapshot. Tweets, Telegram posts and articles disappear or get edited.
6. **Store links and short quotes, never full article text.** This keeps the data lightweight and avoids copyright problems.
7. **Plain, neutral wording** in summaries. Say what happened and who claims what.

## 3. Data model

The prototype had only events and links. The model going forward has five kinds of item plus links (a sixth, `scenario`, was added later; see "Decisions since the handoff"):

| Kind | What it is | Examples |
|---|---|---|
| `event` | Something that happened | Cuban Missile Crisis; Enabling Act passed |
| `signal` | A claim or observation made at a moment, about something uncertain or upcoming | Satellite imagery of a buildup near Belgorod; a Telegram rumor; a US intelligence warning |
| `decision` | A choice by specific people, with the alternatives they had | Hindenburg appoints Hitler chancellor (Jan 1933) |
| `actor` | A person or organization, with a lifespan | Franz von Papen; the GIA; NATO |
| `series` | Numbers over time, drawn as a band along the timeline | German unemployment 1928–34; Nazi vote share; troop counts near the border |

Fields every item has:

- `id`: a stable slug, e.g. `cuban-missile-crisis-1962`.
- `title` and `summary`, both neutral and short.
- `occurred`: when it happened. It is a date range with a precision flag: `century`, `decade`, `year`, `month`, `day` or `hour`. Uncertain dates are allowed.
- `known`: when it became public. Optionally, when it became known to specific parties such as "US intelligence". Default: the same as `occurred`.
- `threads[]`: storylines, e.g. `nuclear`, `migration`, `mideast`.
- `regions[]`
- `actors[]`: ids of the people and organizations involved.
- `importance`: 1–5. Drives what is visible at each zoom level. It could start from Wikipedia pageviews or link counts.
- `sources[]`: each has `url`, `archive_url`, `title`, `publisher`, `date`, `quote` (a short excerpt that supports the claim) and `type` (`primary`, `news`, `scholarly`, `osint` or `reference`).

Extra fields for signals: `source_credibility`, `outcome` (`confirmed`, `false`, `unresolved`), and `resolves_to` (the event it turned out to predict, if any).

Extra fields for decisions: `decided_by[]` and `alternatives[]`.

**Links** each have:

- `from`, `to`
- `type`: one of `led_to` (cause), `revealed` (a later document or disclosure that sheds light on an earlier event, so it points backward in time), `echo` (a parallel with no causal link), `signal_of` (a signal pointing to an event), or `part_of` (a sub-event inside a larger event, which is how zooming in works).
- `confidence`: `documented` or `contested`.
- `note`: one sentence.
- `sources[]`: required.
- For contested links: `positions[]`, each with `{claim, held_by, sources}`.

**Storage:** one file per item, as YAML or JSON, under `data/events/`, `data/links/` and so on. A JSON Schema defines the format, and a Python validator enforces it in CI. A build step compiles everything into one `dist/graph.json` for the viewer. One file per item keeps pull requests small and reviewable, like Wikipedia's edit history.

## 4. The viewer (lessons from the prototype)

What worked:
- **Time runs along a central spine. Threads are lanes arranged around it.** An event on several threads sits between their lanes, closer to the spine.
- **Link types are told apart by color.** Contested links are dashed. Small dots move along each link to show its direction, which matters because `revealed` links point backward.
- **Clicking an event** dims everything unrelated, flies the camera to it, and opens a side panel with the summary, threads, regions, sources and a list of connections you can click through.
- **Guided paths** step through a chain of events with the arrow keys. This covers the "explain" use case; free exploration covers the "explore" use case.
- **A toggle rebuilds the lanes by region** instead of by thread. Different arrangements reveal different patterns.

What is needed next:
- **A stretchable time axis.** Zooming should go from centuries down to hours, with events opening into their `part_of` sub-events. The prototype's fixed scale of 4 units per year will not work.
- **Visibility tied to importance and zoom level.** The prototype will become unreadable at a few hundred events.
- **Series drawn as bands** along the relevant lane.
- **A "knowable on" slider** that hides anything whose `known` date is after the slider date.
- **Eras shown as faint zones** along the spine.
- **"Why did this happen?"**: trace `led_to` chains backward 2–4 steps from any event.

Tech: the prototype uses three.js 0.147 from a CDN, in one HTML file with no build step. For the real project, a small Vite + three.js app is reasonable. Keep it simple: the data pipeline matters more than the framework.

## 5. Getting data in at scale

- **Wikidata** is public domain (CC0), so its data can be used freely. Use it for event skeletons: dates, places, and the "has cause" (P828) and "has effect" (P1542) properties, which exist but are sparsely filled in.
- **AI-assisted link extraction.** Wikipedia articles are full of sentences like "the crisis led to…" with citations attached. A script can extract these as *proposed* links with their source and quote. A human accepts or rejects each one. Nothing auto-merges.
- **An archiving script** snapshots every source URL when it is added.

## 6. First milestones

1. **Set up the repo:** folder layout, JSON Schema, Python validator, build script that outputs `dist/graph.json`, a GitHub Action that runs the validator, and a README that explains the principles in section 2.
2. **Port the prototype's data into the new format.** The prototype's `EVENTS` and `LINKS` arrays are in `prototype/index.html`. Add `known` dates, actors and proper sources as you go. Flag anything that could not be verified.
3. **Get the viewer loading `graph.json`,** at the same features as the prototype.
4. **Deep dive A: Russia's buildup, March 2021 to February 24, 2022.** This includes the spring 2021 buildup and partial pullback (a false alarm), the late-2021 satellite imagery, Russia's December 2021 draft treaties, the January 2022 embassy evacuations, the public US warnings, the February 21 recognition of the Donetsk and Luhansk "republics", and the Google Maps traffic jam spotted near Belgorod on the night of the invasion. This dive tests signals, both kinds of time, and zooming down to the day.
5. **Deep dive B: Germany 1928–1934.** Nazi vote share goes from 2.6% (1928) to 18.3% (1930), 37.3% (July 1932) and 33.1% (November 1932). Then come the January 1933 appointment, the Reichstag fire, the March 1933 election (43.9%), the Enabling Act, and Hindenburg's death in August 1934. This dive tests decisions, actors and series (unemployment).
6. Then: zooming, importance-based visibility, the "knowable on" slider.

**Every fact in the deep dives must be checked against sources as it is entered.** The prototype's content came from Claude's own knowledge, with Wikipedia links as placeholders. None of it has been verified yet.

## 7. Open questions

- The data license. CC BY-SA would match Wikipedia; CC0 would match Wikidata.
- The contribution flow: GitHub pull requests only at first, or an in-app editor later?
- How to handle moderation on the most contested topics (Israel–Palestine, immigration, JFK).
- Whether the project is mainly a tool Michael builds, or a knowledge base with a community. This changes how much effort goes into contributor tooling.
