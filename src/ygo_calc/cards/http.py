"""Small HTTP helpers shared by the card sources and the image loader.

Requests only go to the card data and image sites below, over HTTPS, and redirects are held
to the same rule. Some URLs come from those sites' own data (e.g. image links in YGOPRODeck's
card info), so this keeps the server from being pointed anywhere else, such as at addresses
inside the network it runs in (server-side request forgery).

Requests to each site are also throttled: YGOPRODeck blocks an address for an hour if it makes
more than 20 requests a second, so requests to one host are spaced out well under that, only a
few run at once, and a host that answers 429 (too many requests) is left alone until it says.
"""

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from typing import Dict, Optional, Tuple
from urllib.parse import urlsplit

USER_AGENT = 'Mozilla/5.0 YGO-Calculator/1.0'

ALLOWED_HOSTS = frozenset({
    "db.ygoprodeck.com",          # card names
    "images.ygoprodeck.com",      # card images
    "api.github.com",             # the list of EDOPro card databases
    "raw.githubusercontent.com",  # the EDOPro card databases
    "pics.projectignis.org",      # EDOPro card images
})


class BlockedURLError(ValueError):
    """A URL that isn't HTTPS to one of ALLOWED_HOSTS."""


def check_url(url: str) -> str:
    """Return the URL if it may be fetched, else raise BlockedURLError."""
    parts = urlsplit(url)
    if parts.scheme != "https" or (parts.hostname or "").lower() not in ALLOWED_HOSTS or parts.username or parts.password:
        raise BlockedURLError(f"Blocked request to {url!r}")
    return url


class _CheckedRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_opener = urllib.request.build_opener(_CheckedRedirects)

# Per host: at most 10 requests a second (YGOPRODeck allows 20), 4 at a time
MIN_INTERVAL = 0.1
MAX_CONCURRENT = 4
# A request that would wait longer than this for its turn fails instead (the caller can try later)
MAX_QUEUE_SECONDS = 15.0
# How long to leave a host alone after a 429 that doesn't say (and the most a Retry-After may ask)
DEFAULT_BACKOFF = 60
MAX_BACKOFF = 60 * 60
# Per host, at most this many requests a minute in all, whoever asks: past it, requests to that
# host are refused until the minute is up (a busy spell, or someone making the server look up
# made-up cards, can't add up to enough to get the server's address blocked)
MAX_PER_MINUTE = 300
# After this many failures in a row (timeouts, server errors), a host is left alone for a while,
# twice as long each time it fails again, up to MAX_BACKOFF
FAILURES_BEFORE_PAUSE = 5
FAILURE_PAUSE = 30


class HostBusyError(OSError):
    """Not sent: the host asked us to slow down, is failing, or has had its share of requests."""


