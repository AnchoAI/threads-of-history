# Mining Wikipedia for links

`tools/wikimine.py` finds sentences in Wikipedia's event articles that state a connection to another event ("led to", "in response to", "part of") and turns them into proposed links. Each proposal quotes the sentence and cites the article, so it can be checked against the page. Everything lands in `staging/wikimine/` (gitignored), marked `unverified`. Nothing goes into `data/` until a person has checked it.

## Steps

| Step | Command | What it does | Output |
|---|---|---|---|
| 1 | `events` | Asks Wikidata for wars, battles, revolutions, coups, treaties, protests, massacres, pandemics and the like (24 classes) with a date and an English article, plus Wikidata's own "part of", "has cause" and "has effect" statements between them | `events.jsonl` |
| 2 | `fetch` or `dump` | Gets those articles, either from the API (good up to a few thousand) or from a downloaded dump (all of them), and keeps the sentences that contain links | `sentences.jsonl` |
| 3 | `extract` | Keeps sentences where a connecting phrase sits next to a link to another event, works out the direction from the phrase, follows redirects, checks the dates and compares with Wikidata | `candidates.jsonl` |
| 4 | `classify` (optional) | Claude reads each sentence and says whether it really states the link, its type and direction. Needs an Anthropic API key | `classified.jsonl` |
| 5 | `sample` | Picks 100 at random into a checklist for a person; `sample --score FILE` gives the precision | `sample-DATE.md` |
| 6 | `write` | Writes YAML link files, plus stub files for events not yet in `data/` | `links/`, `events/` |

## Running it locally

You need Python 3.10+, about 30 GB of free disk for the full run and an internet connection (Wikidata, and the API for redirects).

```bash
git clone https://github.com/AnchoAI/threads-of-history.git
cd threads-of-history
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt mwparserfromhell
```

### A pilot (an hour or so, no download)

```bash
python tools/wikimine.py events --from 1900                  # ~15–30 min, all 24 classes
python tools/wikimine.py fetch --limit 3000                  # the 3,000 events with the most language versions
python tools/wikimine.py extract
python tools/wikimine.py sample --n 100
```

Open `staging/wikimine/sample-<date>.md`, tick one box per item, then run `python tools/wikimine.py sample --score staging/wikimine/sample-<date>.md`.

### Everything (an evening)

Download the current English dump and its index from <https://dumps.wikimedia.org/enwiki/latest/>, about 27 GB in total:

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
python tools/wikimine.py sample --n 100
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

## What it does not do

- **It never writes to `data/`.** Promotion is a separate, human step. One thing still needs deciding: whether a person checks every mined link (the rule in `CLAUDE.md` today), or a random sample is checked per batch and the batch goes in only if its precision clears a bar. Until that is decided, mined links go into `data/` one by one, after a person has checked each.
- Quotes from the `dump` and default `fetch` paths come from wikitext. Sentences with a template the tool can't render (`{{convert}}`, `{{circa}}`...) are skipped, so the remaining quotes should match the page, but run the usual quote check when you promote. `fetch --html` uses the rendered page instead (one request per article, slower).
- The direction comes from the phrase: "X led to Y" gives X → Y, "X, in response to Y" gives Y → X. When no event is named before the phrase, the article's own event is taken to be the subject. That is the main source of errors, and it is why the sample matters.
- Hedged sentences ("some historians argue", "may have") are kept but flagged. They are candidates for `contested` links with positions, which a person has to write.
- Wikidata's "has cause" and "has effect" statements are used only to rank candidates, never as a source.
