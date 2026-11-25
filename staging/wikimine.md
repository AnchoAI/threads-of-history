# Mining Wikipedia for links

`tools/wikimine.py` finds sentences in Wikipedia's event articles that state a connection to another event ("led to", "in response to", "part of") and turns them into proposed links. Each proposal quotes the sentence and cites the article, so it can be checked against the page. Everything lands in `staging/wikimine/`, marked `unverified`. `events.jsonl` and `candidates.jsonl` are committed (short quotes with links to their articles); the rest is rebuilt locally. Nothing goes into `data/` until a person has checked it.

## Steps

| Step | Command | What it does | Output |
|---|---|---|---|
| 1 | `events` | Asks Wikidata for wars, battles, revolutions, coups, treaties, elections, laws, disasters, strikes, crises, pandemics and the like (about 70 classes, each with a minimum number of language editions for noisy ones such as elections) with a date and an English article, plus Wikidata's own "part of", "has cause" and "has effect" statements between them | `events.jsonl` |
| 2 | `fetch` or `dump` | Gets those articles, from the API (50 per request) or from a downloaded dump, and keeps the sentences that have a connecting phrase, plus the infobox "Part of" field | `sentences.jsonl` |
| 3 | `extract` | Keeps sentences where a connecting phrase sits next to a link to another event (all of them for "led to A and B"), and the infobox's "Part of" field, works out the direction from the phrase, follows redirects, checks the dates and compares with Wikidata | `candidates.jsonl` |
| 4 | `classify` (optional) | Claude reads each sentence and says whether it really states the link, its type and direction. Needs an Anthropic API key | `classified.jsonl` |
| 5 | `sample` | Picks 30 at random from each batch (below) into a checklist for a person; `sample --score FILE` gives each batch's precision | `sample-DATE.md`, `sample-DATE.json` |
| 6 | `write` | Writes YAML link files, plus stub files for events not yet in `data/` | `links/`, `events/` |
| 7 | `promote` | Writes a batch that cleared its sampled check into `data/` (below) | `data/links/`, `data/events/` |

## Running it locally

You need Python 3.10+, about 30 GB of free disk for the full run and an internet connection (Wikidata, and the API for redirects).

```bash
git clone https://github.com/AnchoAI/threads-of-history.git
cd threads-of-history
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt mwparserfromhell
```

### Everything through the API (recommended; no download)

```bash
python tools/wikimine.py events --from 500                   # an hour or more; each class is cached, so rerun after an interruption
python tools/wikimine.py fetch                               # every event article, 50 per request (add --limit 3000 for a quick pilot)
python tools/wikimine.py extract
python tools/wikimine.py sample --n 30
```

Open `staging/wikimine/sample-<date>.md`, tick one box per item, then run `python tools/wikimine.py sample --score staging/wikimine/sample-<date>.md`.

### Or from a downloaded dump

This reads the same articles from a local copy instead of the API. Download the current English dump and its index from <https://dumps.wikimedia.org/enwiki/latest/>, about 27 GB in total:

```bash
mkdir -p ~/wikidumps && cd ~/wikidumps
curl -LO https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles-multistream.xml.bz2
curl -LO https://dumps.wikimedia.org/enwiki/latest/enwiki-latest-pages-articles-multistream-index.txt.bz2
cd -
```

Then:

```bash
python tools/wikimine.py events --from 500                   # the project's earliest year
python tools/wikimine.py dump \
  --dump ~/wikidumps/enwiki-latest-pages-articles-multistream.xml.bz2 \
  --index ~/wikidumps/enwiki-latest-pages-articles-multistream-index.txt.bz2 \
  --workers 8                                                # one per CPU core
python tools/wikimine.py extract
python tools/wikimine.py sample --n 30
```

`dump` reads only the parts of the dump that hold event articles (the index says where each one is), so it doesn't unpack all 27 GB. Expect 20–60 minutes on a laptop, mostly reading the index. If `events` times out on a big class, rerun it with `--step 5`.

### Optional: let Claude check each candidate first

