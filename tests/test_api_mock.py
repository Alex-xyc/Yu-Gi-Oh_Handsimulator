import os
import sys
import unittest
import json
from unittest.mock import patch, MagicMock

# ensure src is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import tempfile

import card_cache
import main

class TestAPIMock(unittest.TestCase):
    def setUp(self):
        # Use an empty cache so the tests exercise the (mocked) API, not files on disk
        self._tmp = tempfile.TemporaryDirectory()
        self._env = patch.dict(os.environ, {'YGO_CACHE_DIR': self._tmp.name})
        self._env.start()
        card_cache._db = None
        card_cache._edopro = None
        main._card_name_cache.clear()
        main._card_image_cache.clear()

    def tearDown(self):
        self._env.stop()
        self._tmp.cleanup()
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
        fake_bytes = json.dumps(fake_data).encode('utf-8')

        class FakeResp:
            def __init__(self, data):
                self._data = data
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        with patch('urllib.request.urlopen', return_value=FakeResp(fake_bytes)) as m:
            res = main.fetch_multiple_card_names(['100', '200'], verbose=False)
            # verify mapping and that cache was populated
            self.assertIn('100', res)
            self.assertEqual(res['100'], 'Alpha')
            self.assertEqual(main.get_card_image_url('100'), 'http://img/alpha_small.png')

    def test_fetch_multiple_card_names_empty(self):
        # If API returns empty data, function should return {} and not crash
        fake_data = {"data": []}
        fake_bytes = json.dumps(fake_data).encode('utf-8')
        class FakeResp:
            def __init__(self, data):
                self._data = data
            def read(self):
                return self._data
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False

        with patch('urllib.request.urlopen', return_value=FakeResp(fake_bytes)):
            res = main.fetch_multiple_card_names(['999'], verbose=False)
            self.assertIsInstance(res, dict)

if __name__ == '__main__':
    unittest.main()
