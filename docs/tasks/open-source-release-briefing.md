# Briefing: making Threads of History public

**For:** Codex. **From:** Claude Code, at Michael's request, October 2026.
**What we want from you:** your critique of the plan below, not code changes yet. Say where you disagree, what is missing, and what you would do in a different order. Answer the questions in the last section. Write your reply as `docs/tasks/open-source-release-codex-review.md`.

Read `CLAUDE.md` (decisions and progress), `README.md` (principles), `AGENTS.md` (rules for agents) and `docs/table-licenses.md` first. They are the source of truth. This briefing only summarises them where it needs to.

## 1. Where the project stands

The repository (`anchoai/threads-of-history`) is private. It has 84 commits. What it holds:

- **Data** (`data/`), one YAML file per record: 594 events, 20 signals, 9 decisions, 314 actors, 16 series, 777 links and 11 guided paths. Across all records, about 1,500 have `review.status: sourced` and about 240 are `unverified`. Nothing is `reviewed`; only a person may set that.
- **Tooling:** a validator, a build to `dist/graph.json`, and an archive script (`tools/`). These run in CI with pytest (`.github/workflows/validate.yml`).
- **Viewer** (`viewer/`): Vite and three.js, with Playwright tests in CI. It has time zooming, the "knowable on" slider, causal chains, era zones and a 2D/3D toggle.
- **Forecasting** (`forecast/`): country-year models and backtests. The reports are in `docs/backtests/`.
- **Imported tables** (`data/tables/`): V-Dem (CC BY-SA 4.0), UCDP/PRIO and UCDP GED (CC BY 4.0), Maddison (CC BY 4.0) and World Bank WDI (CC BY 4.0, plus World Bank terms). Each keeps its source's licence.
- **Restricted datasets, not committed:** Powell & Thyne coups, EPR, Archigos and IMF vintages are not in git, which we checked across the whole history. Only their registry files in `data/datasets/` are. While the repo is private, Powell & Thyne is read from `.cache/private-tables/` (gitignored).
- **Secrets:** a grep for credentials found nothing besides a false positive in `viewer/unit/knowable.test.mjs`. It has not been checked with a real secret scanner yet.

## 2. Open decisions (Michael's call, but we want your view)

`CLAUDE.md` lists these as undecided. They block publication, because they cannot be applied retroactively once outside contributions arrive.

### Licence

What we propose:
- **Code** (`tools/`, `forecast/`, `viewer/`, `schema/`): Apache-2.0, for its patent grant. MIT is the alternative.
- **Data** (`data/` except `data/tables/`): CC BY-SA 4.0. Our reasons:
  - The V-Dem tables are already CC BY-SA, and forecasts and series built from them inherit share-alike.
  - It matches Wikipedia, which is where most sources and likely contributors come from.
  - It still allows a paid API or a paid forecasting benchmark later.
- **`data/tables/`:** each source's own licence, as documented in `docs/table-licenses.md`.

The alternatives we weighed:
- **CC0.** It matches Wikidata and has the least friction for reuse, but it lets anyone take the dataset closed.
- **CC BY, with the V-Dem tables kept separate.** It is easier to reuse, but share-alike still applies to anything that combines our data with V-Dem.

One complication: summaries are our own words, but each source carries a short `quote` that is mostly from Wikipedia (CC BY-SA) or from news articles (copyrighted, relying on fair use or quotation exceptions). Whatever licence we pick for `data/` cannot relicense those quotes. We think a notice that quotes stay under their source's terms is enough. Is it?

### Contributor terms

- **DCO** (`Signed-off-by` on each commit): light and standard, but the project can never relicense.
- **CLA:** it keeps the option to relicense or to dual-license commercially, which matters because "nonprofit or business" is still open. It deters some contributors.

We lean towards DCO unless Michael wants to keep the business option fully open.

## 3. Proposed plan

### Step 1. Cleanup before publishing (on a branch, reviewed by Michael)

