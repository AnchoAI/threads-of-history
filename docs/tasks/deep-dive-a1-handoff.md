# Deep dive A1: review and continuation handoff

Branch: `codex/russia-buildup-a1`, based on main at `6bce72a`.
Scope: A1 only. No A2 links, contested positions or guided path. Do not start Task 2a.

## Work ready for review

- 20 timeline items: 11 events (10 new and the refined existing invasion), seven signals and two decisions.
- Four new actors: Joe Biden, Sergei Shoigu, Jake Sullivan and Belarus. Wikidata identities were checked via entity JSON. Existing Putin ID is `vladimir-putin`.
- 19 `part_of` links, all pointing into the new buildup parent.
- 28 distinct source URLs, with exact excerpts from sources actually opened. Maximum excerpt length is 106 characters. Sources were read through the web tool or Python urllib with certificate verification enabled. Search snippets alone were not used as evidence.
- The existing `russian-invasion-of-ukraine-2022` ID is retained, its start is refined to 24 February, and its unsourced Nord Stream 2 side claim is removed. **Task 2a should skip this item.**
- The draft agreements have `occurred: 2021-12-15`, public disclosure on 17 December, and `known.by` for **US government** on 15 December, supported by the opened MFA release mirrored by GlobalSecurity.
- The Belgorod observation has `2022-02-24T03:15+03:00`, hour precision, with the observation time and historical UTC offset separately sourced. Public reporting is conservatively dated to 24 February, not to an unverified tweet timestamp.
- Nothing is marked reviewed. Thirty-eight of the 43 touched data records are sourced; five remain unverified because of missing archives.

## Verification and blockers

Completed on the curated data:

- `python tools/validate.py`: **0 errors, 134 warnings**, versus 135 warnings at baseline. **No warnings in touched files.**
- `python tools/build.py`: pass, producing 152 items, 100 links and three existing paths.
- `python -m pytest -q`: **91 passed**.
- `cd viewer; npm ci`: pass, zero audit vulnerabilities.
- `npm run data`: pass.
- `npm test`: **14 unit tests pass; 15 browser tests pass and two fail.** The browser was installed locally after the initial missing-browser run.

The failing browser tests are `viewer/tests/viewer.spec.js:64` (canvas click) and `:209` (2D picking). They select `russian-invasion-of-ukraine-2022` by its projected position at the initial full-timeline scale. That node is now a child of the buildup parent. `viewer/src/visibility.js` intentionally hides children until the parent fills a quarter of the time window (unless selected/forced). The tests must zoom to this episode or use a genuinely visible node before testing picking. **Do not remove the historically meaningful relationship merely to satisfy the tests.** The user expressly prohibits editing `viewer/`; a viewer-owner fix or explicit scope authorization is needed before that change. No PR has been opened because the user requires all checks to pass first.

The checked main-based viewer also has **no “Show only what was known by a date” checkbox or party picker**. All eight requested visual filter checks (four dates × public/US government) are therefore blocked. An earlier inspection found the feature on the unmerged `claude/gracious-noether-71yqww` branch at `d5b5bcf`; recheck current remote state before coordinating with that work. Do not cherry-pick or edit the viewer under this data task without authorization.

Manual browser inspection confirmed the app loads and search opens the Belgorod panel with `03:15+03:00`, the public reporting date, sources and review notes. This does not substitute for the missing filters. The tab initially loaded a graph built while archiving was still in progress; reload after the final build when checking archive badges.

An independent date-field audit (not a visual test and not a test of the future viewer implementation) gives these counts among the 20 A1 timeline items:

| Cutoff | Public | US government | Difference |
| --- | ---: | ---: | --- |
| 2021-04-30 | 3 | 3 | Parent, spring concern and pullback; no invasion |
| 2021-12-15 | 6 | 7 | Draft agreements available only to US government |
| 2022-02-20 | 17 | 17 | No recognition, Belgorod observation or invasion yet |
| 2022-02-24 | 20 | 20 | All A1 timeline items |

## Archiving

`tools/archive.py` ran on every touched data file, including nested `known.by` sources, with the bundled certifi CA file. TLS verification stayed on. It processed **51 source occurrences, added 46 archive URLs, and reported five failures covering three distinct URLs**. Successful snapshots can be much later than the historical publication; they are preservation evidence, not evidence of when a claim became public.

The following stay unverified, with the failure recorded in `review.notes`:

