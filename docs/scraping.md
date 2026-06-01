# Polite scraping with `brood`

`brood.scraper.PoliteScraper` sits on top of the [pacer](rate-limiting.md) and
makes "be nice to their server" a one-liner. It spaces requests per host with
jittered, coprime gaps and does the four courteous things a server expects:

- **Respects `Retry-After`** — if a response says wait *N* seconds (or until an
  HTTP-date), it waits exactly that long instead of guessing.
- **Backs off on 429 / 503** — treats them as "slow down" and retries with
  full-jitter exponential backoff, up to a cap.
- **Obeys `robots.txt`** — honours `Allow` / `Disallow` and `Crawl-delay` via
  the standard library (`urllib.robotparser`), no extra dependency.
- **Paces per host** — each domain gets its own pacer, so hitting many hosts
  stays polite to each one independently.

## The one-liner

Install the optional HTTP extra and let the scraper carry a `requests` session:

```sh
pip install 'brood[http]'
```

```python
from brood import PoliteScraper

scraper = PoliteScraper(per_second=1)        # at most ~1 request/second/host
html = scraper.get("https://example.com").text

for url, resp in scraper.crawl(urls):        # paced, robots-aware, skips Disallow
    if resp.status_code == 200:
        handle(url, resp.text)
```

`get()` and `crawl()` apply pacing, `Retry-After`, backoff, and robots
automatically. `crawl()` silently skips URLs that robots.txt disallows.

## Bring your own client (zero extra dependencies)

The core is client-agnostic. Pass any zero-argument callable that returns a
response with a `.status_code` (or `.status`) and `.headers` — `requests`,
`httpx`, and `urllib` all work:

```python
import httpx
from brood import PoliteScraper

scraper = PoliteScraper(per_second=2)
resp = scraper.fetch(lambda: httpx.get(url), url)
```

`fetch(call, url)` does everything `get()` does — it just lets you own the HTTP
call (custom headers, sessions, auth, async client wrapped in a sync shim, …).

## Knobs

```python
PoliteScraper(
    per_second=1.0,          # target rate per host
    jitter=0.2,              # gaps drawn from mean ± 20%, coprime to round windows
    max_retries=4,
    base_backoff=0.5,        # seconds; full-jitter exponential
    max_backoff=60.0,
    retry_statuses=(429, 503),
    respect_retry_after=True,
    obey_robots=True,
    user_agent="my-bot/1.0 (+https://example.com/bot)",   # used for robots + requests
    seed=None,               # set for reproducible jitter
)
```

A few notes:

- **Set a real `user_agent`.** It identifies you to the site and is the agent
  string matched against `robots.txt`.
- **`Crawl-delay` wins.** If robots.txt asks for a longer delay than your
  `per_second`, the longer delay is used.
- The first request to each host goes out immediately; only *subsequent*
  requests to that host are spaced.

## Why coprime gaps here

The pacing gaps are drawn coprime to a set of "round" windows (1000 / 500 /
250 / 200 / 100 ms — all 2·5-smooth), i.e. the wheel(2, 5) spokes. As
[docs/rate-limiting.md](rate-limiting.md) shows, this does not change your
*rate* (politeness is the rate you choose), but it spreads requests across
every window's phase and keeps multiple scraper instances from
re-synchronising into bursts. The heavy lifting for "don't get throttled" is
the rate and the jitter; the coprime structure is the brood flavour on top.

## Testing your own usage

Every timing path is injectable, so you can unit-test a scraper without a
network or real sleeping:

```python
sleeps = []
scraper = PoliteScraper(
    per_second=10,
    sleep=sleeps.append,                       # record instead of sleeping
    robots_fetcher=lambda url: "User-agent: *\nCrawl-delay: 2\n",
    session=FakeSession(...),                  # or use fetch() with a fake call
    seed=0,
)
```
