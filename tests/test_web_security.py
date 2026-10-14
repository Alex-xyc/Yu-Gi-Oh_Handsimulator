"""Tests for the web app's protections: security headers, request limits, rate limits and input
checks (no network is used)."""
import os
import sys
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

try:
    from fastapi.testclient import TestClient
except ImportError:  # The web dependencies are optional (requirements-web.txt)
    TestClient = None

from ygo_calc.web.security import RateLimiter, request_kind


def body(**extra):
    return {"name": "Deck", "cards": [{"name": f"Card {i}", "copies": 1} for i in range(40)], **extra}


class TestRateLimiter(unittest.TestCase):
    def test_limits_per_client_and_kind_and_resets(self):
        limiter = RateLimiter({"api": 2, "decks": 1}, window=60)
        self.assertIsNone(limiter.check("a", "api", now=0))
        self.assertIsNone(limiter.check("a", "api", now=1))
        self.assertIsNotNone(limiter.check("a", "api", now=2))   # third in the window
        self.assertIsNone(limiter.check("b", "api", now=2))      # another client
        self.assertIsNone(limiter.check("a", "decks", now=2))    # another kind
        self.assertIsNone(limiter.check("a", "api", now=61))     # a new window

    def test_kinds(self):
        self.assertEqual(request_kind("POST", "/api/decks"), "decks")
        self.assertEqual(request_kind("POST", "/api/decks/info"), "decks")
        self.assertEqual(request_kind("GET", "/api/cards/123/image"), "images")
        self.assertEqual(request_kind("POST", "/api/stats"), "api")
        self.assertIsNone(request_kind("GET", "/assets/index.js"))


@unittest.skipIf(TestClient is None, "web dependencies not installed")
class TestServerProtection(unittest.TestCase):
    def setUp(self):
        from ygo_calc.web import server
        self.server = server
        self.client = TestClient(server.app)
        # A fresh rate limiter for each test
        for middleware in server.app.user_middleware:
            middleware.kwargs.pop("limiter", None)
        server.app.middleware_stack = None

    def test_security_headers(self):
        response = self.client.post("/api/stats", json=body())
        self.assertEqual(response.status_code, 200)
        csp = response.headers["content-security-policy"]
        self.assertIn("script-src 'self'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")
        # Errors get them too
        self.assertIn("content-security-policy", self.client.get("/api/cards/abc/image").headers)

    def test_large_body_rejected(self):
        response = self.client.post("/api/stats", content=b"{" + b" " * 70_000 + b"}",
                                    headers={"content-type": "application/json"})
        self.assertEqual(response.status_code, 413)

    def test_rate_limit(self):
        from ygo_calc.web.security import SecurityMiddleware
        with patch.dict("ygo_calc.web.security.RATE_LIMITS", {"decks": 2, "images": 600, "api": 300}):
            self.server.app.middleware_stack = None
            client = TestClient(self.server.app)
            codes = [client.post("/api/decks", json={"code": "nonsense"}).status_code for _ in range(3)]
        self.assertEqual(codes[:2], [400, 400])
        self.assertEqual(codes[2], 429)
        self.assertIsNotNone(SecurityMiddleware)

    def test_docs_hidden(self):
        for path in ("/api/docs", "/redoc", "/api/openapi.json"):
            self.assertEqual(self.client.get(path).status_code, 404, path)

    def test_card_ids_must_be_plain_numbers(self):
        for card_id in ("١٢٣", "12345678901", "..%2F..%2Fetc", "1e5"):
            self.assertEqual(self.client.get(f"/api/cards/{card_id}/image").status_code, 404, card_id)

    def test_huge_deck_code_not_looked_up(self):
        ydk = "#main\n" + "\n".join(str(1000 + i) for i in range(500))
        with patch("ygo_calc.deck_loading.fetch_multiple_card_names") as lookup:
            response = self.client.post("/api/decks", json={"code": ydk})
        self.assertEqual(response.status_code, 400)
        self.assertIn("at most 60", response.json()["detail"])
        lookup.assert_not_called()


@unittest.skipIf(TestClient is None, "web dependencies not installed")
class TestMissingImages(unittest.TestCase):
    def test_missing_image_not_fetched_again(self):
        from ygo_calc.web import images
        with patch.object(images, "fetch_bytes", side_effect=OSError("offline")) as fetch, \
             patch.object(images, "image_cache_dir", return_value=os.path.join(ROOT, "tests")):
            images._missing.clear()
            self.assertIsNone(images.load_card_image("999999991", "small"))
            calls = fetch.call_count
            self.assertIsNone(images.load_card_image("999999991", "small"))
            self.assertEqual(fetch.call_count, calls)  # remembered as missing
            self.assertEqual(images._locks, {})        # no lock left behind
        images._missing.clear()


