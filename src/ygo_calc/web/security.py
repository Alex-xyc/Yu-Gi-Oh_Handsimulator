"""Protection for the public web app, as one ASGI middleware around the whole app:

- Security headers on every response (Content-Security-Policy, no framing, no sniffing, ...).
- A size limit on request bodies, so nobody can make the server parse huge JSON.
- A per-client rate limit on the API, stricter for the endpoints that call outside services
  (deck lookups and card images), so the app can't be used to flood YGOPRODeck or EDOPro.
  A client that keeps sending requests after being refused is blocked for a while.

The client is the connecting address. Behind a reverse proxy or a hosting platform, set
YGO_PROXY_HOPS to the number of proxies in front of the app (1 on Cloud Run): the client is then
that many entries from the right of X-Forwarded-For. Each proxy appends the address it saw, so
those entries can't be faked, unlike the ones further left, which the client sends itself.
"""

import json
import logging
import os
import threading
import time
from typing import Dict, Optional, Tuple

# What the page may load: only its own files (fonts included), plus inline styles (MUI and
# animations set styles inline). No inline or outside scripts, no plugins, no framing by other sites.
CONTENT_SECURITY_POLICY = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "font-src 'self'",
    "img-src 'self' data: blob:",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
])

SECURITY_HEADERS = [
    (b"content-security-policy", CONTENT_SECURITY_POLICY.encode()),
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"DENY"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"camera=(), microphone=(), geolocation=(), payment=()"),
    (b"cross-origin-opener-policy", b"same-origin"),
    # Browsers only honour this over HTTPS, so it's harmless on plain HTTP
    (b"strict-transport-security", b"max-age=31536000"),
]

# The largest request body the API accepts. A full deck with labels is a few kilobytes.
MAX_BODY_BYTES = 64 * 1024

# Requests per client per minute, by kind. Generous for normal use: labelling cards sends a
# (debounced) stats request per click, and opening a deck loads up to 60 card images.
RATE_LIMITS = {
    "decks": 30,     # POST /api/decks and /api/decks/info: look cards up online
    "images": 600,   # GET /api/cards/{id}/image: downloads images not yet cached
    "api": 300,      # everything else under /api
}
WINDOW_SECONDS = 60.0
# A client that sends this many times its limit in one window (i.e. ignores the 429s) is
# refused everything for BLOCK_SECONDS
BLOCK_AFTER = 2
BLOCK_SECONDS = 10 * 60
# Clients remembered at most; past this the oldest are forgotten (so a flood of addresses
# can't use up memory)
MAX_CLIENTS = 50_000