```bash
pip install anthropic
export ANTHROPIC_API_KEY=...                                 # or `ant auth login`
python tools/wikimine.py classify --now 20                   # 20 right away, to see what it does
python tools/wikimine.py classify --submit                   # everything, as a batch at half price
python tools/wikimine.py classify --collect                  # later; waits until the batch is done
```

`classify` uses `claude-opus-5-5` at low effort. Pick another model with `--model`, for example `--model claude-haiku-5-5`, which costs much less. Only the sentence is judged, not the model's own knowledge of history. `sample` and `write` use `classified.jsonl` when it exists.

### Writing files for review

```bash
python tools/wikimine.py write --min-score 2
```

This writes `staging/wikimine/links/*.yaml` and stubs in `staging/wikimine/events/` for events not yet in `data/`. Stubs need a summary, threads and regions. Links between two events already in `data/` are the quickest to promote.

## Batches and the sampled check

`extract` puts each candidate in one batch, or holds it back:

| Batch | What is in it |
|---|---|
| `part_of-infobox` | The article's infobox "Part of" field |
| `part_of-text` | "X was part of Y" in a sentence about the article's own event |
| `led_to` | "led to", "caused", "in response to"... with a clear subject (the article's event, or an event named right before the phrase) and dates in order |
| `influenced` | "inspired", "influenced by"... under the same conditions |

Held back: an unclear subject, dates out of order, hedged wording, or an endpoint that Wikidata files only as a "social movement" (often an organisation or an art movement). Held-back candidates stay in `candidates.jsonl` for a person to look at one by one.

**The rule for now (decided November 2026):** a person checks a random sample of each batch, 30 items by default. A batch goes into `data/` only if at least 95% of its sample is correct (`--bar`), and its links go in as `sourced`, never `reviewed`, with a note naming the sample. `sample --score` prints each batch's share correct with a 95% interval; with 30 items, the interval is wide, so a batch that barely clears the bar deserves a second sample.

## Promoting a batch

```bash
python tools/wikimine.py promote --batch part_of-infobox \
  --check staging/wikimine/checks/2026-11-25.json \
  --events staging/wikimine/first-batch-events.yaml \
  --map Q126065=iranian-revolution-1979 --skip Q3266633 Q3108868
```

`promote` refuses a batch whose sample in the check record (`staging/wikimine/checks/`) missed the bar. It writes the batch's links whose part is already in `data/`, the larger events they name, and links among those. Each new event needs an entry in `--events`, written by hand from the article's lead: summary, dates, threads, regions, importance and quotes; `promote` checks every quote against the lead and stops if one is missing. `--map` gives Wikidata ids to items in `data/` that lack one, `--skip` leaves out events (duplicates, or a Wikidata item whose article redirects elsewhere), and a pair where each is "part of" the other is left out. Links go in as `sourced`, with a note naming the batch and its sample.

First batch (25 November 2026): 119 `part_of` links from infoboxes and 46 new events (wars, fronts and theatres such as the Western Front, the Pacific War and the Iran–Israel proxy conflict). Left out: Nakba (our "Palestinian exodus (Nakba)" item already carries the name), Atlantic Revolutions (its article redirects to "Age of Revolution"), and the Chinese Civil War ↔ Chinese Communist Revolution pair.

## What it does not do

- **It never writes to `data/`.** Promotion is a separate step, after the sampled check above.
- Quotes from the `dump` and default `fetch` paths come from wikitext. Sentences with a template the tool can't render (`{{convert}}`, `{{circa}}`...) are skipped, so the remaining quotes should match the page, but run the usual quote check when you promote. `fetch --html` uses the rendered page instead (one request per article, slower).
- The direction comes from the phrase: "X led to Y" gives X → Y, "X, in response to Y" gives Y → X. When no event is named before the phrase, the article's own event is taken to be the subject. That is the main source of errors, and it is why the sample matters.
- Hedged sentences ("some historians argue", "may have") are kept but flagged. They are candidates for `contested` links with positions, which a person has to write.
- Wikidata's "has cause" and "has effect" statements are used only to rank candidates, never as a source.
