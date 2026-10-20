import os
import sys
import unittest
from unittest.mock import patch

# ensure src is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import tempfile

import card_cache
import main
from ygo_calc.cards import cache
from ygo_calc.cards.edopro import _edopro_info
from ygo_calc.cards.ygoprodeck import card_info


def mock_api(fake_data):
    """Patch the YGOPRODeck request and the EDOPro fallback so no network is used."""
    api = patch('ygo_calc.cards.ygoprodeck.fetch_json', return_value=fake_data)
    edopro = patch('ygo_calc.cards.ygoprodeck.fetch_edopro_card_names', return_value={})
    return api, edopro


class TestAPIMock(unittest.TestCase):
    def setUp(self):
        # Use an empty cache so the tests exercise the (mocked) API, not files on disk
        tmp = tempfile.TemporaryDirectory()  # pylint: disable=consider-using-with
        self.addCleanup(tmp.cleanup)
        self._env = patch.dict(os.environ, {'YGO_CACHE_DIR': tmp.name})
        self._env.start()
        card_cache._db = None
        card_cache._edopro = None
        cache.names.clear()
        cache.image_urls.clear()
        cache.aliases.clear()

    def tearDown(self):
        self._env.stop()
        card_cache._db = None
        card_cache._edopro = None

    def test_fetch_multiple_card_names_batch(self):
        # Prepare fake API response
        fake_data = {
            "data": [
                {"id": 100, "name": "Alpha", "card_images": [{"image_url_small": "http://img/alpha_small.png"}]},
                {"id": 200, "name": "Beta", "card_images": [{"image_url_small": "http://img/beta_small.png"}]}
            ]
        }
        api, edopro = mock_api(fake_data)
        with api, edopro:
            res = main.fetch_multiple_card_names(['100', '200'], verbose=False)
            # verify mapping and that cache was populated
            self.assertIn('100', res)
            self.assertEqual(res['100'], 'Alpha')
            self.assertEqual(main.get_card_image_url('100'), 'http://img/alpha_small.png')

    def test_fetch_multiple_card_names_empty(self):
        # If API returns empty data, function should return {} and not crash
        api, edopro = mock_api({"data": []})
        with api, edopro:
            res = main.fetch_multiple_card_names(['999'], verbose=False)
            self.assertEqual(res, {})

class TestBanStatus(unittest.TestCase):
    MONSTER = {"type": "Effect Monster", "frameType": "effect", "level": 3}

    def status(self, **fields):
        return card_info({**self.MONSTER, **fields})["status"]

    def test_tcg_banlist(self):
        self.assertEqual(self.status(banlist_info={"ban_tcg": "Forbidden", "ban_ocg": "Limited"}), "banned")
        self.assertEqual(self.status(banlist_info={"ban_tcg": "Limited"}), "limited")
        self.assertEqual(self.status(banlist_info={"ban_tcg": "Semi-Limited"}), "semi_limited")
        # Only the OCG's list doesn't count
        self.assertEqual(self.status(banlist_info={"ban_ocg": "Semi-Limited"},
                                     misc_info=[{"formats": ["TCG", "OCG"]}]), "")
        self.assertEqual(self.status(), "")

    def test_ocg_only(self):
        self.assertEqual(self.status(misc_info=[{"formats": ["OCG"]}]), "ocg")
        self.assertEqual(self.status(misc_info=[{"formats": ["TCG", "OCG"]}]), "")

    def test_edopro_regions(self):
        self.assertEqual(_edopro_info(0x21, 4, 0x1)["status"], "ocg")
        self.assertEqual(_edopro_info(0x21, 4, 0x101)["status"], "ocg")  # OCG pre-release
        self.assertEqual(_edopro_info(0x21, 4, 0x3)["status"], "")
        self.assertEqual(_edopro_info(0x21, 4, 0x102)["status"], "")  # TCG pre-release


if __name__ == '__main__':
    unittest.main()
