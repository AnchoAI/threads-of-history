"""Mine English Wikipedia for proposed links between events.

  python tools/wikimine.py events  [--from 1900 --to 2027]        Wikidata: event articles with dates
  python tools/wikimine.py fetch   [--limit N]                    REST API: fetch those articles (a pilot)
  python tools/wikimine.py dump    --dump FILE --index FILE       Or read them from a downloaded dump (the full run)
  python tools/wikimine.py extract                                Sentences with a connecting phrase -> candidates
  python tools/wikimine.py classify --now 20 | --submit | --collect   Optional: Claude checks each candidate
  python tools/wikimine.py sample  [--n 100] | --score FILE       A random sample for a person to check
  python tools/wikimine.py write   [--min-score 2]                YAML link files for review

Everything goes to staging/wikimine/ (gitignored) and nothing touches data/. A candidate is a
sentence, from the article about one event, that links to the article about another event and
uses a connecting phrase ("led to", "in response to", "part of"). The quote is the sentence and
the source is the article, so each proposal can be checked against the page it came from. All
output is `unverified`: a person accepts or rejects it before anything is promoted to data/.

See staging/wikimine.md for how to run it locally on the whole of Wikipedia.
"""
from __future__ import annotations

import argparse
import bz2
import datetime as dt
import gzip
import hashlib
import html
import json
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "staging" / "wikimine"
CACHE = ROOT / ".cache" / "wikimine"
UA = "ThreadsOfHistory/0.1 (https://github.com/AnchoAI/threads-of-history; wikimine)"
SPARQL = "https://query.wikidata.org/sparql"
REST = "https://en.wikipedia.org/api/rest_v1/page/html/"
ACTION = "https://en.wikipedia.org/w/api.php"

# Wikidata classes whose instances (and instances of their subclasses) count as events.
CLASSES = {
    "war": "Q198", "armed conflict": "Q350604", "battle": "Q178561", "siege": "Q188055",
    "military operation": "Q645883", "revolution": "Q10931", "coup d'etat": "Q45382",
    "rebellion": "Q124734", "riot": "Q124757", "protest": "Q273120", "massacre": "Q3199915",
    "genocide": "Q41397", "assassination": "Q3882219", "terrorist attack": "Q2223653",
    "treaty": "Q131569", "pandemic": "Q12184", "epidemic": "Q44512", "famine": "Q168247",
    "financial crisis": "Q114380", "scandal": "Q1150958", "political crisis": "Q3002772",
    "diplomatic crisis": "Q1371150", "independence declaration": "Q1464916", "referendum": "Q43109",
}


# --- small helpers ------------------------------------------------------------------------------

def get(url: str, params: dict | None = None, accept: str | None = None, tries: int = 6) -> bytes:
    if params:
        url += ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    headers = {"User-Agent": UA, "Accept-Encoding": "gzip"}
    if accept:
        headers["Accept"] = accept
    for i in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as r:
                body = r.read()
                return gzip.decompress(body) if r.headers.get("Content-Encoding") == "gzip" else body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise
            if e.code not in (429, 500, 502, 503, 504) or i == tries - 1:
                raise
            wait = float(e.headers.get("Retry-After") or 2 ** (i + 1))
        except (urllib.error.URLError, TimeoutError):
            if i == tries - 1:
                raise
            wait = 2 ** (i + 1)
        time.sleep(min(wait, 120))
    raise RuntimeError("unreachable")


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def norm_title(t: str) -> str:
    """Wikipedia's canonical form: spaces not underscores, no fragment, first letter capital."""
    t = urllib.parse.unquote(t).split("#")[0].replace("_", " ").strip()
    t = re.sub(r"\s+", " ", t)
    return t[:1].upper() + t[1:]


def wiki_url(title: str) -> str:
    return "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"), safe="()',-.:_")


def year(s: str | None) -> int | None:
    m = re.match(r"^(-?\d+)", s or "")
    return int(m.group(1)) if m else None


