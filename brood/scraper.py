"""A polite scraper built on the brood pacer.

`PoliteScraper` spaces your requests with jittered, coprime gaps (per host) and
does the courteous things a server expects:

* **Respect Retry-After.** When a response carries a ``Retry-After`` header
  (seconds or an HTTP-date), wait exactly that long.
* **Back off on 429 / 503.** Treat "Too Many Requests" / "Service Unavailable"
  as *slow down* and retry with full-jitter exponential backoff.
* **Obey robots.txt.** Honour ``Allow`` / ``Disallow`` and ``Crawl-delay`` via
  the standard library (`urllib.robotparser`) -- no new dependency.
* **Pace per host.** Each domain gets its own pacer, so many hosts stay polite
  to each one independently.

Two ways to use it. Bring your own client (zero extra dependencies)::

    scraper = PoliteScraper(per_second=1)
    resp = scraper.fetch(lambda: httpx.get(url), url)

or let it carry a ``requests`` session for you (``pip install 'brood[http]'``)::

    scraper = PoliteScraper(per_second=1)
    html = scraper.get(url).text
    for url, resp in scraper.crawl(urls):
        ...

The timing methods take an injectable ``sleep`` and the robots loader an
injectable fetcher, so the whole thing is unit-testable without real time or a
network.
"""
from __future__ import annotations

import random
import time
import zlib
from typing import Callable, Dict, Iterable, Iterator, Optional, Sequence, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from .ratelimit import Pacer

__all__ = ["PoliteScraper", "Disallowed"]

DEFAULT_USER_AGENT = "brood-politescraper/0.1 (+https://github.com/odomojuli/brood)"

# Assumed limiter windows (ms). All 2*5-smooth, so the safe gaps are the
# wheel(2, 5) spokes -- coprime to every "round" interval.
DEFAULT_WINDOWS: Tuple[int, ...] = (1000, 500, 250, 200, 100)


class Disallowed(Exception):
    """Raised when robots.txt disallows the URL for our user-agent."""


