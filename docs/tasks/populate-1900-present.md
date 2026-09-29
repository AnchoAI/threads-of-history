# Task: populate 1900 to the present

**For:** Codex or another coding agent. **Read first:** `AGENTS.md`, `CLAUDE.md`, `README.md`.

## Goal

Grow the dataset from the 75 unchecked prototype events into a sourced map of 1900 to the present, in small reviewable steps. Quality matters more than quantity: 200 well-sourced events beat 5,000 unchecked ones.

Do **not** write history from memory. The strategy is:

1. **Scripts gather raw material** (Wikidata events, published datasets) into `staging/` and `data/tables/`.
2. **Batches curate it.** Each batch promotes a few dozen events into `data/`, links them with sourced quotes, and lands as one pull request.
3. **A person reviews each pull request.**

## How to work

- Do the tasks below **in order**. Each task is **one pull request** unless it says otherwise. Stop after each one so it can be reviewed.
- Branch from `main`. If `main` does not exist yet, branch from `claude/gracious-noether-71yqww`.
- Before finishing any pull request: `python tools/validate.py` shows 0 errors, `python tools/build.py` succeeds, and `python -m pytest -q` passes. Files you added or changed should have no warnings either (check with `--verbose`).
- The pull request description says what you did, gives counts (items, links, sources added), and lists **everything you could not verify** and **every link you dropped or downgraded, and why**.

---

## Task 0: check your environment (no pull request)

Check that you can reach, from your sandbox:

- `https://query.wikidata.org/sparql` and `https://www.wikidata.org`
- `https://en.wikipedia.org`
- `https://web.archive.org` (including `https://web.archive.org/save/`)
- the dataset sites listed in `data/datasets/`

If any are blocked, **stop and report which ones.** Everything below depends on them.

## Task 1: the archiving script

Principle 5: every source gets an archive snapshot when it is added.

Write `tools/archive.py`:

- Finds every source in `data/` (item sources, link sources, position sources, `known.by` sources, alternatives) that has a `url` but no `archive_url`.
- Asks the Wayback Machine for a snapshot. Prefer an existing snapshot close to the source's `date`, or to today when there is no date. Otherwise request a new one through the Save Page Now API.
- Writes only `archive_url` back into the YAML. It must not reorder or reformat anything else, so use a targeted edit, not a full YAML rewrite.
- Is polite: rate-limited, retries with back-off, and resumable. It has `--dry-run`, and `--path` to limit it to some files.
- Has tests with the network mocked.

Run it on the existing data in the same pull request.

## Task 2: clean up the ported prototype data

Two pull requests: **2a** for events and actors, **2b** for links.

**2a. Events and actors** (`data/events/`, `data/actors/`):

- Add `wikidata` ids. Match on label **and** date; if unsure, leave it out and note why. Use `"none"` only after checking that Wikidata has no matching item.
- Add `iso3` to state actors that have one.
- Work through every `review.notes` entry. Fix dates where a source shows the prototype was wrong. Split the combined events the notes point out (for example "Israel founded; first Arab–Israeli war"), keeping the old id for the main part so links still work.
- Check every summary against a source. Add sources with quotes, archive them, and raise the status to `sourced` when every claim in the summary is covered.
- Anything you could not source stays `unverified`, with a note saying what is missing.

**2b. Links** (`data/links/`):

- Each link currently cites a *candidate* Wikipedia article that nobody has checked. For each link, find a source that **itself states the connection**, and quote the sentence that does. Prefer the scholarly or primary source that Wikipedia cites over Wikipedia itself. Citing Wikipedia is allowed as `type: reference`, but say so in `review.notes`.
- If no source you can find makes the claim, **do not keep the link as documented.** Either mark it `contested` with sourced positions, or delete it and list it in the pull request.
- For contested links, replace every `(needs sourcing)` with a real attribution and source, or remove that position if nobody can be found who holds it. A contested link needs at least two positions.
- Raise to `sourced` only when every source and position has a quote.

## Task 3: check the dataset registry, then write the first importers

**3a. Registry (one pull request).** For each file in `data/datasets/`, confirm the URL, the latest version, the exact licence (with `license.url`) and the recommended citation. Set `license.redistribution` to `allowed` or `restricted`. Set `review.status` to `sourced` and quote the licence text in `notes`. If a dataset's licence is restricted, say what that rules out.

**3b. Importers (one pull request each).** Use `tools/importers/common.py` (`write_table`, `write_series`). Each importer downloads its **pinned** version into `.cache/`, which git ignores, and keeps only 1900 onwards. Running it twice must give identical files.