def read_jsonl(path: Path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            n += 1
    return n


def load_events(out: Path = OUT) -> dict:
    path = out / "events.jsonl"
    if not path.exists():
        raise SystemExit(f"{rel(path)} not found: run `python tools/wikimine.py events` first")
    return {e["qid"]: e for e in read_jsonl(path)}


def known_items(root: Path = ROOT) -> dict:
    """Wikidata id -> our item id, for everything already in data/."""
    out = {}
    for path in (root / "data").glob("*/*.yaml"):
        try:
            d = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError:
            continue
        if isinstance(d, dict) and str(d.get("wikidata", "")).startswith("Q"):
            out[d["wikidata"]] = d["id"]
    return out


def known_pairs(root: Path = ROOT) -> set:
    out = set()
    for path in (root / "data" / "links").glob("*.yaml"):
        d = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.add((d["from"], d["to"]))
        out.add((d["to"], d["from"]))
    return out


# --- 1. events: the skeleton from Wikidata -------------------------------------------------------

EVENT_QUERY = """
SELECT ?e ?article ?label ?start ?point ?end ?sitelinks WHERE {
  ?e wdt:P31/wdt:P279* wd:%(cls)s .
  ?article schema:about ?e ; schema:isPartOf <https://en.wikipedia.org/> ; schema:name ?label .
  OPTIONAL { ?e wdt:P580 ?start }
  OPTIONAL { ?e wdt:P585 ?point }
  OPTIONAL { ?e wdt:P582 ?end }
  ?e wikibase:sitelinks ?sitelinks .
  BIND(COALESCE(?start, ?point) AS ?s)
  FILTER(BOUND(?s) && YEAR(?s) >= %(lo)d && YEAR(?s) < %(hi)d)
}"""

RELATION_QUERY = """
SELECT ?e ?p ?o WHERE {
  VALUES ?e { %s }
  VALUES ?p { wdt:P361 wdt:P828 wdt:P1542 }
  ?e ?p ?o .
}"""
RELATIONS = {"P361": "part_of", "P828": "has_cause", "P1542": "has_effect"}


def sparql(query: str) -> list[dict]:
    body = get(SPARQL, {"query": query, "format": "json"}, accept="application/sparql-results+json")
    return json.loads(body)["results"]["bindings"]


def cmd_events(args) -> None:
    events: dict[str, dict] = {}
    step = args.step
    for name, cls in CLASSES.items():
        if args.classes and name not in args.classes:
            continue
        got = 0
        for lo in range(args.start, args.end, step):
            hi = min(lo + step, args.end)
            try:
                rows = sparql(EVENT_QUERY % {"cls": cls, "lo": lo, "hi": hi})
            except urllib.error.HTTPError as e:
                print(f"  {name} {lo}-{hi}: {e} (try a smaller --step)", file=sys.stderr)
                continue
            for r in rows:
                qid = r["e"]["value"].rsplit("/", 1)[1]
                start = (r.get("start") or r.get("point"))["value"][:10]
                end = r["end"]["value"][:10] if "end" in r else None
                e = events.get(qid)
                if e is None:
                    events[qid] = e = {"qid": qid, "title": norm_title(r["label"]["value"]), "start": start,
                                       "end": end, "sitelinks": int(r["sitelinks"]["value"]), "classes": []}
                    got += 1
                else:   # several dates on one item: keep the earliest start and the latest end
                    if (year(start) or 0) < (year(e["start"]) or 0):
                        e["start"] = start
                    if end and (not e["end"] or (year(end) or 0) > (year(e["end"]) or 0)):
                        e["end"] = end
                if name not in e["classes"]:
                    e["classes"].append(name)
            time.sleep(1)
        print(f"{name}: {got} new events", file=sys.stderr)
    # Wikidata's own part of / has cause / has effect statements among these events.
    qids = sorted(events)
    for i in range(0, len(qids), 200):
        for r in sparql(RELATION_QUERY % " ".join("wd:" + q for q in qids[i:i + 200])):
            o = r["o"]["value"].rsplit("/", 1)[-1]
            if o in events:
                prop = RELATIONS[r["p"]["value"].rsplit("/", 1)[1]]
                events[r["e"]["value"].rsplit("/", 1)[1]].setdefault(prop, []).append(o)
        time.sleep(1)
    n = write_jsonl(args.out / "events.jsonl", sorted(events.values(), key=lambda e: -e["sitelinks"]))
    print(f"wrote {n} events to {rel(args.out / 'events.jsonl')}")


# --- 2a. fetch: articles from the REST API (fine for a few thousand) -----------------------------

def page_cache(title: str, kind: str) -> Path:
    return CACHE / kind / (hashlib.sha1(title.encode()).hexdigest() + ".gz")


def cmd_fetch(args) -> None:
    events = sorted(load_events(args.out).values(), key=lambda e: -e["sitelinks"])
    if args.min_sitelinks:
        events = [e for e in events if e["sitelinks"] >= args.min_sitelinks]
    if args.limit:
        events = events[:args.limit]
    kind = "html" if args.html else "wikitext"
    missing = [e for e in events if not page_cache(e["title"], kind).exists()]
    if args.html:   # Parsoid HTML, one request per article: closest to the page as shown
        for i, e in enumerate(missing):
            try:
                body = get(REST + urllib.parse.quote(e["title"].replace(" ", "_"), safe=""))
            except urllib.error.HTTPError as err:
                print(f"  {e['title']}: {err}", file=sys.stderr)
                continue
            save(page_cache(e["title"], kind), body)
            time.sleep(args.delay)
            if (i + 1) % 100 == 0:
                print(f"  {i + 1}/{len(missing)} fetched", file=sys.stderr)
    else:   # wikitext, 50 articles per request
        for i in range(0, len(missing), 50):
            batch = [e["title"] for e in missing[i:i + 50]]
            d = json.loads(get(ACTION, {"action": "query", "prop": "revisions", "rvprop": "content", "rvslots": "main",
                                        "titles": "|".join(batch), "format": "json", "formatversion": 2}))
            q = d.get("query", {})
            back = {x["to"]: x["from"] for x in q.get("normalized", [])}
            for page in q.get("pages", []):
                if "revisions" in page:
                    title = back.get(page["title"], page["title"])
                    save(page_cache(title, kind), page["revisions"][0]["slots"]["main"]["content"].encode("utf-8"))
            time.sleep(args.delay)
            print(f"  {min(i + 50, len(missing))}/{len(missing)} fetched", file=sys.stderr)
    rows = []
    for e in events:
        path = page_cache(e["title"], kind)
        if path.exists():
            text = gzip.decompress(path.read_bytes()).decode("utf-8")
            for s in (html_sentences(text) if args.html else wikitext_sentences(text)):
                rows.append({"article": e["title"], "qid": e["qid"], **s})
    n = write_jsonl(args.out / "sentences.jsonl", rows)
    print(f"{len(events)} articles ({len(missing)} fetched now, the rest cached): {n} sentences with links")


def save(path: Path, body: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(body))


class _ParsoidText(HTMLParser):
    """Paragraph text and wiki links from Parsoid HTML, skipping references, tables and figures."""
    SKIP = {"table", "style", "script", "figure", "sup", "math"}
    VOID = {"br", "img", "meta", "link", "hr", "wbr", "input", "source", "col", "area", "base", "embed", "param", "track"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.paras: list[tuple[str, str, list]] = []   # (section, text, [(start, end, target)])
        self.section = ""
        self.skip = 0
        self.stack: list[str] = []
        self.buf: list[str] | None = None
        self.links: list = []
        self.link: tuple[int, str] | None = None
        self.heading: list[str] | None = None

    def handle_starttag(self, tag, attrs):
        if tag in self.VOID:
            return
        a = dict(attrs)
        self.stack.append(tag)
        if self.skip or tag in self.SKIP or "mw-ref" in (a.get("class") or "") or "navbox" in (a.get("class") or ""):
            self.skip += 1
            return
        if tag in ("h2", "h3"):
            self.heading = []
        elif tag == "p":
            self.buf, self.links = [], []
        elif tag == "a" and self.buf is not None and a.get("rel") == "mw:WikiLink" and (a.get("href") or "").startswith("./"):
            self.link = (len("".join(self.buf)), norm_title(a["href"][2:]))

    def handle_endtag(self, tag):
        if tag in self.VOID or not self.stack:
            return
        while self.stack and self.stack[-1] != tag:   # tolerate unclosed tags
            self._close(self.stack.pop())
        if self.stack:
            self._close(self.stack.pop())

    def _close(self, tag):
        if self.skip:
            self.skip -= 1
            return
        if tag in ("h2", "h3") and self.heading is not None:
            self.section = "".join(self.heading).strip()
            self.heading = None
        elif tag == "a" and self.link is not None and self.buf is not None:
            start, target = self.link
            end = len("".join(self.buf))
            if end > start and ":" not in target.split(" ")[0][:-1]:   # skip File:, Category: ...
                self.links.append((start, end, target))
            self.link = None
        elif tag == "p" and self.buf is not None:
            text = "".join(self.buf)
            if text.strip():
                self.paras.append((self.section, text, self.links))
            self.buf = None

    def handle_data(self, data):
        if self.skip:
            return
        if self.heading is not None:
            self.heading.append(data)
        elif self.buf is not None:
            self.buf.append(data)


def html_sentences(page: str):
    p = _ParsoidText()
    p.feed(page)
    p.close()
    for section, text, links in p.paras:
        yield from split_sentences(section, text, links)


# --- 2b. dump: the same from a downloaded multistream dump (the full run) -----------------------

def dump_offsets(index: Path, wanted: set[str]) -> dict[int, set[str]]:
    """Read the multistream index (offset:page id:title) and keep the streams holding wanted pages."""
    out: dict[int, set[str]] = defaultdict(set)
    with bz2.open(index, "rt", encoding="utf-8") as f:
        for line in f:
            off, _, title = line.rstrip("\n").split(":", 2)
            if title in wanted:
                out[int(off)].add(title)
    return out


def read_stream(dump: Path, offset: int) -> bytes:
    """One bz2 stream of the multistream dump: about a hundred <page> elements."""
    d = bz2.BZ2Decompressor()
    chunks = []
    with open(dump, "rb") as f:
        f.seek(offset)
        while not d.eof:
            block = f.read(1 << 20)
            if not block:
                break
            chunks.append(d.decompress(block))
    return b"".join(chunks)


def _dump_job(job):
    dump, offset, titles = job
    xml = read_stream(Path(dump), offset).decode("utf-8")
    root = ET.fromstring("<pages>" + xml + "</pages>")
    out = []
    for page in root.iter("page"):
        title = page.findtext("title")
        if title not in titles or page.find("redirect") is not None:
            continue
        text = page.findtext("revision/text") or ""
        out.append((title, list(wikitext_sentences(text))))
    return out


def cmd_dump(args) -> None:
    events = load_events(args.out)
    by_title = {e["title"]: e for e in events.values()}
    print("reading the index (a few minutes)...", file=sys.stderr)
    streams = dump_offsets(args.index, set(by_title))
    jobs = [(str(args.dump), off, titles) for off, titles in sorted(streams.items())]
    print(f"{sum(len(t) for t in streams.values())} of {len(by_title)} articles found in {len(jobs)} streams",
          file=sys.stderr)
    rows = []
    if args.workers > 1:
        from multiprocessing import Pool
        with Pool(args.workers) as pool:
            results = pool.imap_unordered(_dump_job, jobs, chunksize=8)
            rows = _collect(results, by_title, len(jobs))
    else:
        rows = _collect(map(_dump_job, jobs), by_title, len(jobs))
    n = write_jsonl(args.out / "sentences.jsonl", rows)
    print(f"{n} sentences with links")


def _collect(results, by_title, total):
    rows = []
    for i, pages in enumerate(results):
        for title, sents in pages:
            rows += [{"article": title, "qid": by_title[title]["qid"], **s} for s in sents]
        if (i + 1) % 500 == 0:
            print(f"  {i + 1}/{total} streams", file=sys.stderr)
    return rows


def wikitext_sentences(text: str):
    """Plain text with link positions from wikitext. Templates, references, tables, lists are dropped."""
    import mwparserfromhell as mw
    from mwparserfromhell.nodes import Comment, ExternalLink, Heading, HTMLEntity, Tag, Template, Text, Wikilink

    section = ""
    buf: list[str] = []
    links: list = []

    def size():
        return sum(map(len, buf))

    def render(nodes):
        nonlocal section
        for n in nodes:
            if isinstance(n, Text):
                buf.append(str(n.value))
            elif isinstance(n, HTMLEntity):
                buf.append(html.unescape(str(n)))
            elif isinstance(n, Wikilink):
                target = str(n.title).strip()
                if ":" in target.lstrip(":").split(" ")[0][:-1] or target.startswith(":"):
                    continue   # File:, Category:, interwiki
                label = n.text.strip_code() if n.text is not None else target.split("#")[0]
                start = size()
                buf.append(label)
                if label:
                    links.append((start, size(), norm_title(target)))
            elif isinstance(n, ExternalLink):
                if n.title is not None:
                    buf.append(n.title.strip_code())
            elif isinstance(n, Heading):
                flush()
                section = n.title.strip_code().strip()
            elif isinstance(n, Tag):
                tag = str(n.tag).lower()
                if tag in ("ref", "table", "gallery", "math", "references", "timeline", "score", "div"):
                    continue
                if tag == "br":
                    buf.append(" ")
                elif n.wiki_markup in ("*", "#", ";", ":"):
                    buf.append(n.wiki_markup)   # list markers: _paragraphs drops these lines
                elif n.contents is not None:
                    render(n.contents.nodes)
            elif isinstance(n, Template):
                name = str(n.name).strip().lower()
                positional = [p for p in n.params if not p.showkey]
                if name.startswith("lang-") and positional:
                    buf.append(mw.parse(str(positional[0].value)).strip_code())
                elif name in WRAPPERS and len(positional) > max(WRAPPERS[name], -WRAPPERS[name] - 1):
                    buf.append(mw.parse(str(positional[WRAPPERS[name]].value)).strip_code())
                elif name in ("anchor", "-", "clear", "toc limit"):
                    continue
                elif not name.startswith(("efn", "sfn", "refn", "citation", "cite", "harv", "#tag")):
                    buf.append(GAP)   # text the page shows but we can't render: drop the sentence
            elif isinstance(n, Comment):
                continue

    def flush():
        text = "".join(buf)
        sents = []
        for para_text, para_links in _paragraphs(text, links):
            sents += split_sentences(section, para_text, para_links)
        out.extend(sents)
        buf.clear()
        links.clear()

    out: list = []
    render(mw.parse(text).nodes)
    flush()
    return out


GAP = "\x00"
# Templates that only wrap text the page shows, and which parameter that text is in.
WRAPPERS = {"nowrap": 0, "nobr": 0, "small": 0, "big": 0, "nobold": 0, "noitalic": 0, "abbr": 0, "ill": 0,
            "interlanguage link": 0, "vanchor": 0, "lang": 1, "transl": -1, "transliteration": -1, "linktext": 0}


def _paragraphs(text: str, links):
    """Group rendered wikitext into paragraphs (runs of plain lines), dropping list and markup lines."""
    groups, cur, pos = [], [], 0
    for line in text.split("\n"):
        start, pos = pos, pos + len(line) + 1
        s = line.strip(" \t" + GAP)
        if s and s[0] not in "|{}!*#:;=" and not s.startswith("__"):
            cur.append((start, line))
        elif cur:
            groups.append(cur)
            cur = []
    if cur:
        groups.append(cur)
    for g in groups:
        para, ps = "", []
        for start, line in g:
            if para:
                para += " "
            shift = len(para) - start
            para += line
            ps += [(a + shift, b + shift, t) for a, b, t in links if a >= start and b <= start + len(line)]
        lead = len(para) - len(para.lstrip(" \t" + GAP))
        para = para.rstrip(" \t" + GAP)
        yield para[lead:], [(a - lead, b - lead, t) for a, b, t in ps if a >= lead and b <= len(para)]


# --- sentences ----------------------------------------------------------------------------------

ABBREV = re.compile(r"(?:\b(?:[A-Z]|U\.S|U\.K|St|Mr|Mrs|Dr|Gen|Col|Lt|Capt|Sgt|Adm|Gov|Sen|Rep|Jr|Sr|Inc|Co|Ltd|"
                    r"No|vs|c|ca|approx|e\.g|i\.e|Jan|Feb|Mar|Apr|Aug|Sep|Sept|Oct|Nov|Dec)\.)$")
BOUNDARY = re.compile(r"(?<=[.!?])[\"”’)]?\s+(?=[A-Z0-9\"“‘(])")


def split_sentences(section: str, text: str, links) -> list[dict]:
    """Sentences that contain at least one link, each with the links' positions inside it."""
    out, start = [], 0
    cuts = [m.end() for m in BOUNDARY.finditer(text) if not ABBREV.search(text[:m.start()].rstrip("\"”’)"))]
    for end in cuts + [len(text)]:
        raw = text[start:end]
        lead = len(raw) - len(raw.lstrip())
        sent = raw.strip()
        s0 = start + lead
        ls = [[a - s0, b - s0, t] for a, b, t in links if a >= s0 and b <= s0 + len(sent)]
        if ls and 20 <= len(sent) <= 600 and GAP not in sent:
            out.append({"section": section, "text": sent, "links": ls})
        start = end
    return out


# --- 3. extract: connecting phrases -> candidate links -------------------------------------------

# (phrase, link type, direction). "forward": the thing before the phrase -> the thing after it.
# "backward": the thing after the phrase -> the thing before it ("X, in response to Y": Y -> X).
CUES = [
    (r"led (?:directly |indirectly |eventually |ultimately )?to", "led_to", "forward"),
    (r"leading (?:directly )?to", "led_to", "forward"),
    (r"resulted in|resulting in|culminated in|culminating in", "led_to", "forward"),
    (r"(?:directly )?(?:caused|triggered|sparked|precipitated|provoked|prompted|instigated)(?! by)", "led_to", "forward"),
    (r"contributed (?:directly |significantly )?to|paved the way for|gave rise to|set the stage for", "led_to", "forward"),
    (r"was a (?:major |key |direct |primary )?(?:cause|catalyst|trigger) (?:of|for)", "led_to", "forward"),
    (r"in (?:direct )?response to|in reaction to|in retaliation for|as a (?:direct )?(?:result|consequence) of", "led_to", "backward"),
    (r"(?:was |were )?(?:caused|triggered|sparked|precipitated|provoked|prompted) by", "led_to", "backward"),
    (r"in the (?:wake|aftermath) of|(?:a|the) (?:direct )?(?:result|consequence) of", "led_to", "backward"),
    (r"(?:was |were )?(?:inspired|influenced) by", "influenced", "backward"),
    (r"(?:inspired|influenced)(?! by)", "influenced", "forward"),
    (r"(?:was |were |formed |is )?(?:a |an )?(?:part|phase|theatre|theater|campaign|front|episode) of", "part_of", "forward"),
]
CUE_RE = [(re.compile(r"\b(?:" + p + r")\b", re.I), t, d) for p, t, d in CUES]
NEGATION = re.compile(r"\b(?:not|never|no|nor|neither|denied|deny|rather than)\b[^.;]{0,25}$", re.I)
HEDGE = re.compile(r"\b(?:may have|might have|could have|possibly|perhaps|arguably|allegedly|reportedly|"
                   r"some (?:historians|scholars|observers|analysts)|it (?:has been|is) (?:argued|claimed|suggested|believed)|"
                   r"is (?:believed|thought|said)|according to some|disputed|controversial|speculat\w+)\b", re.I)
NEAR = 90      # characters between the phrase and the linked event it points at


def resolve_links(rows: list[dict], titles: dict[str, str], offline: bool) -> dict[str, str]:
    """Link target -> event qid, following redirects through the API (cached) for unknown targets."""
    cache_path = CACHE / "redirects.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    unknown = sorted({l[2] for r in rows for l in r["links"] if l[2] not in titles and l[2] not in cache})
    if unknown and not offline:
        print(f"resolving {len(unknown)} link targets through the API...", file=sys.stderr)
        for i in range(0, len(unknown), 50):
            batch = unknown[i:i + 50]
            d = json.loads(get(ACTION, {"action": "query", "redirects": 1, "titles": "|".join(batch),
                                        "format": "json", "formatversion": 2}))
            q = d.get("query", {})
            hop = {x["from"]: x["to"] for x in q.get("normalized", [])}
            redir = {x["from"]: x["to"] for x in q.get("redirects", [])}
            for t in batch:
                u = hop.get(t, t)
                cache[t] = redir.get(u, u)
            if (i // 50) % 20 == 19 or i + 50 >= len(unknown):
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(json.dumps(cache))
                print(f"  {min(i + 50, len(unknown))}/{len(unknown)}", file=sys.stderr)
            time.sleep(0.1)
    return {t: titles[cache.get(t, t)] for t in {l[2] for r in rows for l in r["links"]} if cache.get(t, t) in titles}


EVENT_NOUN = (r"battles?|wars?|conflict|coup|putsch|revolution|treaty|agreement|accord|pact|armistice|crisis|uprising|"
              r"rebellion|revolt|insurgency|protests?|demonstrations?|massacre|siege|offensive|operation|campaign|"
              r"invasion|landing|attack|bombing|assassination|killing|genocide|pandemic|epidemic|outbreak|famine|"
              r"election|referendum|scandal|affair|movement|strikes?|riots?|declaration|conference|incident|events?|"
              r"fighting|defeat|victory|occupation|intervention|blockade")
SUBJECT = re.compile(r"^(?:(?:however|meanwhile|eventually|ultimately|initially|subsequently|thus|in turn|"
                     r"in \d{4}|on [^,]{1,30}|by [^,]{1,30}|after [^,]{1,40}),\s*)?"
                     r"(?:(?P<pro>it|this)(?:\s+\w+){0,3}\s*$|its (?:\w+ ){0,2}(?:outcome|failure|success|aftermath)\b|"
                     r"the (?:[\w-]+ ){0,3}?(?P<noun>" + EVENT_NOUN + r")\b)", re.I)
GENERIC = {"conflict", "fighting"}   # fine for any armed conflict


def article_is_subject(pre: str, article: str, classes=()) -> bool:
    """Does the text before the phrase start with the article's own event: "It", "This", its name,
    or "The battle" when the article is about a battle?"""
    core = re.sub(r"\s*\(.*?\)", "", article).strip()
    if len(core) > 4 and core.lower() in pre.lower():
        return True
    m = SUBJECT.match(pre.strip())
    if not m:
        return False
    noun = (m.group("noun") or "").lower().rstrip("s")
    if not noun:
        return True
    kinds = " ".join(classes).lower()
    return (noun in article.lower() or noun in kinds or
            (noun in GENERIC and any(k in kinds for k in ("war", "conflict", "battle", "siege", "operation"))))


def sentence_candidates(row: dict, link_qid: dict[str, str]) -> list[dict]:
    """Candidate (from, to, type) triples in one sentence.

    The target is the first link after the phrase, and it must be an event: in "led to the fall
    of [Paris] and the [Armistice]" the object is Paris, not the armistice. The other side is the
    nearest event linked before the phrase, or else the article's own event, but only when the
    sentence begins with it ("The battle...", "It...", its name). Otherwise the subject is unclear.
    """
    text, me = row["text"], row["qid"]
    links = sorted((a, b, link_qid.get(t)) for a, b, t in row["links"])
    if not any(q and q != me for _, _, q in links):
        return []
    out = []
    for rx, kind, direction in CUE_RE:
        for m in rx.finditer(text):
            pre = text[:m.start()]
            if NEGATION.search(pre):
                continue
            reach = 30 if kind == "part_of" else NEAR
            after = [l for l in links if l[0] >= m.end()]
            if not after or after[0][0] > m.end() + reach or ";" in text[m.end():after[0][0]]:
                continue
            target = after[0][2]
            if not target or target == me:
                continue
            before = [l for l in links if l[1] <= m.start() and l[1] >= m.start() - NEAR - 30 and ";" not in text[l[1]:m.start()]]
            if before and before[-1][2] and before[-1][2] != me:
                other, subject = before[-1][2], "named"
            elif article_is_subject(pre, row.get("article", ""), row.get("classes", ())):
                other, subject = me, "article"
            else:
                other, subject = me, "unclear"
            if other == target:
                continue
            a, b = (other, target) if direction == "forward" else (target, other)
            out.append({"from": a, "to": b, "type": kind, "cue": m.group(0).lower(),
                        "hedged": bool(HEDGE.search(text)), "subject": subject})
    return out


def date_ok(kind: str, a: dict, b: dict) -> bool:
    ya, yb = year(a.get("start")), year(b.get("start"))
    if ya is None or yb is None:
        return True
    if kind == "led_to":
        return ya <= yb
    if kind == "influenced":
        return ya <= (year(b.get("end")) or 10 ** 4)
    if kind == "part_of":   # the part lies within the whole (a year of slack either side)
        return year(b["start"]) - 1 <= ya <= (year(b.get("end")) or yb) + 1
    return True


def wikidata_agrees(kind: str, a: dict, b: dict) -> bool:
    if kind == "part_of":
        return b["qid"] in a.get("part_of", [])
    return b["qid"] in a.get("has_effect", []) or a["qid"] in b.get("has_cause", [])


def cmd_extract(args) -> None:
    events = load_events(args.out)
    rows = list(read_jsonl(args.out / "sentences.jsonl"))
    titles = {e["title"]: q for q, e in events.items()}
    cue_rows = [dict(r, classes=events[r["qid"]]["classes"]) for r in rows
                if r["qid"] in events and any(rx.search(r["text"]) for rx, _, _ in CUE_RE)]
    link_qid = resolve_links(cue_rows, titles, args.offline)
    pairs: dict[tuple, dict] = {}
    for r in cue_rows:
        for c in sentence_candidates(r, link_qid):
            key = (c["from"], c["to"], c["type"])
            p = pairs.setdefault(key, {"from": c["from"], "to": c["to"], "type": c["type"], "evidence": []})
            ev = {"article": r["article"], "section": r["section"], "sentence": r["text"], "cue": c["cue"],
                  "hedged": c["hedged"], "subject": c["subject"], "url": wiki_url(r["article"])}
            if ev["sentence"] not in [x["sentence"] for x in p["evidence"]]:
                p["evidence"].append(ev)
    known = known_items(args.root)
    have = known_pairs(args.root)
    out = []
    for p in pairs.values():
        a, b = events[p["from"]], events[p["to"]]
        p["from_title"], p["to_title"] = a["title"], b["title"]
        p["from_id"], p["to_id"] = known.get(a["qid"]), known.get(b["qid"])
        p["date_ok"] = date_ok(p["type"], a, b)
        p["wikidata_agrees"] = wikidata_agrees(p["type"], a, b)
        p["in_data"] = bool(p["from_id"] and p["to_id"] and (p["from_id"], p["to_id"]) in have)
        p["hedged"] = all(e["hedged"] for e in p["evidence"])
        p["score"] = score(p)
        p["evidence"] = sorted(p["evidence"], key=lambda e: (e["subject"] == "unclear", e["hedged"]))[:5]
        out.append(p)
    out.sort(key=lambda p: (-p["score"], p["from_title"]))
    n = write_jsonl(args.out / "candidates.jsonl", out)
    by_type = defaultdict(int)
    for p in out:
        by_type[p["type"]] += 1
    print(f"{len(rows)} sentences, {len(cue_rows)} with a connecting phrase -> {n} candidate links "
          f"({', '.join(f'{k} {v}' for k, v in sorted(by_type.items()))}); "
          f"{sum(p['wikidata_agrees'] for p in out)} agree with Wikidata, {sum(not p['date_ok'] for p in out)} fail the date check")


def score(p: dict) -> int:
    """A rough ranking: more sentences, Wikidata agreeing and both events already mapped count for it."""
    s = min(len(p["evidence"]), 3) + 2 * p["wikidata_agrees"] + bool(p["from_id"] and p["to_id"])
    if p["hedged"]:
        s -= 1
    if all(e["subject"] == "unclear" for e in p["evidence"]):
        s -= 2
    if not p["date_ok"]:
        s -= 3
    if any(e["article"] in (p["from_title"], p["to_title"]) for e in p["evidence"]):
        s += 1   # stated in the article about one of the two events
    return s


# --- 4. classify: optional check by Claude ------------------------------------------------------

CLASSIFY_SYSTEM = """You check proposed links for a sourced map of how historical events connect.

You get two events, A and B, and one sentence from an English Wikipedia article. Decide only what the sentence itself states. Do not use your own knowledge of history: if the sentence does not say it, the answer is no, even when the link is true.

- led_to: the sentence says one event caused, led to, prompted or was a response to the other.
- influenced: the sentence says one shaped attitudes, ideas or behaviour that bore on the other, without saying it caused it.
- part_of: the sentence says one event was a part, phase, campaign or theatre of the other.
- none: the sentence mentions both but states no such connection, or the connection is between other things.

direction is a_to_b when A is the cause, the influence or the part; b_to_a when B is. hedged is true when the sentence attributes the claim to some people or marks it as uncertain or disputed. reason: at most 25 words."""

CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "stated": {"type": "boolean"},
        "type": {"type": "string", "enum": ["led_to", "influenced", "part_of", "none"]},
        "direction": {"type": "string", "enum": ["a_to_b", "b_to_a", "none"]},
        "hedged": {"type": "boolean"},
        "reason": {"type": "string"},
    },
    "required": ["stated", "type", "direction", "hedged", "reason"],
    "additionalProperties": False,
}


def classify_params(p: dict, events: dict, model: str, effort: str) -> dict:
    a, b, ev = events[p["from"]], events[p["to"]], p["evidence"][0]
    user = (f"A: {a['title']} ({a['start'][:4]}{'–' + a['end'][:4] if a.get('end') else ''})\n"
            f"B: {b['title']} ({b['start'][:4]}{'–' + b['end'][:4] if b.get('end') else ''})\n\n"
            f"From the Wikipedia article \"{ev['article']}\"{', section ' + repr(ev['section']) if ev['section'] else ''}:\n"
            f"\"{ev['sentence']}\"")
    return {"model": model, "max_tokens": 2048,
            "system": [{"type": "text", "text": CLASSIFY_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": CLASSIFY_SCHEMA}},
            "messages": [{"role": "user", "content": user}]}


def apply_verdict(p: dict, v: dict | None) -> dict:
    p = dict(p, verdict=v)
    if v and v["stated"] and v["type"] != "none":
        if v["direction"] == "b_to_a":
            p["from"], p["to"] = p["to"], p["from"]
            p["from_title"], p["to_title"] = p["to_title"], p["from_title"]
            p["from_id"], p["to_id"] = p["to_id"], p["from_id"]
        p["type"] = v["type"]
        p["hedged"] = v["hedged"]
    return p


def verdict_text(msg) -> dict | None:
    if msg.stop_reason != "end_turn":   # refusal or max_tokens: leave it for a person
        return None
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def cmd_classify(args) -> None:
    import anthropic
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    client = anthropic.Anthropic()
    events = load_events(args.out)
    cands = [p for p in read_jsonl(args.out / "candidates.jsonl") if not p["in_data"]]
    if args.min_score is not None:
        cands = [p for p in cands if p["score"] >= args.min_score]
    state_path = args.out / "classify-batches.json"
    if args.now:   # a small synchronous run, to see what it does before paying for a batch
        out = []
        for p in cands[:args.now]:
            msg = client.messages.create(**classify_params(p, events, args.model, args.effort))
            v = verdict_text(msg)
            out.append(apply_verdict(p, v))
            print(f"{p['from_title']} -> {p['to_title']} [{p['type']}]: {v}")
        write_jsonl(args.out / "classified.jsonl", out)
        return
    if args.submit:
        ids = []
        for i in range(0, len(cands), 50_000):
            chunk = cands[i:i + 50_000]
            batch = client.messages.batches.create(requests=[
                Request(custom_id=f"c{i + j}", params=MessageCreateParamsNonStreaming(**classify_params(p, events, args.model, args.effort)))
                for j, p in enumerate(chunk)])
            ids.append(batch.id)
            print(f"submitted batch {batch.id} ({len(chunk)} candidates)")
        state_path.write_text(json.dumps({"batches": ids, "min_score": args.min_score, "count": len(cands)}))
        print("run `python tools/wikimine.py classify --collect` later (most batches finish within an hour)")
        return
    if args.collect:
        state = json.loads(state_path.read_text())
        verdicts: dict[int, dict | None] = {}
        for bid in state["batches"]:
            while (b := client.messages.batches.retrieve(bid)).processing_status != "ended":
                print(f"{bid}: {b.request_counts.processing} still processing; waiting...", file=sys.stderr)
                time.sleep(60)
            for r in client.messages.batches.results(bid):
                verdicts[int(r.custom_id[1:])] = verdict_text(r.result.message) if r.result.type == "succeeded" else None
        out = [apply_verdict(p, verdicts.get(i)) for i, p in enumerate(cands)]
        write_jsonl(args.out / "classified.jsonl", out)
        ok = sum(1 for p in out if p["verdict"] and p["verdict"]["stated"])
        print(f"{len(out)} classified: {ok} stated, {sum(1 for p in out if p['verdict'] is None)} without a verdict")
        return
    raise SystemExit("choose --now N, --submit or --collect")


# --- 5. sample: a random check by a person ------------------------------------------------------

def cmd_sample(args) -> None:
    if args.score:
        text = Path(args.score).read_text(encoding="utf-8")
        marks = re.findall(r"- \[[xX]\] (correct|wrong direction|wrong type|not stated)", text)
        if not marks:
            raise SystemExit("no ticked boxes found")
        counts = {k: marks.count(k) for k in ("correct", "wrong direction", "wrong type", "not stated")}
        print(f"{len(marks)} checked: " + ", ".join(f"{k} {v} ({v / len(marks):.0%})" for k, v in counts.items()))
        return
    src = args.out / ("classified.jsonl" if (args.out / "classified.jsonl").exists() and not args.raw else "candidates.jsonl")
    rows = [p for p in read_jsonl(src) if not p["in_data"] and (src.name == "candidates.jsonl" or (p["verdict"] and p["verdict"]["stated"]))]
    if args.min_score is not None:
        rows = [p for p in rows if p["score"] >= args.min_score]
    random.Random(args.seed).shuffle(rows)
    lines = [f"# Wikipedia mining: random sample of {min(args.n, len(rows))} from {len(rows)} ({src.name})", "",
             "For each one, open the link and tick one box. Correct means the sentence itself states this link, "
             "in this direction, of this type. Then run `python tools/wikimine.py sample --score THIS_FILE`.", ""]
    for i, p in enumerate(rows[:args.n], 1):
        e = p["evidence"][0]
        verb = {"led_to": "contributed to", "influenced": "influenced", "part_of": "was part of"}[p["type"]]
        lines += [f"## {i}. {p['from_title']} → {verb} → {p['to_title']}", "",
                  f"> {e['sentence']}", "",
                  f"From [{e['article']}]({e['url']}){' (' + e['section'] + ')' if e['section'] else ''}. "
                  f"Phrase: \"{e['cue']}\"" + ("; hedged" if p["hedged"] else "") +
                  ("" if p["date_ok"] else "; dates look wrong") + (f"; Claude: {p['verdict']['reason']}" if p.get("verdict") else ""), "",
                  "- [ ] correct", "- [ ] wrong direction", "- [ ] wrong type", "- [ ] not stated", ""]
    path = args.out / f"sample-{dt.date.today()}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {rel(path)}")


# --- 6. write: YAML for review ------------------------------------------------------------------

def slugify(title: str, start: str | None) -> str:
    s = re.sub(r"\(.*?\)", "", title).lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    y = year(start)
    if y is not None and str(abs(y)) not in s:
        s = f"{s}-{y}" if y >= 0 else f"{s}-{-y}-bce"
    return s or "event"


def link_yaml(p: dict, from_id: str, to_id: str, today: str) -> dict:
    ev = p["evidence"][0]
    notes = [f"Extracted automatically by tools/wikimine.py from the sentence above (phrase \"{ev['cue']}\"); "
             "no person has checked it. Check that the article states this link, its direction and its type."]
    if p["hedged"]:
        notes.append("The sentence hedges or attributes the claim; this may need to be contested, with positions.")
    if not p["date_ok"]:
        notes.append("The Wikidata dates do not fit this direction.")
    if p.get("verdict"):
        notes.append(f"Claude's check: {p['verdict']['reason']}")
    return {
        "id": f"{from_id}--{p['type']}--{to_id}", "from": from_id, "to": to_id, "type": p["type"],
        "confidence": "documented",
        "note": f"{ev['article']} (Wikipedia): \"{ev['cue']}\".",
        "sources": [{"url": ev["url"], "title": ev["article"], "publisher": "Wikipedia",
                     "quote": ev["sentence"][:600], "type": "reference", "accessed": today}
                    for ev in p["evidence"][:2]],
        "review": {"status": "unverified", "notes": notes},
    }


def event_stub(e: dict, slug: str, today: str) -> dict:
    occurred = {"start": e["start"][:10].lstrip("+"), "precision": "day"}
    if e.get("end"):
        occurred["end"] = e["end"][:10].lstrip("+")
    return {"id": slug, "title": e["title"], "summary": "TODO", "occurred": occurred, "threads": [], "regions": [],
            "importance": 2, "wikidata": e["qid"],
            "sources": [{"url": wiki_url(e["title"]), "title": e["title"], "publisher": "Wikipedia",
                         "type": "reference", "accessed": today}],
            "review": {"status": "unverified", "notes": [
                "Stub created by tools/wikimine.py from Wikidata; needs a summary, threads, regions and a checked date "
                "(Wikidata's day precision is often wrong for older events)."]}}


def cmd_write(args) -> None:
    events = load_events(args.out)
    src = args.out / ("classified.jsonl" if (args.out / "classified.jsonl").exists() and not args.raw else "candidates.jsonl")
    rows = [p for p in read_jsonl(src) if not p["in_data"]]
    if src.name == "classified.jsonl":
        rows = [p for p in rows if p.get("verdict") and p["verdict"]["stated"] and p["verdict"]["type"] != "none"]
    rows = [p for p in rows if p["score"] >= args.min_score and (p["date_ok"] or args.keep_bad_dates)]
    today = str(dt.date.today())
    links_dir, events_dir = args.out / "links", args.out / "events"
    for d in (links_dir, events_dir):
        d.mkdir(parents=True, exist_ok=True)
        for old in d.glob("*.yaml"):
            old.unlink()
    slugs: dict[str, str] = {}
    taken = {p.stem for p in (args.root / "data").glob("*/*.yaml")}
    new_events = 0

    def item_id(qid: str, known: str | None) -> str:
        nonlocal new_events
        if known:
            return known
        if qid not in slugs:
            base = slug = slugify(events[qid]["title"], events[qid]["start"])
            n = 2
            while slug in taken:
                slug, n = f"{base}-{n}", n + 1
            taken.add(slug)
            slugs[qid] = slug
            dump_yaml(events_dir / f"{slug}.yaml", event_stub(events[qid], slug, today))
            new_events += 1
        return slugs[qid]

    for p in rows:
        a, b = item_id(p["from"], p["from_id"]), item_id(p["to"], p["to_id"])
        d = link_yaml(p, a, b, today)
        dump_yaml(links_dir / f"{d['id']}.yaml", d)
    print(f"wrote {len(rows)} links to {rel(links_dir)} and {new_events} event stubs to {rel(events_dir)}")


def dump_yaml(path: Path, d: dict) -> None:
    path.write_text(yaml.safe_dump(d, sort_keys=False, allow_unicode=True, width=110), encoding="utf-8")


# --- command line -------------------------------------------------------------------------------

def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=OUT, help="output folder (default staging/wikimine)")
    ap.add_argument("--root", type=Path, default=ROOT, help=argparse.SUPPRESS)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("events", help="event articles with dates, from Wikidata")
    p.add_argument("--from", dest="start", type=int, default=1900)
    p.add_argument("--to", dest="end", type=int, default=dt.date.today().year + 1)
    p.add_argument("--step", type=int, default=10, help="years per query (smaller if queries time out)")
    p.add_argument("--classes", nargs="*", help=f"only these classes: {', '.join(CLASSES)}")
    p.set_defaults(fn=cmd_events)

    p = sub.add_parser("fetch", help="fetch the articles through the REST API")
    p.add_argument("--limit", type=int, help="only the N articles with the most language versions")
    p.add_argument("--min-sitelinks", type=int, default=0)
    p.add_argument("--delay", type=float, default=0.5, help="seconds between requests")
    p.add_argument("--html", action="store_true", help="rendered HTML, one request per article (slower, better quotes)")
    p.set_defaults(fn=cmd_fetch)

    p = sub.add_parser("dump", help="read the articles from a downloaded multistream dump")
    p.add_argument("--dump", type=Path, required=True, help="enwiki-...-pages-articles-multistream.xml.bz2")
    p.add_argument("--index", type=Path, required=True, help="enwiki-...-pages-articles-multistream-index.txt.bz2")
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(fn=cmd_dump)

    p = sub.add_parser("extract", help="connecting phrases -> candidate links")
    p.add_argument("--offline", action="store_true", help="don't resolve redirects through the API")
    p.set_defaults(fn=cmd_extract)

    p = sub.add_parser("classify", help="optional: Claude checks each candidate (needs ANTHROPIC_API_KEY)")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--now", type=int, metavar="N", help="check the top N right away (no batch)")
    g.add_argument("--submit", action="store_true", help="send every candidate as a batch (half price)")
    g.add_argument("--collect", action="store_true", help="wait for the batch and save the verdicts")
    p.add_argument("--model", default="claude-opus-5-5")
    p.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    p.add_argument("--min-score", type=int)
    p.set_defaults(fn=cmd_classify)

    p = sub.add_parser("sample", help="a random sample for a person to check, or score a checked one")
    p.add_argument("--n", type=int, default=100)
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--min-score", type=int)
    p.add_argument("--raw", action="store_true", help="sample candidates even if classified.jsonl exists")
    p.add_argument("--score", metavar="FILE", help="count the ticked boxes in a checked sample")
    p.set_defaults(fn=cmd_sample)

    p = sub.add_parser("write", help="YAML link files (and event stubs) for review")
    p.add_argument("--min-score", type=int, default=2)
    p.add_argument("--raw", action="store_true", help="use candidates even if classified.jsonl exists")
    p.add_argument("--keep-bad-dates", action="store_true")
    p.set_defaults(fn=cmd_write)

    args = ap.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    args.fn(args)


if __name__ == "__main__":
    main()
