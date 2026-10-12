"""Protection for the public web app, as one ASGI middleware around the whole app:

- Security headers on every response (Content-Security-Policy, no framing, no sniffing, ...).
- A size limit on request bodies, so nobody can make the server parse huge JSON.
- A per-client rate limit on the API, stricter for the endpoints that call outside services
  (deck lookups and card images), so the app can't be used to flood YGOPRODeck or EDOPro.

The client is the connecting address. Behind a reverse proxy or a hosting platform, set the
FORWARDED_ALLOW_IPS environment variable (e.g. to the proxy's address, or "*" when only the
platform can reach the app) so uvicorn takes the real client address from X-Forwarded-For.
"""

import json
import logging
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
    "decks": 30,     # POST /api/decks: looks card names up online
    "images": 600,   # GET /api/cards/{id}/image: downloads images not yet cached
    "api": 300,      # everything else under /api
}
WINDOW_SECONDS = 60.0


class RateLimiter:
    """Counts requests per (client, kind) in fixed one-minute windows, in memory."""

    def __init__(self, limits: Dict[str, int], window: float = WINDOW_SECONDS):
        self.limits = limits
        self.window = window
        self._counts: Dict[Tuple[str, str], Tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, client: str, kind: str, now: Optional[float] = None) -> Optional[int]:
        """Counts a request; returns None if allowed, else the seconds until it would be."""
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._counts) > 50_000:
                self._forget_old(now)
            start, count = self._counts.get((client, kind), (now, 0))
            if now - start >= self.window:
                start, count = now, 0
            if count >= self.limits[kind]:
                # Logged once per client and window, so a flood can't flood the log too
                if count == self.limits[kind]:
                    logging.warning("Rate limit: %s made over %d %s requests in a minute; refusing until the window ends",
                                    client, self.limits[kind], kind)
                    self._counts[(client, kind)] = (start, count + 1)
                return max(1, int(start + self.window - now) + 1)
            self._counts[(client, kind)] = (start, count + 1)
            return None

    def _forget_old(self, now: float):
        self._counts = {key: value for key, value in self._counts.items() if now - value[0] < self.window}


def request_kind(method: str, path: str) -> Optional[str]:
    """Which rate limit applies to a request (None: not limited, e.g. the page's own files)."""
    if not path.startswith("/api/"):
        return None
    if path.startswith("/api/cards/"):
        return "images"
    if path == "/api/decks" and method == "POST":
        return "decks"
    return "api"


class SecurityMiddleware:
    def __init__(self, app, limiter: Optional[RateLimiter] = None, max_body: int = MAX_BODY_BYTES):
        self.app = app
        self.limiter = limiter or RateLimiter(RATE_LIMITS)
        self.max_body = max_body

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
            client = (scope.get("client") or ("unknown", 0))[0]
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
