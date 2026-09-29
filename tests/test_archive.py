import io
import json
from unittest.mock import Mock
import urllib.error

import pytest
import yaml

import archive


URL = "https://example.org/source"
SNAP = "https://web.archive.org/web/20240102030405/" + URL


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    monkeypatch.setattr(archive.urllib.request, "urlopen", Mock(side_effect=AssertionError("unexpected network")))


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_nested_sources_preserve_every_other_byte(tmp_path, newline):
    text = """# Header é
sources:
- url: https://example.org/source # keep comment
  title: 'Original quoting'
  quote: |
    Keep this exact text.
known:
  by:
  - sources: [{url: 'https://example.org/source', title: X}]
alternatives:
- sources:
  - url: https://example.org/source
positions:
- sources:
  - url: https://example.org/source
review: {status: unverified}
""".replace("\n", newline)
    path = tmp_path / "item.yaml"
    path.write_bytes(text.encode())
    client = Mock()
    client.archive.return_value = SNAP
    assert archive.process(path, client) == (4, 4, 0)
    result = path.read_bytes().decode()
    # Removing only inserted fields recovers the original bytes, including CRLF.
    import re
    stripped = re.sub(r'archive_url: "[^"]+"' + newline + r' *', '', result)
    stripped = stripped.replace('"archive_url": ' + json.dumps(SNAP) + ', ', '')
    assert stripped == text
    assert yaml.safe_load(result)["review"]["status"] == "unverified"
    client.reset_mock()
    assert archive.process(path, client) == (0, 0, 0)
    client.archive.assert_not_called()


@pytest.mark.parametrize("old", ["null", "''", '""', "~"])
def test_empty_existing_archive_is_replaced_only(tmp_path, old):
    path = tmp_path / "item.yaml"
    text = f"sources: [{{url: '{URL}', archive_url: {old}, title: 'Hi'}}] # comment\n"
    path.write_text(text)
    client = Mock()
    client.archive.return_value = SNAP
    assert archive.process(path, client) == (1, 1, 0)
    assert path.read_text() == text.replace(f"archive_url: {old}", f"archive_url: {json.dumps(SNAP)}")


def test_implicit_null_archive(tmp_path):
    path = tmp_path / "item.yaml"
    text = f"sources:\n- url: {URL}\n  archive_url:\n  title: Keep\n"
    path.write_text(text)
    client = Mock()
    client.archive.return_value = SNAP
    assert archive.process(path, client) == (1, 1, 0)
    assert path.read_text() == text.replace("archive_url:", "archive_url: " + json.dumps(SNAP))


def test_alias_edited_once_and_existing_archive_untouched(tmp_path):
    path = tmp_path / "item.yaml"
    path.write_text(f"sources:\n- &src {{url: '{URL}'}}\n- *src\n- {{url: '{URL}', archive_url: keep}}\n")
    client = Mock()
    client.archive.return_value = SNAP
    assert archive.process(path, client) == (1, 1, 0)
    values = yaml.safe_load(path.read_text())["sources"]
    assert values[0]["archive_url"] == values[1]["archive_url"] == SNAP
    assert values[2]["archive_url"] == "keep"


def test_dry_run_no_network_or_writes(tmp_path):
    path = tmp_path / "item.yaml"
    original = f"sources: [{{url: '{URL}'}}]\n".encode()
    path.write_bytes(original)
    assert archive.process(path, dry_run=True) == (1, 0, 0)
    assert path.read_bytes() == original


def test_failure_leaves_source_untouched(tmp_path):
    path = tmp_path / "item.yaml"
    path.write_text(f"sources: [{{url: '{URL}'}}]\n")
    original = path.read_bytes()
    client = Mock()
    client.archive.side_effect = ValueError("not archived")
    assert archive.process(path, client) == (1, 0, 1)
    assert path.read_bytes() == original


def test_available_snapshot_cached_across_runs(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(return_value=({"archived_snapshots": {"closest": {
        "available": True, "status": "200", "url": SNAP,
    }}}, {}, ""))
    assert client.archive(URL, "20240101") == SNAP
    assert "timestamp=20240101" in client.request.call_args.args[0]
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=AssertionError("cached"))
    assert client.archive(URL, "20240101") == SNAP


