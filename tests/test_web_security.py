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

    def test_client_ignoring_refusals_is_blocked(self):
        limiter = RateLimiter({"api": 2, "images": 100}, window=60, block_seconds=600)
        for second in range(2):
            self.assertIsNone(limiter.check("a", "api", now=second))
        self.assertLess(limiter.check("a", "api", now=2), 600)        # refused, until the window ends
        self.assertEqual(limiter.check("a", "api", now=3), 600)       # 2x the limit: blocked
        self.assertIsNotNone(limiter.check("a", "api", now=100))      # still blocked in the next window
        self.assertIsNotNone(limiter.check("a", "images", now=100))   # for everything
        self.assertIsNone(limiter.check("b", "api", now=100))         # others aren't
        self.assertIsNone(limiter.check("a", "api", now=605))         # block over

    def test_clients_remembered_are_bounded(self):
        limiter = RateLimiter({"api": 5}, window=60, max_clients=100)
        for i in range(1000):
            limiter.check(f"10.0.{i // 256}.{i % 256}", "api", now=1)
        self.assertLessEqual(len(limiter._counts), 100)

    def test_client_address_from_proxy_not_spoofable(self):
        from ygo_calc.web.security import client_address
        scope = {"client": ("10.1.1.1", 0), "headers": [(b"x-forwarded-for", b"6.6.6.6, 203.0.113.9")]}
        self.assertEqual(client_address(scope, 0), "10.1.1.1")       # no proxy: the connecting address
        self.assertEqual(client_address(scope, 1), "203.0.113.9")    # the address the proxy added
        self.assertEqual(client_address({"client": ("10.1.1.1", 0), "headers": []}, 1), "10.1.1.1")

    def test_client_address_check_logged_when_asked(self):
        import asyncio
        from ygo_calc.web.security import SecurityMiddleware

        async def app(_scope, _receive, _send):
            pass

        scope = {"type": "http", "method": "GET", "path": "/api/cards/1/image", "client": ("10.1.1.1", 0),
                 "headers": [(b"x-forwarded-for", b"6.6.6.6, 203.0.113.9")]}
        with patch.dict(os.environ, {"YGO_LOG_CLIENT": "1"}):
            middleware = SecurityMiddleware(app, proxy_hops=1)
        with self.assertLogs(level="WARNING") as logs:
            asyncio.run(middleware(scope, None, None))
        self.assertIn("6.6.6.6, 203.0.113.9", logs.output[0])
        self.assertIn("rate limited as 203.0.113.9", logs.output[0])

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
    def tearDown(self):
        from ygo_calc.web import images
        images._missing.clear()
        images._unavailable.clear()

    def test_missing_image_not_fetched_again(self):
        import urllib.error
        from ygo_calc.web import images
        not_found = urllib.error.HTTPError("https://x", 404, "Not Found", None, None)
        with patch.object(images, "fetch_bytes", side_effect=not_found) as fetch, \
             patch.object(images, "image_cache_dir", return_value=os.path.join(ROOT, "tests")):
            self.assertIsNone(images.load_card_image("999999991", "small"))
            calls = fetch.call_count
            self.assertIsNone(images.load_card_image("999999991", "small"))
            self.assertEqual(fetch.call_count, calls)  # remembered as missing
            self.assertEqual(images._locks, {})        # no lock left behind

    def test_unreachable_sites_mean_try_again_soon(self):
        import urllib.error
        from ygo_calc.web import images
        not_found = urllib.error.HTTPError("https://x", 404, "Not Found", None, None)
        with patch.object(images, "fetch_bytes", side_effect=[not_found, OSError("offline")]) as fetch, \
             patch.object(images, "image_cache_dir", return_value=os.path.join(ROOT, "tests")):
            with self.assertRaises(images.ImageUnavailable):
                images.load_card_image("999999995", "small")
            calls = fetch.call_count
            with self.assertRaises(images.ImageUnavailable) as raised:   # not asked again for now
                images.load_card_image("999999995", "small")
            self.assertEqual(fetch.call_count, calls)
            self.assertLessEqual(raised.exception.retry_after, images.UNAVAILABLE_FOR_SECONDS)
            self.assertEqual(images._missing, {})   # not taken for a card without an image

    def test_api_answers_503_while_unavailable(self):
        from ygo_calc.web import images
        from ygo_calc.web.server import app
        with patch.object(images, "fetch_bytes", side_effect=OSError("offline")), \
             patch.object(images, "image_cache_dir", return_value=os.path.join(ROOT, "tests")):
            response = TestClient(app).get("/api/cards/999999996/image")
        self.assertEqual(response.status_code, 503)
        self.assertTrue(response.headers["retry-after"].isdigit())
        self.assertNotIn("immutable", response.headers.get("cache-control", ""))


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
                self.assertEqual(images.load_card_image("999999992", "small"), b"jpeg")
                time.sleep(0.01)
            path = os.path.join(cache_dir, "999999992_small.jpg")
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"jpeg")
            self.assertEqual(os.listdir(cache_dir), ["999999992_small.jpg"])  # no temp file left
            # From memory, then (once memory is cleared, e.g. after a restart) from the cache folder
            self.assertEqual(images.load_card_image("999999992", "small"), b"jpeg")
            images._memory.clear()
            self.assertEqual(images.load_card_image("999999992", "small"), b"jpeg")
            self.assertEqual(fetch.call_count, 1)

    def test_memory_cache_drops_least_recently_used(self):
        from ygo_calc.web.images import _MemoryCache
        memory = _MemoryCache(max_bytes=10)
        memory.put("a", b"1234")
        memory.put("b", b"1234")
        memory.get("a")                 # a is now the most recent
        memory.put("c", b"1234")        # over 10 bytes: b goes
        self.assertEqual((memory.get("a"), memory.get("b"), memory.get("c")), (b"1234", None, b"1234"))
        memory.put("huge", b"x" * 11)   # bigger than the whole cache: not kept
        self.assertIsNone(memory.get("huge"))

    def test_api_serves_new_and_cached_images(self):
        import tempfile
        import time
        from ygo_calc.web import images
        from ygo_calc.web.server import app
        client = TestClient(app)
        with tempfile.TemporaryDirectory() as cache_dir, \
             patch.object(images, "fetch_bytes", return_value=b"jpeg"), \
             patch.object(images, "image_cache_dir", return_value=cache_dir), \
             patch.dict(images.cache.names, {"999999993": "A card"}):   # a deck lookup found it
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

    def test_requests_to_a_host_are_spaced_out(self):
        import time
        from ygo_calc.cards import http
        throttle = http._Throttle()
        start = time.monotonic()
        for _ in range(4):
            throttle.acquire("images.ygoprodeck.com").release()
        self.assertGreaterEqual(time.monotonic() - start, 3 * http.MIN_INTERVAL * 0.9)
        throttle.acquire("other.example").release()   # other hosts don't wait their turn

    def test_host_left_alone_after_429(self):
        import io
        import urllib.error
        from ygo_calc.cards import http
        error = urllib.error.HTTPError("https://db.ygoprodeck.com/", 429, "Too Many Requests",
                                       {"Retry-After": "120"}, io.BytesIO())
        with patch.object(http, "_throttle", http._Throttle()), \
             patch.object(http._opener, "open", side_effect=error) as opened:
            with self.assertRaises(urllib.error.HTTPError):
                http.fetch_bytes("https://db.ygoprodeck.com/api/v7/cardinfo.php", timeout=1)
            with self.assertRaises(http.HostBusyError):   # not sent at all
                http.fetch_bytes("https://db.ygoprodeck.com/api/v7/cardinfo.php", timeout=1)
            self.assertEqual(opened.call_count, 1)

    def test_requests_a_minute_capped_per_host(self):
        from ygo_calc.cards import http
        throttle = http._Throttle(max_per_minute=3)
        with patch.object(http, "MIN_INTERVAL", 0):
            for _ in range(3):
                throttle.acquire("db.ygoprodeck.com").release()
            with self.assertRaises(http.HostBusyError):
                throttle.acquire("db.ygoprodeck.com")
            with self.assertRaises(http.HostBusyError):   # held off for the rest of the minute
                throttle.acquire("db.ygoprodeck.com")
            throttle.acquire("pics.projectignis.org").release()

    def test_failing_host_left_alone_for_a_while(self):
        from ygo_calc.cards import http
        with patch.object(http, "_throttle", http._Throttle()), patch.object(http, "MIN_INTERVAL", 0), \
             patch.object(http._opener, "open", side_effect=TimeoutError("timed out")) as opened:
            for _ in range(http.FAILURES_BEFORE_PAUSE):
                with self.assertRaises(TimeoutError):
                    http.fetch_bytes("https://images.ygoprodeck.com/images/cards/1.jpg", timeout=1)
            with self.assertRaises(http.HostBusyError):
                http.fetch_bytes("https://images.ygoprodeck.com/images/cards/1.jpg", timeout=1)
            self.assertEqual(opened.call_count, http.FAILURES_BEFORE_PAUSE)

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

    def test_made_up_card_ids_not_looked_up_again(self):
        import urllib.error
        from ygo_calc.cards import cache, ygoprodeck
        not_a_card = urllib.error.HTTPError("https://db.ygoprodeck.com/", 400, "Bad Request", None, None)
        cache.unknown.clear()
        try:
            with patch.object(ygoprodeck, "fetch_json", side_effect=not_a_card) as lookup, \
                 patch.object(ygoprodeck, "fetch_edopro_card_names", return_value={}) as edopro:
                ygoprodeck.fetch_card_infos(["999999997"])
                ygoprodeck.fetch_card_infos(["999999997"])
                ygoprodeck.fetch_multiple_card_names(["999999997"], verbose=False)
            self.assertEqual((lookup.call_count, edopro.call_count), (1, 1))
        finally:
            cache.unknown.clear()

    def test_card_ids_looked_up_again_if_ygoprodeck_unreachable(self):
        from ygo_calc.cards import cache, ygoprodeck
        cache.unknown.clear()
        with patch.object(ygoprodeck, "fetch_json", side_effect=OSError("offline")) as lookup, \
             patch.object(ygoprodeck, "fetch_edopro_card_names", return_value={}):
            ygoprodeck.fetch_card_infos(["999999998"])
            ygoprodeck.fetch_card_infos(["999999998"])
        self.assertEqual(lookup.call_count, 2)
        self.assertEqual(cache.unknown, {})

    def test_edopro_listing_asked_for_once(self):
        from ygo_calc.cards import edopro
        with patch.object(edopro, "_names_cache", (0.0, [])), \
             patch.object(edopro, "fetch_json", return_value=[{"name": "extra.cdb"}]) as listing:
            self.assertIn("extra.cdb", edopro._edopro_cdb_names())
            self.assertIn("extra.cdb", edopro._edopro_cdb_names())
        self.assertEqual(listing.call_count, 1)

    def test_failed_database_download_not_retried_at_once(self):
        import tempfile
        from ygo_calc.cards import edopro
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(edopro, "_failed_at", {}), \
             patch.object(edopro, "_edopro_cache_dir", return_value=folder), \
             patch.object(edopro, "_edopro_store_dir", return_value=""), \
             patch.object(edopro, "fetch_bytes", side_effect=OSError("offline")) as fetch:
            self.assertEqual(edopro._edopro_cdb_path("cards.cdb"), "")
            self.assertEqual(edopro._edopro_cdb_path("cards.cdb"), "")
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(os.listdir(folder), [])   # no half-written file left

    def test_unsafe_database_name_never_downloaded(self):
        from ygo_calc.cards import edopro
        with patch.object(edopro, "fetch_bytes") as fetch, patch.object(edopro, "_edopro_cache_dir", return_value=ROOT):
            self.assertEqual(edopro._edopro_cdb_path("../../evil.cdb"), "")
        fetch.assert_not_called()