1. **README status line.** It still says "none of it has been checked against sources yet" and "every item is marked `unverified`". Replace it with current counts by review status, and say plainly that nothing is `reviewed` by a person yet.
2. **Private tables.** Confirm that every code path reading `.cache/private-tables/` degrades cleanly when the file is absent. `forecast/panel.py` and `forecast/outcomes.py` seem to already. Confirm that `docs/backtests/` shows only derived scores. The GBM report states "497 attempts from 1950" and per-outcome counts drawn from Powell & Thyne; we think that is fine, but please check.
3. **Licence files:** `LICENSE` (code), `LICENSE-data` (data), and a short licensing section in the README pointing to `docs/table-licenses.md`.
4. **`CITATION.cff`.**
5. **`CONTRIBUTING.md`,** built from the README principles and `AGENTS.md`. It should cover:
   - what counts as a source;
   - that a link's source must itself make the claim;
   - quotes and `archive_url`;
   - the review statuses, and that only people set `reviewed`;
   - how to dispute a link;
   - DCO or CLA.
6. **`CODE_OF_CONDUCT.md`** (Contributor Covenant).
7. **Issue templates:** "Propose a link", "Report an error", "Dispute a link or summary", plus a PR template with a source checklist.
8. **`CODEOWNERS` and branch protection:** CI plus one human review required on `main`. Stricter owners for contested threads (Israel–Palestine, immigration and the like), per the decision that moderation stays with people.
9. **Secret scan** of the full history with a real scanner (gitleaks, or GitHub's secret scanning once the repo is public).

### Step 2. Make it usable without cloning

- **GitHub Pages:** CI builds `graph.json` and the viewer and deploys on every merge to `main`. The viewer already shows review status; it must stay prominent so `unverified` is never read as fact.
- **Versioned data releases:** tag a release with `graph.json` attached, and connect Zenodo so each release gets a DOI. A frozen release is also what a forecasting leaderboard will need: forecasts have to be scored against a fixed snapshot.
- **A `graph.json` format note** (fields and stability promises), so outside tools can depend on it.

### Step 3. Launch in stages

1. **Quiet public:** flip visibility, share with a handful of people, and fix what they find.
2. **Reviewers before a crowd:** recruit a few historians or subject experts to move items from `sourced` to `reviewed`, starting with the guided paths and the deep dives. A small reviewed core is the best credibility signal. The contested links and false-alarm signals will draw the most scrutiny.
3. **Announce:** once the viewer is hosted and one deep dive is reviewed. Venues: Hacker News, digital humanities, data visualisation. Lead with what is new: sourced causal links and the "knowable on" slider.
4. **Forecasting benchmark later,** as `docs/forecasting.md` plans. It needs a licence-clean frozen release, and coups dropped or licensed.

## 4. Risks we see

- **Credibility:** the first visitors will find errors. Mitigations: honest status labels, an easy "Report an error" path, and fast responses.
- **Contested topics** attracting brigading. Mitigations: `CODEOWNERS`, human-only review, and `contested` links with positions rather than winners.
- **Licence mistakes in quotes or tables** are hard to undo once forks exist. This is why the licence decision and the table audit come first.
- **Maintainer load:** Michael is one person. Templates and the validator have to do most of the gatekeeping.
- **The forecasting side** may draw attention ("AI predicts wars") out of proportion to its maturity. Should it be labelled experimental, or held back from the first announcement?

## 5. Questions for you

1. Do you agree with Apache-2.0 for code and CC BY-SA 4.0 for data? If not, what would you choose and why?
2. DCO or CLA, given the open nonprofit-or-business question?
3. Is the quotes notice enough, or do news-article quotes need different handling (shorter limits, linking only)?
4. Are the Powell & Thyne-derived counts and scores in `docs/backtests/` safe to publish before that licence is confirmed?
5. Should `forecast/` be in the public repo from day one, in a separate repo, or behind an "experimental" label?
6. What is missing from Step 1? For example: a security policy, a governance doc, a takedown or correction policy for living people named in the data.
7. Would you change the launch order, for example by recruiting reviewers before going public at all?
8. Anything in the repo, such as the prototype, the staging pools or the task handoffs, that you would remove or rewrite before publishing?

Please keep to the project's style (plain, short sentences) and the rules in `AGENTS.md`. Do not change licence files, data or review statuses as part of this review.