| Importer | Tables to produce (series ids are suggestions) |
|---|---|
| `tools/importers/maddison.py` | `maddison-gdp-per-capita`, `maddison-population` |
| `tools/importers/vdem.py` | electoral democracy index, liberal democracy index, civil liberties index. Confirm the variable codes (`v2x_polyarchy`, `v2x_libdem`, `v2x_civlib`) in the codebook. |
| `tools/importers/ucdp_armed_conflict.py` | country-year: any active armed conflict (0/1), and the highest intensity that year |
| `tools/importers/powell_thyne_coups.py` | country-year: coup attempts and successful coups. Also write each coup as a row in `staging/coups.csv` for later curation. |

Countries:

- Use ISO 3166-1 alpha-3 codes.
- For states that no longer exist, use the ISO 3166-3 former codes: `SUN` (Soviet Union), `YUG` (Yugoslavia), `CSK` (Czechoslovakia), `DDR` (East Germany). Map West Germany to `DEU` and say so.
- Put the full mapping in the importer, and list any rows you had to drop, with the reason.

Each series item gets:

- `dataset` and `indicator`.
- `threads`: use existing ones, or propose a new thread such as `economy-indicators` under the `economy` domain.
- `regions`: all regions it covers.
- `importance: 2`.
- A source pointing to the dataset's page.

## Task 4: the Wikidata candidate pool

Write `tools/importers/wikidata_events.py`, which queries Wikidata and writes `staging/wikidata-events.csv`.

- **Scope:** events starting in 1900 or later.
- **Classes:** wars and armed conflicts, revolutions, coups, treaties, assassinations, terrorist attacks, massacres and genocides, declarations of independence, national general elections, economic crises, famines, pandemics and major disasters, major protests. **Look up the correct class ids and verify them.** Include subclasses (`wdt:P31/wdt:P279*`), but watch for query timeouts. Query class by class and decade by decade if needed.
- **Columns:** `qid, label, description, start, end, precision, instance_of, countries, sitelinks, enwiki_url, has_cause, has_effect, imported_on`. `has_cause` and `has_effect` come from P828 and P1542; they are sparse, but useful leads for links.
- **Filter** to events with at least ~10 sitelinks, to keep the pool manageable. Record the threshold in the script.
- **Importance:** add a suggested `importance` column based on sitelinks. Calibrate the cut-offs so the prototype's events land roughly where they are now, and document the cut-offs.
- Sort rows so reruns give small diffs. Commit the CSV if it is under about 10 MB; otherwise commit only the script and say so.

## Task 5 onwards: batches

Each batch is one pull request covering **one thread and one period**, for example "Cold War, 1945–1962", or one storyline, for example "Russian Revolution to the founding of the USSR".

**Size:** up to about 30 new events and 40 links. Smaller is fine.

**For each event:**

- Promote it from `staging/wikidata-events.csv` or `staging/coups.csv` when it is there, keeping its `wikidata` id and its dates as a starting point. Check the dates against a source; Wikidata is sometimes wrong.
- Write a neutral one- or two-sentence summary that its sources support.
- Assign existing `threads` and `regions`. New threads go in `data/threads.yaml` with a `domain`.
- Add `actors`, creating actor files as needed with `wikidata` ids.
- Add `known` when an event became public later than it happened, with a source.

**Links:** only links that a source states, each with a quote. Contested links carry positions with sources. Look for `revealed` links (later disclosures) and `part_of` links (sub-events) as well as `led_to`.

**False alarms:** where the period has well-documented warnings or buildups that led nowhere, add them as `signal` items with `outcome: false`.

**Status:** `sourced` when everything is quoted; otherwise `unverified` with notes.

**Suggested order:**

1. **Fill 1900–1945,** which the prototype barely covers: the First World War and its causes, the Russian Revolution and civil war, the collapse of the Ottoman Empire, the interwar crises and the Great Depression (deep dive B covers Germany 1928–34 separately), and the Second World War.
2. **Cover regions the prototype left out.** The prototype is heavily centred on Europe, the US and the Middle East:
   - China: the 1911 revolution, the civil war, 1949, the Great Leap Forward, the Cultural Revolution, reform, 1989.
   - Japan and Korea.
   - Vietnam and South-East Asia.
   - Sub-Saharan Africa: decolonisation, Congo, Biafra, apartheid, the Rwandan genocide.
   - Latin America: the Mexican Revolution, coups, the debt crisis.
   - South Asia beyond partition.
3. **Deepen the existing threads** where they have gaps.
4. **Economy:** the Great Depression, Bretton Woods, the oil shocks, the debt crises, 2008. Link events to the imported series where a source makes the connection.
5. **Later domains** (society, science, culture, sports) once the person reviewing says so.

## Out of scope for these tasks

- The viewer (`viewer/`), which is being built separately.
- The deep dives in `CLAUDE.md` section 6, which get their own handoffs.
- Scenarios and forecasting.
- Anything before 1900. Existing background items such as Sykes–Picot, 1916, are fine; do not add more.