class TestEdoproStore(unittest.TestCase):
    """The EDOPro databases are kept in the cache folder (on Cloud Run the bucket) as well, so a
    restarted server copies them from there instead of downloading them again."""
    DATABASE = b"SQLite format 3\x00" + b"cards"

    def setUp(self):
        import shutil
        import tempfile
        from ygo_calc.cards import edopro
        self.edopro = edopro
        self.real_store_dir = edopro._edopro_store_dir
        self.local, self.store = tempfile.mkdtemp(), tempfile.mkdtemp()
        for folder in (self.local, self.store):
            self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        self._patches = [patch.object(edopro, "_failed_at", {}),
                         patch.object(edopro, "_edopro_cache_dir", return_value=self.local),
                         patch.object(edopro, "_edopro_store_dir", return_value=self.store)]
        for p in self._patches:
            p.start()
            self.addCleanup(p.stop)

    def read(self, folder):
        with open(os.path.join(folder, "cards.cdb"), "rb") as f:
            return f.read()

    def test_downloaded_database_stored(self):
        with patch.object(self.edopro, "fetch_bytes", return_value=self.DATABASE):
            self.assertEqual(self.edopro._edopro_cdb_path("cards.cdb"), os.path.join(self.local, "cards.cdb"))
        self.assertEqual(self.read(self.local), self.DATABASE)
        self.assertEqual(self.read(self.store), self.DATABASE)

    def test_stored_database_used_without_downloading(self):
        with open(os.path.join(self.store, "cards.cdb"), "wb") as f:
            f.write(self.DATABASE)
        with patch.object(self.edopro, "fetch_bytes") as fetch:
            self.assertEqual(self.edopro._edopro_cdb_path("cards.cdb"), os.path.join(self.local, "cards.cdb"))
        fetch.assert_not_called()
        self.assertEqual(self.read(self.local), self.DATABASE)
        self.assertEqual(os.listdir(self.local), ["cards.cdb"])   # no temp file left

    def test_stale_stored_database_replaced_or_used_as_last_resort(self):
        import time
        stored = os.path.join(self.store, "cards.cdb")
        with open(stored, "wb") as f:
            f.write(b"SQLite format 3\x00old")
        week_ago = time.time() - self.edopro.EDOPRO_CACHE_MAX_AGE - 60
        os.utime(stored, (week_ago, week_ago))
        # Can't download a new one: the old one beats none
        with patch.object(self.edopro, "fetch_bytes", side_effect=OSError("offline")):
            self.assertEqual(self.edopro._edopro_cdb_path("cards.cdb"), os.path.join(self.local, "cards.cdb"))
        self.assertEqual(self.read(self.local), b"SQLite format 3\x00old")
        # Once it can, the new one replaces both copies
        self.edopro._failed_at.clear()
        os.utime(os.path.join(self.local, "cards.cdb"), (week_ago, week_ago))
        with patch.object(self.edopro, "fetch_bytes", return_value=self.DATABASE):
            self.edopro._edopro_cdb_path("cards.cdb")
        self.assertEqual((self.read(self.local), self.read(self.store)), (self.DATABASE, self.DATABASE))

    def test_store_only_when_cache_folder_is_elsewhere(self):
        with patch.dict(os.environ, {"YGO_CACHE_DIR": self.store}):
            # Cloud Run: used from /tmp, kept in the bucket
            self.assertEqual(self.real_store_dir(), os.path.join(self.store, "edopro"))
            # Docker Compose: both are the same volume, so there's nothing to copy
            with patch.object(self.edopro, "_edopro_cache_dir", return_value=os.path.join(self.store, "edopro")):
                self.assertEqual(self.real_store_dir(), "")
        with patch.dict(os.environ, {"YGO_CACHE_DIR": ""}):
            self.assertEqual(self.real_store_dir(), "")   # the desktop app


