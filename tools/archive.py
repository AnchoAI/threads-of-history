#!/usr/bin/env python3
"""Fill missing source archive_url fields without reserializing YAML.

Availability API: https://archive.org/help/wayback_api.php
Save Page Now: https://web.archive.org/save/
Only confirmed captures are written; pending jobs are kept in .cache/archives.json.
"""
from __future__ import annotations

import argparse
import datetime as dt
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import re
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import yaml
from yaml.nodes import MappingNode, ScalarNode, SequenceNode

ROOT = Path(__file__).resolve().parents[1]
AVAILABLE = "https://archive.org/wayback/available"
SAVE = "https://web.archive.org/save/"


def sources(node, inside=False, seen=None):
    """Find source mappings at every nesting depth, including aliased sources."""
    seen = set() if seen is None else seen
    if node is None or (id(node), inside) in seen:
        return
    seen.add((id(node), inside))
    if isinstance(node, MappingNode):
        fields = {key.value: value for key, value in node.value}
        if len(fields) != len(node.value):
            raise ValueError("duplicate YAML mapping keys")
        if inside and "<<" in fields:
            raise ValueError("merged source mappings require manual handling")
        if inside and "url" in fields:
            url = fields["url"]
            archive = fields.get("archive_url")
            if isinstance(url, ScalarNode) and url.value and (
                archive is None or archive.tag.endswith(":null") or archive.value == ""
            ):
                yield node, fields
        for key, value in node.value:
            yield from sources(value, inside or key.value == "sources", seen)
    elif isinstance(node, SequenceNode):
        for value in node.value:
            yield from sources(value, inside, seen)


def target_date(value=None):
    if value is None:
        return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%d")
    value = str(value)
    if "T" in value:
        moment = dt.datetime.fromisoformat(value)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=dt.timezone.utc)
        return moment.astimezone(dt.timezone.utc).strftime("%Y%m%d%H%M%S")
    if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
        raise ValueError(f"invalid source date: {value}")
    parts = [int(part) for part in value.split("-")]
    date = dt.date(*(parts + [1] * (3 - len(parts))))
    return date.strftime("%Y%m%d")


def snapshot_url(value):
    """Accept only a concrete Wayback capture, never a save/status URL."""
    if not isinstance(value, str):
        raise ValueError("missing snapshot URL")
    value = urllib.parse.urljoin(SAVE, value)
    parsed = urllib.parse.urlsplit(value)
    if (parsed.scheme not in {"http", "https"} or parsed.netloc != "web.archive.org"
            or not re.match(r"^/web/\d{14}/https?://", parsed.path)):
        raise ValueError(f"not a concrete Wayback snapshot: {value}")
    dt.datetime.strptime(parsed.path.split("/")[2], "%Y%m%d%H%M%S")
    return value.replace("http://web.archive.org/", "https://web.archive.org/", 1)


def edit(text, node, fields, archive):
    """Return a single insertion/replacement span using parser character marks."""
    encoded = json.dumps(snapshot_url(archive))
    old = fields.get("archive_url")
    if old is not None:
        if old.start_mark.index == old.end_mark.index and text[old.start_mark.index - 1] == ":":
            encoded = " " + encoded
        return old.start_mark.index, old.end_mark.index, encoded
    if node.flow_style:
        start = text.index("{", node.start_mark.index, node.end_mark.index) + 1
        return start, start, '"archive_url": ' + encoded + ", "
    key = node.value[0][0]
    start = key.start_mark.index
    newline = "\r\n" if "\r\n" in text else "\n"
    return start, start, "archive_url: " + encoded + newline + " " * key.start_mark.column


