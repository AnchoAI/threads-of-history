# Instructions for AI agents (Codex and others)

Read `CLAUDE.md` first. It is the source of truth for this project's principles, data model and roadmap. `README.md` documents the data format. This file only adds the working rules every agent must follow.

## Commands

```sh
pip install -r requirements-dev.txt
python tools/validate.py            # must report 0 errors before you finish
python tools/validate.py --verbose  # list warnings too
python tools/build.py               # must succeed
python -m pytest -q                 # must pass
```

## Hard rules

1. **Never write a link, date or figure from your own memory.** Every claim needs a source you actually opened, and the source itself must make the claim. If you cannot open a source, leave the item `unverified` and say so in `review.notes`.
2. **Never set `review.status: reviewed`.** Only a person can. The highest status an agent may set is `sourced`: every source has a `quote` that you copied from the page, and contested positions each have a source.
3. **Quotes are short excerpts copied exactly from the source,** never paraphrased and never full text. Keep them under about 300 characters.
4. **Archive every source you add** (`archive_url`), using `tools/archive.py` once it exists.
5. **Contested means contested.** If serious sources disagree, mark the link `contested` and record each side with its own source. Do not pick a winner.
6. **Neutral, plain wording.** Summaries say what happened and who claims what, in one or two sentences.
7. **Record what you could not verify** in `review.notes`, and list it in your pull request description.
8. **Do not import data from datasets whose licence is `restricted` or not yet checked.** Check and record the licence first (`data/datasets/`).
9. **Keep pull requests small**: one task or one batch each. Do not change `schema/` or `tools/validate.py` in a data pull request. If the format needs to change, propose it in a separate pull request that explains why.
10. **Do not edit `viewer/`.** Other work is happening there.

## Larger tasks

Written handoffs live in `docs/tasks/`. Follow them in order, and stop at the end of each task so a person can review the pull request.
