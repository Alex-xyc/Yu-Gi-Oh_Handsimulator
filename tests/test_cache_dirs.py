"""Tests for the cache folders: one that can't be created (e.g. a Docker volume owned by another
user) costs the cache, never the request (no network is used)."""
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from ygo_calc.cards import edopro

try:
    from ygo_calc.web import images
except ImportError:  # The web dependencies are optional (requirements-web.txt)
    images = None


class TestEdoproStoreDir(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with
        # The folder the databases are used from, apart from the store
        used = patch.object(edopro, '_edopro_cache_dir', return_value=os.path.join(self.temp, 'used'))
        used.start()
        self.addCleanup(used.stop)

    def test_no_store_without_cache_dir(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop('YGO_CACHE_DIR', None)
            self.assertEqual(edopro._edopro_store_dir(), '')

    def test_store_created_under_cache_dir(self):
        with patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp}):
            path = edopro._edopro_store_dir()
        self.assertEqual(path, os.path.join(self.temp, 'edopro'))
        self.assertTrue(os.path.isdir(path))

    def test_no_store_when_it_is_the_folder_in_use(self):
        with patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp}), \
             patch.object(edopro, '_edopro_cache_dir', return_value=os.path.join(self.temp, 'edopro')):
            self.assertEqual(edopro._edopro_store_dir(), '')

    def test_no_store_when_it_cant_be_created(self):
        with patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp}), \
             patch.object(edopro.os, 'makedirs', side_effect=PermissionError(13, 'Permission denied')), \
             self.assertLogs(level='ERROR'):
            self.assertEqual(edopro._edopro_store_dir(), '')


@unittest.skipIf(images is None, "web dependencies not installed")
class TestImageCacheDir(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())  # pylint: disable=consider-using-with

    def test_created_under_cache_dir(self):
        with patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp}):
            path = images.image_cache_dir()
        self.assertEqual(path, os.path.join(self.temp, 'images'))
        self.assertTrue(os.path.isdir(path))

    def test_folder_that_cant_be_created_only_costs_the_cache(self):
        with patch.dict(os.environ, {'YGO_CACHE_DIR': self.temp}), \
             patch.object(images.os, 'makedirs', side_effect=PermissionError(13, 'Permission denied')), \
             self.assertLogs(level='ERROR'):
            path = images.image_cache_dir()
            # Nothing cached there to read: a miss, not an error
            self.assertIsNone(images._from_disk('89631139', 'small'))
        self.assertEqual(path, os.path.join(self.temp, 'images'))


if __name__ == '__main__':
    unittest.main()
