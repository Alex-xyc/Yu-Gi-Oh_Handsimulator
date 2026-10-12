"""Card images for the web app, downloaded once and then served from a disk cache.

YGOPRODeck asks sites not to hotlink its images, so the server fetches each image
once and serves its own copy.
"""

import logging
import os
import threading
import time
from typing import Dict, List, Optional

from ..cards import cache
from ..cards.edopro import EDOPRO_IMAGE_URL
from ..cards.http import fetch_bytes

YGOPRODECK_IMAGE_URLS = {
    "small": "https://images.ygoprodeck.com/images/cards_small/{card_id}.jpg",
    "full": "https://images.ygoprodeck.com/images/cards/{card_id}.jpg",
}
SIZES = tuple(YGOPRODECK_IMAGE_URLS)

# Card images are well under this; anything bigger isn't a card image
MAX_IMAGE_BYTES = 5 * 1024 * 1024
# IDs with no image anywhere aren't tried again for a while (so made-up IDs can't make the
# server call the image sites over and over), up to a bounded number of them
MISSING_FOR_SECONDS = 6 * 60 * 60
MAX_MISSING = 10_000

_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
_missing: Dict[str, float] = {}


def image_cache_dir() -> str:
    """Where downloaded images are kept: $YGO_CACHE_DIR/images, or the user cache folder."""
    base = os.environ.get("YGO_CACHE_DIR")
    if not base:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
        base = os.path.join(local, "YGO-Calc")
    path = os.path.join(base, "images")
    os.makedirs(path, exist_ok=True)
    return path


def image_urls(card_id: str, size: str) -> List[str]:
    """Image URLs to try for a card ID, in order: YGOPRODeck, then EDOPro."""
    real_id = cache.aliases.get(card_id, card_id)
    urls = [YGOPRODECK_IMAGE_URLS[size].format(card_id=real_id)]
    if size == "small" and cache.image_urls.get(card_id):
        urls.insert(0, cache.image_urls[card_id])
    urls.append(EDOPRO_IMAGE_URL.format(card_id=real_id))
    return list(dict.fromkeys(urls))


def card_image_path(card_id: str, size: str) -> Optional[str]:
    """Path of the cached image file, downloading it first if needed (None if unavailable)."""
    path = os.path.join(image_cache_dir(), f"{card_id}_{size}.jpg")
    if os.path.exists(path):
        return path
    if time.monotonic() < _missing.get(path, 0):
        return None
    # One download per image, even when several requests for it arrive at once
    with _locks_guard:
        lock = _locks.setdefault(path, threading.Lock())
    try:
        with lock:
            if os.path.exists(path):
                return path
            for url in image_urls(card_id, size):
                try:
                    data = fetch_bytes(url, timeout=10, max_bytes=MAX_IMAGE_BYTES)
                except Exception:
                    logging.warning("Failed to load image for %s from %s", card_id, url)
                    continue
                temp = f"{path}.{threading.get_ident()}.part"
                with open(temp, "wb") as f:
                    f.write(data)
                os.replace(temp, path)
                return path
            _remember_missing(path)
            return None
    finally:
        with _locks_guard:
            if _locks.get(path) is lock and not lock.locked():
                del _locks[path]


def _remember_missing(path: str):
    now = time.monotonic()
    if len(_missing) >= MAX_MISSING:
        for key in [key for key, until in _missing.items() if until <= now] or list(_missing)[:MAX_MISSING // 10]:
            _missing.pop(key, None)
    _missing[path] = now + MISSING_FOR_SECONDS
