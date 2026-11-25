# Contributing

Thanks for helping map how history connects. You can help without writing any code.

## Ways to take part

1. **Discuss an event or a connection.** Open any event in the viewer and choose **Discuss** at the bottom of the panel, or start a thread in [GitHub Discussions](https://github.com/AnchoAI/threads-of-history/discussions). The categories:
   - **Event discussions**: one thread per event or link, created from the viewer.
   - **Proposed connections**: "A contributed to B, and here is a source that says so."
   - **Contested links**: where sources disagree, with each side's sources.
   - **Sources and corrections**: a wrong date, a better source, a quote that doesn't support its claim.
   - **Ideas**: anything about the project itself.
2. **Propose a connection or an event** with the issue forms ([new connection](https://github.com/AnchoAI/threads-of-history/issues/new?template=propose-connection.yml), [new event](https://github.com/AnchoAI/threads-of-history/issues/new?template=propose-event.yml)). A maintainer turns accepted proposals into data.
3. **Edit the data directly** with a pull request, if you are comfortable with git: add or change a YAML file under `data/`, run `python tools/validate.py`, and open the PR. The format is in the [README](README.md#the-data-format).
4. **Review.** Check an item marked "Sourced, not yet reviewed": open its sources, confirm each quote says what is claimed, and say so in its discussion. Maintainers then mark it reviewed.

## The one rule that matters most

**Every connection needs a source that itself states the connection.** Two events being related, or one following the other, is not enough. The quote must say that A led to, contributed to, influenced, or was part of B. If no source says it, it doesn't go on the map, however obvious it seems. This is what keeps the map from becoming a conspiracy board.

Other rules from the [principles](README.md#principles): contested links record who argues each side; every item has when it happened and when it became known; false alarms belong in the data; summaries are plain and neutral; we store short quotes and links, never full texts.

## What happens to your contribution

- The project's own data is dedicated to the public domain under **CC0 1.0** ([LICENSE](LICENSE)); code is under MIT ([LICENSE-CODE](LICENSE-CODE)). By submitting a contribution you agree to release it under those terms, and confirm that you have the right to do so.
- Quotes from sources stay their authors'; we keep them short. Imported datasets keep their own licences ([CREDITS.md](CREDITS.md)).
- New content comes in as "sourced". Only a reviewer marks it "reviewed".

Please follow the [code of conduct](CODE_OF_CONDUCT.md).
