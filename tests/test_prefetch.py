"""Tests for loading the whole card list and prefetching card images (the network is mocked)."""
import os
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from ygo_calc.cards import cache, catalog, ygoprodeck
from ygo_calc.cards.http import HostBusyError

try:
    from ygo_calc.web import images
except ImportError:  # The web dependencies are optional (requirements-web.txt)
    images = None

SMALL = "https://images.ygoprodeck.com/images/cards_small/{}.jpg"
CARD_LIST = {"data": [
    {"id": 100, "name": "Ash &amp; Blossom", "type": "Effect Monster", "frameType": "effect", "level": 3,
     "banlist_info": {"ban_tcg": "Limited"}, "misc_info": [{"formats": ["TCG", "OCG"], "genesys_points": 18}],
     "card_images": [{"id": 100, "image_url_small": SMALL.format(100)},
                     {"id": 101, "image_url_small": SMALL.format(101)}]},
    {"id": 200, "name": "Called by the Grave", "type": "Spell Card", "frameType": "spell", "race": "Quick-Play",
     "misc_info": [{"formats": ["OCG"]}], "card_images": [{"id": 200, "image_url_small": SMALL.format(200)}]},
]}


def fake_json(versions):
    def fetch(url, timeout, **_):  # pylint: disable=unused-argument
        if url == catalog.DB_VERSION_URL:
            return [{"database_version": versions.pop(0)}]
        return CARD_LIST
    return fetch


class TestCatalog(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        env = patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp})
        env.start()
        self.addCleanup(env.stop)
        for name, value in (('names', {}), ('info', {}), ('image_urls', {}), ('full_list', False)):
            saved = patch.object(cache, name, value)
            saved.start()
            self.addCleanup(saved.stop)

    def test_downloads_and_fills_the_caches(self):
        with patch.object(catalog, 'fetch_json', side_effect=fake_json(["1.0"])):
            ids = catalog.refresh()
        self.assertEqual(sorted(ids), ["100", "101", "200"])
        self.assertEqual(cache.names["100"], "Ash & Blossom")
        self.assertEqual(cache.info["100"], {"kind": "monster", "level": 3, "status": "limited", "points": 18})
        self.assertEqual(cache.info["200"], {"kind": "spell_quick_play", "level": 0, "status": "ocg", "points": 0})
        # An alternate artwork: the card's name, its own picture
        self.assertEqual(cache.names["101"], "Ash & Blossom")
        self.assertEqual(cache.image_urls["101"], SMALL.format(101))
        self.assertEqual(cache.info["101"]["points"], 18)
        self.assertTrue(os.path.exists(os.path.join(self.temp, "cards.json")))

    def test_saved_list_is_reused_until_the_version_changes(self):
        with patch.object(catalog, 'fetch_json', side_effect=fake_json(["1.0", "1.0", "2.0"])) as fetch:
            catalog.refresh()
            catalog.refresh()
            self.assertEqual(fetch.call_count, 3)  # version, list, version
            catalog.refresh()
            self.assertEqual(fetch.call_count, 5)  # a newer version: the list again

    def test_saved_list_is_used_when_ygoprodeck_cant_be_reached(self):
        with patch.object(catalog, 'fetch_json', side_effect=fake_json(["1.0"])):
            catalog.refresh()
        cache.names.clear()
        with patch.object(catalog, 'fetch_json', side_effect=OSError("offline")):
            ids = catalog.refresh()
        self.assertEqual(len(ids), 3)
        self.assertEqual(cache.names["200"], "Called by the Grave")

    def test_no_list_and_offline(self):
        with patch.object(catalog, 'fetch_json', side_effect=OSError("offline")):
            self.assertEqual(catalog.refresh(), [])
        self.assertFalse(cache.full_list)

    def test_ids_not_in_the_list_arent_sent_to_ygoprodeck(self):
        with patch.object(catalog, 'fetch_json', side_effect=fake_json(["1.0"])):
            catalog.refresh()
        with patch.object(ygoprodeck, 'fetch_json') as lookup, \
             patch.object(ygoprodeck, 'fetch_edopro_card_names', return_value={}) as edopro, \
             patch.object(cache, 'unknown', {}):
            infos = ygoprodeck.fetch_card_infos(["100", "999999971"])
            ygoprodeck.fetch_multiple_card_names(["999999972"], verbose=False)
            self.assertTrue(cache.recently_unknown("999999971"))
        lookup.assert_not_called()
        self.assertEqual(edopro.call_count, 2)  # still looked up there (cards YGOPRODeck lacks)
        self.assertEqual(infos["100"]["status"], "limited")


@unittest.skipIf(images is None, "the web dependencies are not installed")
class TestPrefetchImages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        env = patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp})
        env.start()
        self.addCleanup(env.stop)
        self.folder = images.image_cache_dir()
        self.stop = threading.Event()

    def cached(self, card_id):
        return os.path.join(self.folder, f"{card_id}_small.jpg")

    def test_downloads_only_missing_images(self):
        with open(self.cached("1"), "wb") as f:
            f.write(b"old")
        with patch.object(images, 'fetch_bytes', return_value=b"jpeg") as fetch:
            count = images.prefetch_images(["1", "2"], "small", 1000, self.stop)
        self.assertEqual(count, 1)
        fetch.assert_called_once()
        with open(self.cached("2"), "rb") as f:
            self.assertEqual(f.read(), b"jpeg")

    def test_missing_image_is_skipped(self):
        error = OSError("not found")
        error.code = 404
        with patch.object(images, 'fetch_bytes', side_effect=[error, b"jpeg"]):
            self.assertEqual(images.prefetch_images(["1", "2"], "small", 1000, self.stop), 1)
        self.assertFalse(os.path.exists(self.cached("1")))

    def test_gives_way_when_the_site_is_busy(self):
        with patch.object(images, 'fetch_bytes', side_effect=HostBusyError("busy")), \
             patch.object(self.stop, 'wait') as wait:
            images.prefetch_images(["1"], "small", 1000, self.stop)
        wait.assert_called_once_with(images.BUSY_PAUSE_SECONDS)

    def test_stops_when_asked(self):
        self.stop.set()
        with patch.object(images, 'fetch_bytes') as fetch:
            self.assertEqual(images.prefetch_images(["1", "2"], "small", 1000, self.stop), 0)
        fetch.assert_not_called()


if __name__ == '__main__':
    unittest.main()