- `actors/jake-sullivan.yaml`: `https://www.wikidata.org/wiki/Special:EntityData/Q16730147.json`
- `signals/us-intelligence-offensive-report-2021.yaml` and its `part_of` link: `https://abc17news.com/news/ap-national-news/2021/12/03/u-s-intelligence-finds-russia-planning-ukraine-offensive/`
- `signals/russian-mfa-denial-2022.yaml` and its `part_of` link: `https://www.globalsecurity.org/wmd/library/news/russia/2022/russia-220216-russia-mfab01.htm`

Each live source was opened and its quote checked. Wayback had no usable capture and Save Page Now returned HTTP 401. No archive was fabricated. Retaining unverified status avoids implying completed source preservation and introduces no new validation warnings.

## Deliberately omitted or qualified

- No claimed exact March start day: parent start is month precision. Its public date is a conservative documented-by 13 April, not a claim that no earlier reporting existed.
- Spring concern is **unresolved**, not a fabricated dated forecast. The pullback item records an announced order, not proof that all units withdrew.
- No fixed-date February “false alarm”: sources opened did not establish a sufficiently precise unconditional forecast and resolution. Sullivan’s warning was conditional, so it is not scored as a failed prediction for 16 February.
- The Russian denial is attributed. Its assurance is contradicted by the later invasion; the data does not claim to establish when private intentions formed.
- Confirmed warning/OSINT outcomes concern the subsequent invasion, not every troop estimate or operational detail. Avoid treating these outcomes as information already known at the signal date in future forecasting work.
- No troop figures were copied from memory. The AP assessment is modeled without its numerical estimate.
- January diplomacy is represented by the 12 January council and 26 January proposals; no separate 10 January bilateral-talks item was curated.
- No earlier private intelligence knowledge date was verified. `known.by` is used only for the draft documents, not guessed for intelligence reports.
- Original Google Maps tweets were not independently retrieved. Do not invent their publication times or identify vehicles from traffic data alone.
- Exact invasion start hour, additional evacuations/actors, alleged completed withdrawals and later disclosures were left out rather than thinly sourced.
- Some event slices use `wikidata: none` where no separate match was verified. The parent, essay, draft-agreement episode, exercises, invasion and all four new actors have checked IDs.
- Only A1 relationships are present. All `led_to`, `signal_of`, `revealed`, contested positions and the guided path remain for A2 after review.

## Next steps for Claude or Codex

1. Fetch this branch and read AGENTS.md, CLAUDE.md and README.md, then this handoff. Review the data and its source/quote support before expanding anything.
2. Coordinate the viewer test fix and missing knowable-on controls with the viewer owner. The existing prohibition on editing viewer files remains in force. Do not silently broaden this PR.
3. Once the dependency is available, rerun all required checks and the four-date public/US-government visual checks. Include the exact results and all archive failures in the PR description.
4. Open **one A1 PR against main only after required checks pass**, then stop for review. Do not proceed to A2 or Task 2a.

## Local continuation details

Checkout: `C:\Users\MichaelKauffman\Documents\Codex\2026-09-29\repository-anchoai-threads-of-history-branch\work\threads-of-history`.

Use `.venv\Scripts\python.exe`; prepend `.venv\Scripts` to PATH for `npm run data`. Set npm cache to `.cache\npm`. Playwright was installed under `.cache\playwright`; set `PLAYWRIGHT_BROWSERS_PATH` to that absolute directory. Python tests used `PYTEST_ADDOPTS=--basetemp=.cache/pytest-a1 -o cache_dir=.cache/pytest-cache-a1`; use a fresh basetemp on a later run if permissions require it.

Ignored local evidence: `.cache/a1-manifest.json`, `a1-sources.json`, `a1-quote-check.json`, `a1-archive.log`, `a1-baseline-validation.txt`, `a1-validation-final.txt`, `a1-viewer-tests.log` and `archives.json`. The quote-check script's HTTP 403 entries were separately opened and verified through the web tool; they are not unverified search snippets. Sources and exact quotes are preserved in the committed YAML so another environment does not need these scratch files.

One-off scratch scripts are outside the repository in `../research_a1.py` and `../curate_a1.py`. **Do not rerun the curation generator:** it deliberately refuses overwriting existing records and does not contain the later archive/status changes.

Git publishing uses the already configured AnchoAI account through Git Credential Manager. On this Windows host Schannel failed, so use `git -c http.sslBackend=openssl`. Sandbox credential-store access failed earlier; an approved elevated git process can use the existing sign-in. Never print or paste credentials. Do not ask the user to sign in again without first trying the known working route.
