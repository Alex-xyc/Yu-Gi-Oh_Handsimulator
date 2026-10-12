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

if __name__ == '__main__':
    unittest.main()