def test_save_job_resumes_without_resubmission(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=[({"archived_snapshots": {}}, {}, ""),
                                      ({"job_id": "job-1"}, {}, ""),
                                      TimeoutError("interrupted")])
    with pytest.raises(TimeoutError):
        client.archive(URL, "20240101")
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(return_value=({"status": "success", "timestamp": "20240102030405",
                                        "original_url": URL}, {}, ""))
    assert client.archive(URL, "20240101") == SNAP
    assert client.request.call_args.args[0].endswith("status/job-1")


def test_save_content_location(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=[({"archived_snapshots": {}}, {}, ""),
                                      ({}, {"Content-Location": SNAP}, "")])
    assert client.archive(URL, "20240101") == SNAP
    assert client.request.call_args.args[1] == b"url=https%3A%2F%2Fexample.org%2Fsource"


def test_failed_save_not_recorded_as_archive(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=[({"archived_snapshots": {}}, {}, ""), ({"job_id": "bad"}, {}, ""),
                                      ({"status": "error", "message": "blocked"}, {}, "")])
    with pytest.raises(ValueError, match="blocked"):
        client.archive(URL, "20240101")
    assert client.state == {}


def test_rate_limit_retry_and_backoff(tmp_path, monkeypatch):
    sleep = Mock()
    monkeypatch.setattr(archive.time, "sleep", sleep)
    monkeypatch.setattr(archive.time, "monotonic", lambda: 0)
    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.read.return_value = b'{}'
    response.headers, response.url = {}, URL
    error = urllib.error.HTTPError(URL, 429, "rate limited", {"Retry-After": "20"}, io.BytesIO())
    opener = Mock(side_effect=[error, response])
    monkeypatch.setattr(archive.urllib.request, "urlopen", opener)
    client = archive.Wayback(tmp_path / "cache.json", interval=5)
    client.request(URL)
    assert sleep.call_args_list[0].args == (20,)
    assert sleep.call_args_list[1].args == (5,)
    assert opener.call_count == 2


def test_permanent_http_error_not_retried(tmp_path, monkeypatch):
    error = urllib.error.HTTPError(URL, 403, "blocked", {}, io.BytesIO())
    opener = Mock(side_effect=error)
    monkeypatch.setattr(archive.urllib.request, "urlopen", opener)
    with pytest.raises(urllib.error.HTTPError):
        archive.Wayback(tmp_path / "cache.json").request(URL)
    assert opener.call_count == 1


@pytest.mark.parametrize("value", ["https://evil.org/web/20240102030405/https://example.org",
                                    "https://web.archive.org/save/https://example.org",
                                    "https://web.archive.org/web/latest/https://example.org", None])
def test_reject_unconfirmed_snapshots(value):
    with pytest.raises(ValueError):
        archive.snapshot_url(value)


def test_dates():
    assert archive.target_date("2024") == "20240101"
    assert archive.target_date("2024-02") == "20240201"
    assert archive.target_date("2024-02-29") == "20240229"
    assert archive.target_date("2024-02-29T23:30-04:00") == "20240301033000"
    assert archive.target_date("2024-02-29T23:30") == "20240229233000"
    with pytest.raises(ValueError):
        archive.target_date("2023-02-29")