class PoliteScraper:
    """Polite, per-host paced HTTP access for scrapers."""

    def __init__(
        self,
        per_second: float = 1.0,
        *,
        jitter: float = 0.2,
        windows: Sequence[int] = DEFAULT_WINDOWS,
        max_retries: int = 4,
        base_backoff: float = 0.5,
        max_backoff: float = 60.0,
        retry_statuses: Sequence[int] = (429, 503),
        respect_retry_after: bool = True,
        obey_robots: bool = True,
        user_agent: str = DEFAULT_USER_AGENT,
        session: object = None,
        sleep: Callable[[float], object] = time.sleep,
        robots_fetcher: Optional[Callable[[str], Optional[str]]] = None,
        seed: Optional[int] = None,
    ) -> None:
        if per_second <= 0:
            raise ValueError("per_second must be positive")

        mean_ms = round(1000.0 / per_second)
        self._lo = max(1, int(mean_ms * (1 - jitter)))
        self._hi = max(self._lo + 1, int(mean_ms * (1 + jitter)))

        self.windows = tuple(windows)
        self.max_retries = max_retries
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self.retry_statuses = tuple(retry_statuses)
        self.respect_retry_after = respect_retry_after
        self.obey_robots = obey_robots
        self.user_agent = user_agent
        self.session = session
        self.seed = seed

        self._sleep = sleep
        self._robots_fetcher = robots_fetcher or self._default_robots_fetcher

        self._pacers: Dict[str, Pacer] = {}
        self._robots: Dict[str, RobotFileParser] = {}
        self._seen_hosts: set = set()
        self._rng_for_backoff = random.Random(seed)

    # ----------------------------------------------------------------- core #
    def fetch(self, call: Callable[[], object], url: str,
              *, max_retries: Optional[int] = None) -> object:
        """Pace and run ``call`` (returns a response-like object), retrying
        politely on rate-limit responses. Raises :class:`Disallowed` if
        robots.txt forbids ``url``.
        """
        if self.obey_robots and not self.allowed(url):
            raise Disallowed(url)

        host = _host(url)
        self._pace(host)

        retries = self.max_retries if max_retries is None else max_retries
        attempt = 0
        while True:
            resp = call()
            status = _status(resp)
            if status in self.retry_statuses and attempt < retries:
                delay = self._retry_after(resp) if self.respect_retry_after else None
                if delay is None:
                    delay = self._backoff(attempt)
                self._sleep(delay)
                attempt += 1
                continue
            return resp

    # --------------------------------------------------- requests convenience #
    def get(self, url: str, **kwargs) -> object:
        """Fetch ``url`` politely with a carried ``requests`` session.

        Needs ``requests`` (``pip install 'brood[http]'``); for any other client
        use :meth:`fetch`.
        """
        session = self._ensure_session()
        kwargs.setdefault("timeout", 30)
        return self.fetch(lambda: session.get(url, **kwargs), url)

    def crawl(self, urls: Iterable[str], **kwargs) -> Iterator[Tuple[str, object]]:
        """Yield ``(url, response)`` for each URL, skipping disallowed ones."""
        for url in urls:
            try:
                yield url, self.get(url, **kwargs)
            except Disallowed:
                continue

    # ------------------------------------------------------------- robots.txt #
    def allowed(self, url: str) -> bool:
        """Whether robots.txt permits ``url`` for our user-agent."""
        if not self.obey_robots:
            return True
        rules = self._rules_for(url)
        return rules.can_fetch(self.user_agent, url) if rules else True

    def _rules_for(self, url: str) -> Optional[RobotFileParser]:
        host = _host(url)
        if host not in self._robots:
            parser = RobotFileParser()
            text = self._robots_fetcher(f"{_base(url)}/robots.txt")
            if text is None:
                parser.allow_all = True
            else:
                parser.parse(text.splitlines())
            self._robots[host] = parser
        return self._robots[host]

    def _crawl_delay(self, host: str) -> Optional[float]:
        parser = self._robots.get(host)
        if parser is None:
            return None
        try:
            delay = parser.crawl_delay(self.user_agent)
        except Exception:  # pragma: no cover - defensive
            return None
        return float(delay) if delay is not None else None

    def _default_robots_fetcher(self, robots_url: str) -> Optional[str]:
        import urllib.request

        request = urllib.request.Request(
            robots_url, headers={"User-Agent": self.user_agent})
        try:
            with urllib.request.urlopen(request, timeout=10) as response:
                if getattr(response, "status", 200) >= 400:
                    return None
                return response.read().decode("utf-8", "replace")
        except Exception:
            return None

    # ---------------------------------------------------------------- pacing #
    def _pace(self, host: str) -> None:
        # First request to a host goes out immediately; later ones are spaced.
        if host not in self._seen_hosts:
            self._seen_hosts.add(host)
            return
        gap_s = self._pacer_for(host).next_gap() / 1000.0
        crawl_delay = self._crawl_delay(host)
        if crawl_delay is not None:
            gap_s = max(gap_s, crawl_delay)
        self._sleep(gap_s)

    def _pacer_for(self, host: str) -> Pacer:
        if host not in self._pacers:
            seed = (None if self.seed is None
                    else (self.seed + zlib.crc32(host.encode())) & 0xFFFFFFFF)
            self._pacers[host] = Pacer(
                self.windows, self._lo, self._hi, jitter_start=False, seed=seed)
        return self._pacers[host]

    def _backoff(self, attempt: int) -> float:
        ceiling = min(self.max_backoff, self.base_backoff * (2 ** attempt))
        return self._rng_for_backoff.uniform(0, ceiling)

    # ---------------------------------------------------------------- helpers #
    def _retry_after(self, resp: object) -> Optional[float]:
        value = _header(resp, "Retry-After")
        if not value:
            return None
        value = value.strip()
        if value.isdigit():
            return float(value)
        try:
            from datetime import datetime, timezone
            from email.utils import parsedate_to_datetime

            when = parsedate_to_datetime(value)
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            return max(0.0, (when - datetime.now(timezone.utc)).total_seconds())
        except Exception:
            return None

    def _ensure_session(self):
        if self.session is None:
            try:
                import requests
            except ImportError as exc:  # pragma: no cover - exercised without requests
                raise RuntimeError(
                    "get()/crawl() need requests: pip install 'brood[http]', "
                    "or use fetch() with your own client") from exc
            self.session = requests.Session()
            self.session.headers.update({"User-Agent": self.user_agent})
        return self.session


# --------------------------------------------------------------------------- #
# Response-shape helpers (duck-typed across requests / httpx / urllib)
# --------------------------------------------------------------------------- #
def _host(url: str) -> str:
    return urlparse(url).netloc


def _base(url: str) -> str:
    parts = urlparse(url)
    return f"{parts.scheme}://{parts.netloc}"


def _status(resp: object) -> Optional[int]:
    status = getattr(resp, "status_code", None)
    if status is None:
        status = getattr(resp, "status", None)
    return status


def _header(resp: object, name: str) -> Optional[str]:
    headers = getattr(resp, "headers", None)
    if headers is None:
        return None
    try:
        return headers.get(name)
    except AttributeError:  # pragma: no cover - defensive
        return None
