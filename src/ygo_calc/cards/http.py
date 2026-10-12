"""Small HTTP helpers shared by the card sources and the image loader.

Requests only go to the card data and image sites below, over HTTPS, and redirects are held
to the same rule. Some URLs come from those sites' own data (e.g. image links in YGOPRODeck's
card info), so this keeps the server from being pointed anywhere else, such as at addresses
inside the network it runs in (server-side request forgery).
"""

import json
import urllib.request
from typing import Optional
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


def fetch_bytes(url: str, timeout: float, accept_json: bool = False, max_bytes: Optional[int] = None) -> bytes:
    """GET a URL and return the response body (raising ValueError if it's over max_bytes)."""
    req = urllib.request.Request(check_url(url))
    req.add_header('User-Agent', USER_AGENT)
    if accept_json:
        req.add_header('Accept', 'application/json')
    with _opener.open(req, timeout=timeout) as response:
        if max_bytes is None:
            return response.read()
        data = response.read(max_bytes + 1)
        if len(data) > max_bytes:
            raise ValueError(f"Response from {url} is larger than {max_bytes} bytes")
        return data


def fetch_json(url: str, timeout: float, accept_json: bool = True, max_bytes: Optional[int] = 20 * 1024 * 1024):
    """GET a URL and parse the response as JSON."""
    return json.loads(fetch_bytes(url, timeout, accept_json=accept_json, max_bytes=max_bytes).decode())