def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class Wayback:
    def __init__(self, cache, interval=5, retries=3, timeout=30, cafile=None, offline=False):
        self.cache = Path(cache)
        self.state = json.loads(self.cache.read_text()) if self.cache.exists() else {}
        self.interval, self.retries, self.timeout = interval, retries, timeout
        self.context = ssl.create_default_context(cafile=cafile)
        self.last = None
        self.network_blocked = "offline mode: no cached snapshot" if offline else None

    def remember(self):
        atomic_write(self.cache, (json.dumps(self.state, indent=2, sort_keys=True) + "\n").encode())

    def request(self, url, data=None):
        if self.network_blocked:
            raise ValueError(self.network_blocked)
        for attempt in range(self.retries + 1):
            if self.last is not None:
                time.sleep(max(0, self.interval - (time.monotonic() - self.last)))
            self.last = time.monotonic()
            request = urllib.request.Request(url, data=data, headers={
                "User-Agent": "ThreadsOfHistory/1.0 (source archiver)",
                "Accept": "application/json",
            })
            try:
                with urllib.request.urlopen(request, timeout=self.timeout, context=self.context) as response:
                    body = response.read()
                    try:
                        payload = json.loads(body)
                    except (ValueError, UnicodeDecodeError):
                        payload = {}
                    if not isinstance(payload, dict):
                        raise ValueError("Wayback returned a non-object JSON response")
                    return payload, response.headers, response.url
            except (urllib.error.URLError, TimeoutError) as error:
                if isinstance(error, urllib.error.HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                    raise
                if attempt == self.retries:
                    if isinstance(error, urllib.error.HTTPError) and error.code == 429:
                        self.network_blocked = "Wayback rate limit exhausted; rerun later (cached results still applied)"
                    raise
                delay = self.interval * 2 ** (attempt + 1)
                if isinstance(error, urllib.error.HTTPError):
                    retry_after = error.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        delay = max(delay, int(retry_after))
                    elif retry_after:
                        try:
                            until = parsedate_to_datetime(retry_after)
                            delay = max(delay, (until - dt.datetime.now(dt.timezone.utc)).total_seconds())
                        except (TypeError, ValueError):
                            pass
                time.sleep(delay)
        raise RuntimeError("unreachable")

    def cached(self, url, date, dated):
        """Return (key, entry). Undated sources are keyed by URL alone, so a rerun
        on a later day (when "today" has moved) still finds results and pending jobs.
        Older caches keyed undated sources by the day of the run; those entries are
        adopted under the new key."""
        key = json.dumps([url, date if dated else None])
        if key in self.state or dated:
            return key, self.state.get(key, {})
        for old_key, entry in list(self.state.items()):
            old_url, old_date = json.loads(old_key)
            if old_url == url and old_date is not None and (entry.get("archive_url") or entry.get("job_id")):
                del self.state[old_key]
                self.state[key] = entry
                self.remember()
                return key, entry
        return key, {}

    def archive(self, url, date, dated=True):
        if urllib.parse.urlsplit(url).scheme not in {"http", "https"}:
            raise ValueError("source URL must use HTTP or HTTPS")
        key, entry = self.cached(url, date, dated)
        if entry.get("archive_url"):
            return snapshot_url(entry["archive_url"])
        if not entry.get("job_id"):
            payload, _, _ = self.request(AVAILABLE + "?" + urllib.parse.urlencode({"url": url, "timestamp": date}))
            snapshots = payload.get("archived_snapshots")
            if not isinstance(snapshots, dict):
                raise ValueError("Availability API returned no archived_snapshots object")
            closest = snapshots.get("closest", {})
            if not isinstance(closest, dict):
                raise ValueError("Availability API returned an invalid closest snapshot")
            if closest.get("available") is True and str(closest.get("status")) == "200":
                result = snapshot_url(closest.get("url"))
                self.state[key] = {"archive_url": result}
                self.remember()
                return result
            payload, headers, final = self.request(SAVE, urllib.parse.urlencode({"url": url}).encode())
            candidate = headers.get("Content-Location") or headers.get("Location")
            if candidate or "/web/" in final:
                result = snapshot_url(candidate or final)
                self.state[key] = {"archive_url": result}
                self.remember()
                return result
            if not payload.get("job_id"):
                raise ValueError("Save Page Now returned no capture or job id: " + str(payload))
            entry = {"job_id": payload["job_id"]}
            self.state[key] = entry
            self.remember()
        # Persist jobs before polling so interruption never loses an accepted job.
        for _ in range(12):
            payload, _, _ = self.request(SAVE + "status/" + urllib.parse.quote(str(entry["job_id"]), safe=""))
            if payload.get("status") == "success":
                original = payload.get("original_url")
                if not original:
                    raise ValueError("completed job has no original_url")
                result = snapshot_url(f"https://web.archive.org/web/{payload.get('timestamp')}/{original}")
                self.state[key] = {"archive_url": result}
                self.remember()
                return result
            if payload.get("status") == "error":
                del self.state[key]
                self.remember()
                raise ValueError("Save Page Now failed: " + str(payload.get("message", payload)))
        raise ValueError("capture still pending; rerun to resume its saved job")


def process(path, client=None, dry_run=False):
    original = path.read_bytes()
    text = original.decode("utf-8")
    pending = list(sources(yaml.compose(text)))
    edits, failures = [], 0
    for node, fields in pending:
        url = fields["url"].value
        try:
            source_date = fields["date"].value if "date" in fields else None
            date = target_date(source_date)
            if dry_run:
                print(f"WOULD ARCHIVE {path}: {url} (nearest {date})", flush=True)
                continue
            archive = client.archive(url, date, dated=source_date is not None)
            edits.append(edit(text, node, fields, archive))
            print(f"ARCHIVED {path}: {url} -> {archive}", flush=True)
        except (ValueError, OSError) as error:
            failures += 1
            print(f"FAILED {path}: {url}: {error}", flush=True)
    if edits:
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        yaml.safe_load(text)  # Refuse to write if an unsupported layout broke syntax.
        if path.read_bytes() != original:
            raise ValueError(f"file changed during archiving: {path}")
        atomic_write(path, text.encode("utf-8"))
    return len(pending), len(edits), failures


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", action="append", type=Path, help="file/directory under data/; repeatable")
    parser.add_argument("--dry-run", action="store_true", help="list missing archives; no network or writes")
    parser.add_argument("--offline", action="store_true", help="apply only confirmed cached results; no network")
    parser.add_argument("--cache", type=Path, default=ROOT / ".cache/archives.json")
    parser.add_argument("--interval", type=float, default=5, help="minimum seconds between requests (default: 5)")
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--ca-bundle", help="trusted CA bundle; TLS verification always stays enabled")
    args = parser.parse_args(argv)
    if args.interval <= 0 or args.retries < 0 or args.timeout <= 0:
        parser.error("interval/timeout must be positive and retries nonnegative")
    files = set()
    for path in args.path or [ROOT / "data"]:
        path = path.resolve()
        if not path.is_relative_to(ROOT / "data") or not path.exists():
            parser.error(f"path must exist under {ROOT / 'data'}: {path}")
        files.update(p for p in (path.rglob("*") if path.is_dir() else [path])
                     if p.suffix.lower() in {".yaml", ".yml", ".json"} and p.is_file())
    client = None if args.dry_run else Wayback(args.cache, args.interval, args.retries, args.timeout, args.ca_bundle, args.offline)
    totals = [0, 0, 0]
    for path in sorted(files):
        try:
            counts = process(path, client, args.dry_run)
            totals = [a + b for a, b in zip(totals, counts)]
        except (ValueError, OSError, yaml.YAMLError) as error:
            totals[2] += 1
            print(f"FAILED {path}: {error}", flush=True)
    print(f"Sources missing archives: {totals[0]}; added: {totals[1]}; failures: {totals[2]}")
    return int(totals[2] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