def test_malformed_availability_does_not_submit_save(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(return_value=({}, {}, ""))
    with pytest.raises(ValueError, match="archived_snapshots"):
        client.archive(URL, "20240101")
    assert client.request.call_count == 1


def test_pending_job_remains_resumable(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=[({"archived_snapshots": {}}, {}, ""),
                                      ({"job_id": "pending"}, {}, "")]
                          + [({"status": "pending"}, {}, "")] * 12)
    with pytest.raises(ValueError, match="still pending"):
        client.archive(URL, "20240101")
    assert next(iter(client.state.values())) == {"job_id": "pending"}


def test_retry_exhaustion(tmp_path, monkeypatch):
    monkeypatch.setattr(archive.time, "sleep", Mock())
    opener = Mock(side_effect=TimeoutError("network timeout"))
    monkeypatch.setattr(archive.urllib.request, "urlopen", opener)
    with pytest.raises(TimeoutError):
        archive.Wayback(tmp_path / "cache.json", retries=2).request(URL)
    assert opener.call_count == 3


def test_exhausted_rate_limit_blocks_further_network(tmp_path, monkeypatch):
    error = urllib.error.HTTPError(URL, 429, "rate limited", {}, io.BytesIO())
    opener = Mock(side_effect=error)
    monkeypatch.setattr(archive.urllib.request, "urlopen", opener)
    client = archive.Wayback(tmp_path / "cache.json", retries=0)
    with pytest.raises(urllib.error.HTTPError):
        client.request(URL)
    with pytest.raises(ValueError, match="rate limit exhausted"):
        client.request(URL)
    assert opener.call_count == 1


def test_offline_uses_only_cache(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({json.dumps([URL, "20240101"]): {"archive_url": SNAP}}))
    client = archive.Wayback(cache, offline=True)
    assert client.archive(URL, "20240101") == SNAP
    with pytest.raises(ValueError, match="offline mode"):
        client.archive(URL, "20240102")


def test_duplicate_keys_are_not_silently_rewritten(tmp_path):
    path = tmp_path / "item.yaml"
    path.write_text(f"sources: [{{url: '{URL}', url: '{URL}'}}]")
    with pytest.raises(ValueError, match="duplicate"):
        archive.process(path, dry_run=True)


def test_path_scope_and_dry_run(tmp_path, monkeypatch):
    monkeypatch.setattr(archive, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    path = tmp_path / "data" / "one.yaml"
    path.write_text(f"sources: [{{url: '{URL}'}}]\n")
    (tmp_path / "data" / "broken.yaml").write_text("[")
    assert archive.main(["--dry-run", "--path", str(path)]) == 0
    assert not (tmp_path / ".cache").exists()
    with pytest.raises(SystemExit):
        archive.main(["--dry-run", "--path", str(tmp_path)])


def test_undated_source_resumes_on_a_later_day(tmp_path):
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(side_effect=[({"archived_snapshots": {}}, {}, ""),
                                      ({"job_id": "job-1"}, {}, ""),
                                      TimeoutError("interrupted")])
    with pytest.raises(TimeoutError):
        client.archive(URL, "20240101", dated=False)
    client = archive.Wayback(tmp_path / "cache.json")
    client.request = Mock(return_value=({"status": "success", "timestamp": "20240102030405",
                                        "original_url": URL}, {}, ""))
    assert client.archive(URL, "20240105", dated=False) == SNAP  # "today" has moved on
    assert client.request.call_args.args[0].endswith("status/job-1")


def test_legacy_day_keyed_cache_is_adopted_for_undated_sources(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({json.dumps([URL, "20260926"]): {"archive_url": SNAP}}))
    client = archive.Wayback(cache, offline=True)
    assert client.archive(URL, "20261001", dated=False) == SNAP
    assert json.loads(cache.read_text()) == {json.dumps([URL, None]): {"archive_url": SNAP}}


def test_dated_sources_keep_their_own_date_key(tmp_path):
    cache = tmp_path / "cache.json"
    cache.write_text(json.dumps({json.dumps([URL, "20240101"]): {"archive_url": SNAP}}))
    client = archive.Wayback(cache, offline=True)
    with pytest.raises(ValueError, match="offline mode"):
        client.archive(URL, "20230101")


def test_process_marks_undated_sources(tmp_path):
    path = tmp_path / "item.yaml"
    path.write_text("sources:\n- url: https://example.org/a\n  title: A\n- url: https://example.org/b\n  date: 2024-01-01\n  title: B\n")
    client = Mock()
    client.archive.return_value = SNAP
    archive.process(path, client)
    assert [c.kwargs["dated"] for c in client.archive.call_args_list] == [False, True]