class _Throttle:
    """Spaces out the requests to each host, caps how many run at once and how many a minute,
    and pauses a host that asks us to (429) or keeps failing."""

    def __init__(self, max_per_minute: int = MAX_PER_MINUTE):
        self.max_per_minute = max_per_minute
        self._lock = threading.Lock()
        self._next_start: Dict[str, float] = {}
        self._paused_until: Dict[str, float] = {}
        self._slots: Dict[str, threading.BoundedSemaphore] = {}
        # host -> (start of its current minute, requests sent in it)
        self._minute: Dict[str, Tuple[float, int]] = {}
        self._failures: Dict[str, int] = {}

    def acquire(self, host: str) -> threading.BoundedSemaphore:
        """Wait for this host's turn; returns the slot to release once the request is done."""
        with self._lock:
            self._check_paused(host)
            slot = self._slots.setdefault(host, threading.BoundedSemaphore(MAX_CONCURRENT))
        if not slot.acquire(timeout=MAX_QUEUE_SECONDS):
            raise HostBusyError(f"Too many requests to {host} waiting")
        try:
            with self._lock:
                self._check_paused(host)
                now = time.monotonic()
                start = max(now, self._next_start.get(host, 0.0))
                if start - now > MAX_QUEUE_SECONDS:
                    raise HostBusyError(f"Too many requests to {host} waiting")
                minute_start, sent = self._minute.get(host, (start, 0))
                if start - minute_start >= 60:
                    minute_start, sent = start, 0
                if sent >= self.max_per_minute:
                    self._paused_until[host] = minute_start + 60
                    logging.warning("%d requests to %s this minute; holding off until the minute is up",
                                    sent, host)
                    raise HostBusyError(f"{host} has had its {self.max_per_minute} requests this minute")
                self._minute[host] = (minute_start, sent + 1)
                self._next_start[host] = start + MIN_INTERVAL
            if start > now:
                time.sleep(start - now)
        except BaseException:
            slot.release()
            raise
        return slot

    def pause(self, host: str, seconds: float):
        with self._lock:
            self._paused_until[host] = max(self._paused_until.get(host, 0.0), time.monotonic() + seconds)

    def succeeded(self, host: str):
        with self._lock:
            self._failures.pop(host, None)

    def failed(self, host: str):
        """A timeout or server error: after several in a row, leave the host alone for a while."""
        with self._lock:
            failures = self._failures.get(host, 0) + 1
            self._failures[host] = failures
            if failures < FAILURES_BEFORE_PAUSE:
                return
            seconds = min(FAILURE_PAUSE * 2 ** (failures - FAILURES_BEFORE_PAUSE), MAX_BACKOFF)
            self._paused_until[host] = max(self._paused_until.get(host, 0.0), time.monotonic() + seconds)
        logging.warning("%s failed %d times in a row; not contacting it for %.0fs", host, failures, seconds)

    def _check_paused(self, host: str):
        wait = self._paused_until.get(host, 0.0) - time.monotonic()
        if wait > 0:
            raise HostBusyError(f"{host} is paused for {wait:.0f}s more")


_throttle = _Throttle()


def _retry_after(error: urllib.error.HTTPError) -> float:
    value = error.headers.get("Retry-After", "") if error.headers else ""
    return min(float(value), MAX_BACKOFF) if value.isdigit() else DEFAULT_BACKOFF


def fetch_bytes(url: str, timeout: float, accept_json: bool = False, max_bytes: Optional[int] = None) -> bytes:
    """GET a URL and return the response body (raising ValueError if it's over max_bytes, and
    HostBusyError without sending anything while the host is throttled)."""
    req = urllib.request.Request(check_url(url))
    req.add_header('User-Agent', USER_AGENT)
    if accept_json:
        req.add_header('Accept', 'application/json')
    host = (urlsplit(url).hostname or "").lower()
    slot = _throttle.acquire(host)
    try:
        with _opener.open(req, timeout=timeout) as response:
            if max_bytes is None:
                data = response.read()
            else:
                data = response.read(max_bytes + 1)
                if len(data) > max_bytes:
                    raise ValueError(f"Response from {url} is larger than {max_bytes} bytes")
        _throttle.succeeded(host)
        return data
    except urllib.error.HTTPError as e:
        if e.code == 429:
            seconds = _retry_after(e)
            logging.warning("%s answered 429 (too many requests); not contacting it for %.0fs", host, seconds)
            _throttle.pause(host, seconds)
        elif e.code >= 500:
            _throttle.failed(host)
        else:
            # A 404 and the like: the site is working, it just hasn't got that
            _throttle.succeeded(host)
        raise
    except OSError:
        # Timeouts and connection errors (urllib's URLError is an OSError)
        _throttle.failed(host)
        raise
    finally:
        slot.release()


def fetch_json(url: str, timeout: float, accept_json: bool = True, max_bytes: Optional[int] = 20 * 1024 * 1024):
    """GET a URL and parse the response as JSON."""
    return json.loads(fetch_bytes(url, timeout, accept_json=accept_json, max_bytes=max_bytes).decode())
