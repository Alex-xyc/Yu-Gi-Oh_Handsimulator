"""Small HTTP helpers shared by the card sources and the image loader."""

import json
import urllib.request

USER_AGENT = 'Mozilla/5.0 YGO-Calculator/1.0'


def fetch_bytes(url: str, timeout: float, accept_json: bool = False) -> bytes:
    """GET a URL and return the response body."""
    req = urllib.request.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    if accept_json:
        req.add_header('Accept', 'application/json')
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read()


def fetch_json(url: str, timeout: float, accept_json: bool = True):
    """GET a URL and parse the response as JSON."""
    return json.loads(fetch_bytes(url, timeout, accept_json=accept_json).decode())
