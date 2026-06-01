"""Tests for brood.scraper -- all with fakes, no network or real sleeping."""
import time
from email.utils import formatdate

import pytest

from brood.scraper import Disallowed, PoliteScraper

ALLOW_ALL = lambda url: None  # robots fetcher returning "no robots.txt"


class Resp:
    """A minimal requests-like response."""

    def __init__(self, status, headers=None, body=b"hello"):
        self.status_code = status
        self.headers = headers or {}
        self.content = body
        self.text = body.decode() if isinstance(body, bytes) else body


class UrllibResp:
    """A response exposing .status (not .status_code) -- urllib style."""

    def __init__(self, status):
        self.status = status
        self.headers = {}


class FakeSession:
    def __init__(self, responses):
        self.headers = {}
        self._responses = responses
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        value = self._responses[url]
        return value.pop(0) if isinstance(value, list) else value


def _scraper(**kw):
    kw.setdefault("robots_fetcher", ALLOW_ALL)
    kw.setdefault("seed", 0)
    return PoliteScraper(sleep=kw.pop("sleep"), **kw)


# --------------------------------------------------------------------------- #
# Pacing
# --------------------------------------------------------------------------- #
def test_first_request_immediate_then_paced():
    sleeps = []
    s = _scraper(per_second=10, sleep=sleeps.append)
    s.fetch(lambda: Resp(200), "http://a.com/1")   # first -> immediate
    assert sleeps == []
    s.fetch(lambda: Resp(200), "http://a.com/2")   # second -> spaced
    assert len(sleeps) == 1
    assert s._lo / 1000 <= sleeps[0] <= s._hi / 1000


def test_per_host_independent():
    sleeps = []
    s = _scraper(per_second=10, sleep=sleeps.append)
    s.fetch(lambda: Resp(200), "http://a.com/x")   # first to a.com -> immediate
    s.fetch(lambda: Resp(200), "http://b.com/y")   # first to b.com -> immediate
    assert sleeps == []
    s.fetch(lambda: Resp(200), "http://a.com/z")   # second to a.com -> paced
    assert len(sleeps) == 1


# --------------------------------------------------------------------------- #
# Retry-After
# --------------------------------------------------------------------------- #
def test_retry_after_seconds_honored_exactly():
    sleeps = []
    s = _scraper(sleep=sleeps.append)
    seq = iter([Resp(429, {"Retry-After": "5"}), Resp(200)])
    resp = s.fetch(lambda: next(seq), "http://a.com/p")
    assert resp.status_code == 200
    assert sleeps == [5.0]          # the server's number, not a guess


def test_retry_after_http_date():
    sleeps = []
    s = _scraper(sleep=sleeps.append)
    when = formatdate(time.time() + 60, usegmt=True)
    seq = iter([Resp(503, {"Retry-After": when}), Resp(200)])
    s.fetch(lambda: next(seq), "http://a.com/p")
    assert len(sleeps) == 1
    assert 55 <= sleeps[0] <= 61     # ~60 s in the future


# --------------------------------------------------------------------------- #
# Backoff on 429 / 503
# --------------------------------------------------------------------------- #
def test_backoff_on_503_without_retry_after():
    sleeps = []
    s = _scraper(sleep=sleeps.append, base_backoff=0.5, max_backoff=10)
    seq = iter([Resp(503), Resp(503), Resp(200)])
    resp = s.fetch(lambda: next(seq), "http://a.com/p")
    assert resp.status_code == 200
    assert len(sleeps) == 2                       # two backoff waits
    assert 0 <= sleeps[0] <= 0.5                  # base * 2^0
    assert 0 <= sleeps[1] <= 1.0                  # base * 2^1


def test_max_retries_exhausted_returns_last():
    sleeps = []
    s = _scraper(sleep=sleeps.append, max_retries=2)
    calls = {"n": 0}

    def always_429():
        calls["n"] += 1
        return Resp(429)

    resp = s.fetch(always_429, "http://a.com/p")
    assert resp.status_code == 429
    assert calls["n"] == 3            # initial + 2 retries
    assert len(sleeps) == 2


def test_non_retry_status_passes_through():
    sleeps = []
    s = _scraper(sleep=sleeps.append)
    calls = {"n": 0}

    def once():
        calls["n"] += 1
        return Resp(404)

    assert s.fetch(once, "http://a.com/p").status_code == 404
    assert calls["n"] == 1            # 404 is not retried


def test_status_duck_typing_urllib_style():
    sleeps = []
    s = _scraper(sleep=sleeps.append)
    seq = iter([UrllibResp(429), UrllibResp(200)])
    resp = s.fetch(lambda: next(seq), "http://a.com/p")
    assert resp.status == 200


# --------------------------------------------------------------------------- #
# robots.txt
# --------------------------------------------------------------------------- #
ROBOTS = "User-agent: *\nDisallow: /private/\nCrawl-delay: 3\n"


def test_robots_disallow_raises():
    s = PoliteScraper(robots_fetcher=lambda u: ROBOTS, sleep=lambda s: None, seed=0)
    with pytest.raises(Disallowed):
        s.fetch(lambda: Resp(200), "http://a.com/private/secret")
    assert s.allowed("http://a.com/public") is True


def test_robots_crawl_delay_floors_gap():
    sleeps = []
    s = PoliteScraper(per_second=10, robots_fetcher=lambda u: ROBOTS,
                      sleep=sleeps.append, seed=0)
    s.fetch(lambda: Resp(200), "http://a.com/1")     # first -> immediate
    s.fetch(lambda: Resp(200), "http://a.com/2")     # second -> max(gap, 3s)
    assert sleeps == [3.0]


def test_obey_robots_false_skips_network():
    # No robots_fetcher given, but obey_robots=False must not touch the network.
    s = PoliteScraper(obey_robots=False, sleep=lambda s: None, seed=0)
    assert s.allowed("http://a.com/anything") is True


# --------------------------------------------------------------------------- #
# requests convenience (via an injected session -- no real requests/network)
# --------------------------------------------------------------------------- #
def test_get_uses_session_and_paces():
    sleeps = []
    session = FakeSession({"http://a.com/1": Resp(200), "http://a.com/2": Resp(200)})
    s = _scraper(per_second=10, sleep=sleeps.append, session=session)
    s.get("http://a.com/1")
    s.get("http://a.com/2")
    assert session.calls == ["http://a.com/1", "http://a.com/2"]
    assert len(sleeps) == 1          # second call paced


def test_crawl_skips_disallowed():
    session = FakeSession({
        "http://a.com/ok": Resp(200),
        "http://a.com/private/x": Resp(200),
    })
    s = PoliteScraper(robots_fetcher=lambda u: ROBOTS, sleep=lambda s: None,
                      seed=0, session=session)
    seen = [url for url, _ in s.crawl(["http://a.com/ok", "http://a.com/private/x"])]
    assert seen == ["http://a.com/ok"]    # disallowed one skipped