@unittest.skipIf(TestClient is None, "web dependencies not installed")
class TestNewImages(unittest.TestCase):
    def test_downloaded_image_sent_at_once_then_cached(self):
        import tempfile
        import time
        from ygo_calc.web import images
        with tempfile.TemporaryDirectory() as cache_dir, \
             patch.object(images, "fetch_bytes", return_value=b"jpeg") as fetch, \
             patch.object(images, "image_cache_dir", return_value=cache_dir):
            self.assertEqual(images.load_card_image("999999992", "small"), b"jpeg")
            # Saved in the background; until then it's answered from memory, not downloaded again
            deadline = time.monotonic() + 5
            while images._saving and time.monotonic() < deadline:
                self.assertIn(images.load_card_image("999999992", "small"), (b"jpeg", os.path.join(cache_dir, "999999992_small.jpg")))
                time.sleep(0.01)
            path = os.path.join(cache_dir, "999999992_small.jpg")
            self.assertEqual(images.load_card_image("999999992", "small"), path)
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"jpeg")
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(os.listdir(cache_dir), ["999999992_small.jpg"])  # no temp file left

    def test_api_serves_new_and_cached_images(self):
        import tempfile
        import time
        from ygo_calc.web import images
        from ygo_calc.web.server import app
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as cache_dir, \
             patch.object(images, "fetch_bytes", return_value=b"jpeg"), \
             patch.object(images, "image_cache_dir", return_value=cache_dir):
            response = client.get("/api/cards/999999993/image")      # just downloaded
            self.assertEqual((response.status_code, response.content), (200, b"jpeg"))
            self.assertEqual(response.headers["content-type"], "image/jpeg")
            self.assertIn("immutable", response.headers["cache-control"])
            deadline = time.monotonic() + 5
            while images._saving and time.monotonic() < deadline:   # the background save
                time.sleep(0.01)
            self.assertEqual(os.listdir(cache_dir), ["999999993_small.jpg"])
            response = client.get("/api/cards/999999993/image")      # now from the cache file
            self.assertEqual((response.status_code, response.content), (200, b"jpeg"))
            self.assertIn("immutable", response.headers["cache-control"])


class TestOutboundRequests(unittest.TestCase):
    def test_only_card_sites_over_https(self):
        from ygo_calc.cards.http import BlockedURLError, check_url, fetch_bytes
        self.assertTrue(check_url("https://images.ygoprodeck.com/images/cards/1.jpg"))
        self.assertTrue(check_url("https://pics.projectignis.org:2096/pics/1.jpg"))
        for url in ("http://169.254.169.254/latest/meta-data/", "https://localhost/",
                    "http://images.ygoprodeck.com/1.jpg", "https://images.ygoprodeck.com.evil.example/1.jpg",
                    "https://a:b@images.ygoprodeck.com/", "file:///etc/passwd"):
            with self.assertRaises(BlockedURLError, msg=url):
                fetch_bytes(url, timeout=1)

    def test_redirects_checked(self):
        import urllib.request
        from ygo_calc.cards.http import BlockedURLError, _CheckedRedirects
        req = urllib.request.Request("https://images.ygoprodeck.com/x.jpg")
        with self.assertRaises(BlockedURLError):
            _CheckedRedirects().redirect_request(req, None, 302, "Found", {}, "http://10.0.0.1/admin")

    def test_database_names_are_plain_file_names(self):
        from ygo_calc.cards.edopro import SAFE_CDB_NAME
        for name in ("cards.cdb", "prerelease-others.cdb"):
            self.assertTrue(SAFE_CDB_NAME.fullmatch(name), name)
        for name in ("../cards.cdb", "a/b.cdb", "..\\x.cdb", ".hidden.cdb", "cards.cdb.exe", "x" * 120 + ".cdb"):
            self.assertIsNone(SAFE_CDB_NAME.fullmatch(name), name)

    def test_unsafe_database_name_never_downloaded(self):
        from ygo_calc.cards import edopro
        with patch.object(edopro, "fetch_bytes") as fetch, patch.object(edopro, "_edopro_cache_dir", return_value=ROOT):
            self.assertEqual(edopro._edopro_cdb_path("../../evil.cdb"), "")
        fetch.assert_not_called()


class TestRateLimitLogging(unittest.TestCase):
    def test_logged_once_per_window(self):
        limiter = RateLimiter({"api": 1}, window=60)
        with self.assertLogs(level="WARNING") as logs:
            for t in range(5):
                limiter.check("1.2.3.4", "api", now=t)
        self.assertEqual(len(logs.records), 1)
        self.assertIn("1.2.3.4", logs.output[0])


if __name__ == '__main__':
    unittest.main()