class RateLimiter:
    """Counts requests per (client, kind) in fixed one-minute windows, in memory, and blocks
    clients that carry on regardless."""

    def __init__(self, limits: Dict[str, int], window: float = WINDOW_SECONDS,
                 block_seconds: float = BLOCK_SECONDS, max_clients: int = MAX_CLIENTS):
        self.limits = limits
        self.window = window
        self.block_seconds = block_seconds
        self.max_clients = max_clients
        self._counts: Dict[Tuple[str, str], Tuple[float, int]] = {}
        self._blocked: Dict[str, float] = {}
        self._lock = threading.Lock()

    def check(self, client: str, kind: str, now: Optional[float] = None) -> Optional[int]:
        """Counts a request; returns None if allowed, else the seconds until it would be."""
        now = time.monotonic() if now is None else now
        with self._lock:
            blocked_until = self._blocked.get(client)
            if blocked_until is not None:
                if now < blocked_until:
                    return max(1, int(blocked_until - now) + 1)
                del self._blocked[client]
            if len(self._counts) >= self.max_clients:
                self._forget_old(now)
            start, count = self._counts.get((client, kind), (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            count += 1
            self._counts[(client, kind)] = (start, count)
            limit = self.limits[kind]
            if count <= limit:
                return None
            # Logged once per client and window, so a flood can't flood the log too
            if count == limit + 1:
                logging.warning("Rate limit: %s made over %d %s requests in a minute; refusing until the window ends",
                                client, limit, kind)
            if count >= limit * BLOCK_AFTER:
                logging.warning("Rate limit: %s kept on after being refused; blocking it for %.0fs",
                                client, self.block_seconds)
                self._blocked[client] = now + self.block_seconds
                if len(self._blocked) > self.max_clients:
                    self._blocked = {c: t for c, t in self._blocked.items() if t > now}
                return int(self.block_seconds)
            return max(1, int(start + self.window - now) + 1)

    def _forget_old(self, now: float):
        self._counts = {key: value for key, value in self._counts.items() if now - value[0] < self.window}
        # Still full (many clients in the last minute): drop the oldest windows
        if len(self._counts) >= self.max_clients:
            keep = sorted(self._counts.items(), key=lambda item: item[1][0])[len(self._counts) - self.max_clients // 2:]
            self._counts = dict(keep)


def client_address(scope, proxy_hops: int) -> str:
    """The client's address: the connecting one, or behind proxy_hops proxies, the address the
    outermost proxy saw (proxy_hops entries from the right of X-Forwarded-For)."""
    connected = (scope.get("client") or ("unknown", 0))[0]
    if proxy_hops <= 0:
        return connected
    values = [value.decode("latin-1") for name, value in scope.get("headers", []) if name == b"x-forwarded-for"]
    hosts = [host.strip() for host in ",".join(values).split(",") if host.strip()]
    return hosts[-proxy_hops] if len(hosts) >= proxy_hops else connected


def request_kind(method: str, path: str) -> Optional[str]:
    """Which rate limit applies to a request (None: not limited, e.g. the page's own files)."""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/cards/"):
        return "images"
    if path in ("/api/decks", "/api/decks/info") and method == "POST":
        return "decks"
    return "api"


class SecurityMiddleware:
    def __init__(self, app, limiter: Optional[RateLimiter] = None, max_body: int = MAX_BODY_BYTES,
                 proxy_hops: Optional[int] = None):
        self.app = app
        self.limiter = limiter or RateLimiter(RATE_LIMITS)
        self.max_body = max_body
        self.proxy_hops = int(os.environ.get("YGO_PROXY_HOPS", "0")) if proxy_hops is None else proxy_hops
        # For checking YGO_PROXY_HOPS after a deploy: logs each API request's X-Forwarded-For and the
        # address taken from it. Turn it on for a few requests only (it logs visitors' addresses).
        self.log_client = os.environ.get("YGO_LOG_CLIENT") == "1"

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                names = {name for name, _ in message.get("headers", [])}
                message["headers"] = list(message.get("headers", [])) + [
                    header for header in SECURITY_HEADERS if header[0] not in names]
            await send(message)

        method, path = scope["method"], scope["path"]
        kind = request_kind(method, path)
        if kind:
            client = client_address(scope, self.proxy_hops)
            if self.log_client:
                forwarded = b", ".join(value for name, value in scope.get("headers", []) if name == b"x-forwarded-for")
                logging.warning("Client address check: X-Forwarded-For=%r, YGO_PROXY_HOPS=%d -> rate limited as %s",
                                forwarded.decode("latin-1"), self.proxy_hops, client)
            wait = self.limiter.check(client, kind)
            if wait is not None:
                return await _reply(send_with_headers, 429, "Too many requests. Please wait a moment and try again.",
                                    [(b"retry-after", str(wait).encode())])

        if method in ("POST", "PUT", "PATCH"):
            length = dict(scope.get("headers", [])).get(b"content-length")
            if length is None:
                return await _reply(send_with_headers, 411, "Requests need a Content-Length.")
            if not length.isdigit() or int(length) > self.max_body:
                return await _reply(send_with_headers, 413, "Request is too large.")
            receive = _limited(receive, self.max_body)

        await self.app(scope, receive, send_with_headers)


def _limited(receive, max_body: int):
    """Stops reading a body that turns out longer than its Content-Length promised."""
    received = 0

    async def wrapped():
        nonlocal received
        message = await receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > max_body:
                raise ValueError("Request body larger than allowed")
        return message
    return wrapped


async def _reply(send, status: int, detail: str, headers=()):
    body = json.dumps({"detail": detail}).encode()
    await send({"type": "http.response.start", "status": status, "headers": [
        (b"content-type", b"application/json"), (b"content-length", str(len(body)).encode()), *headers]})
    await send({"type": "http.response.body", "body": body})