@unittest.skipIf(TestClient is None, "web dependencies not installed")
class TestAsyncImages(unittest.TestCase):
    def tearDown(self):
        from ygo_calc.web import images
        images._memory.clear()

    def test_memory_hit_needs_no_worker_thread(self):
        import asyncio
        from ygo_calc.web import images
        images._memory.put("999999981_small", b"jpeg")
        with patch.object(images, "run_in_threadpool", side_effect=AssertionError("used a thread")):
            self.assertEqual(asyncio.run(images.get_card_image("999999981", "small")), b"jpeg")

    def test_cache_folder_read_then_kept_in_memory(self):
        import asyncio
        import tempfile
        from ygo_calc.web import images
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(images, "image_cache_dir", return_value=folder), \
             patch.object(images, "fetch_bytes") as fetch:
            with open(os.path.join(folder, "999999982_full.jpg"), "wb") as f:
                f.write(b"jpeg")
            self.assertEqual(asyncio.run(images.get_card_image("999999982", "full")), b"jpeg")
            self.assertEqual(images._memory.get("999999982_full"), b"jpeg")
        fetch.assert_not_called()

    def test_too_many_waiting_downloads_told_to_try_again(self):
        import tempfile
        import threading
        from ygo_calc.web import images
        from ygo_calc.web.server import app
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(images, "image_cache_dir", return_value=folder), \
             patch.object(images, "_download_slots", threading.BoundedSemaphore(1)) as slots, \
             patch.dict(images.cache.names, {"999999983": "A card"}), \
             patch.object(images, "fetch_bytes") as fetch:
            slots.acquire()   # the one slot is taken
            response = TestClient(app).get("/api/cards/999999983/image")
            slots.release()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["retry-after"], str(images.BUSY_RETRY_SECONDS))
        fetch.assert_not_called()

    def test_unknown_card_images_not_downloaded(self):
        import tempfile
        from ygo_calc.web import images
        from ygo_calc.web.server import app
        with tempfile.TemporaryDirectory() as folder, \
             patch.object(images, "image_cache_dir", return_value=folder), \
             patch.dict(images.cache.unknown, {"999999985": float("inf")}), \
             patch.object(images, "fetch_bytes") as fetch:
            client = TestClient(app)
            # Not looked up yet (maybe a real card in a saved deck): try again shortly
            self.assertEqual(client.get("/api/cards/999999984/image").status_code, 503)
            # Looked up, and no source knew it
            self.assertEqual(client.get("/api/cards/999999985/image").status_code, 404)
        fetch.assert_not_called()


class TestRateLimitLogging(unittest.TestCase):
    def test_logged_once_per_window(self):
        limiter = RateLimiter({"api": 1}, window=60)
        with self.assertLogs(level="WARNING") as logs:
            for t in range(5):
                limiter.check("1.2.3.4", "api", now=t)
        # Once when refused, once when blocked; nothing while blocked
        self.assertEqual(len(logs.records), 2)
        self.assertIn("refusing", logs.output[0])
        self.assertIn("blocking", logs.output[1])
        self.assertIn("1.2.3.4", logs.output[0])


if __name__ == '__main__':
    unittest.main()
