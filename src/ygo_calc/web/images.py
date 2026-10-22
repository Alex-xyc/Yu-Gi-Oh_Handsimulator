"""Card images for the web app, downloaded once and then served from memory or a disk cache.

YGOPRODeck asks sites not to hotlink its images, so the server fetches each image
once and serves its own copy. get_card_image looks in turn at:

1. memory: the images served most recently. Answered straight from the event loop, so the
   common case never waits for a worker thread;
2. the cache folder: on Cloud Run a Cloud Storage bucket, where every file read takes a
   noticeable moment, so it is read in a worker thread (and the image kept in memory);
3. the image sites (throttled in cards/http.py), in a worker thread. Only a few requests may
   wait for a download at once, so downloads can't tie up the threads every other request
   needs; past that the caller is told to try again shortly. A freshly downloaded image is
   sent straight away and written to the cache folder in the background.
"""

import logging
import os
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional

from starlette.concurrency import run_in_threadpool

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
# Images kept in memory, by total size (small ones are ~10-30 KB, full ones ~100-150 KB)
MEMORY_CACHE_BYTES = int(os.environ.get("YGO_IMAGE_MEMORY_MB", "96")) * 1024 * 1024
# IDs with no image anywhere aren't tried again for a while (so made-up IDs can't make the
# server call the image sites over and over), up to a bounded number of them
MISSING_FOR_SECONDS = 6 * 60 * 60
# When the sites couldn't be reached (timeouts, errors, being throttled), only a short pause:
# the image probably exists and a later request should try again
UNAVAILABLE_FOR_SECONDS = 60
MAX_MISSING = 10_000
# Requests that may wait for a download at once. The server has 40 worker threads (Starlette's
# default), and each of these holds one while it waits its turn with the image sites; the rest
# stay free for everything else. Past this, requests are told to try again after BUSY_RETRY_SECONDS.
MAX_DOWNLOADS_WAITING = 16
BUSY_RETRY_SECONDS = 5


class ImageUnavailable(Exception):
    """The image can't be had just now (the sites can't be reached, we're holding off them, or
    too many downloads are waiting); try again after retry_after seconds."""

    def __init__(self, retry_after: float):
        super().__init__(f"Card image unavailable for {retry_after:.0f}s")
        self.retry_after = retry_after


class _MemoryCache:
    """The most recently used images, up to a total size."""

    def __init__(self, max_bytes: int):
        self.max_bytes = max_bytes
        self._items: "OrderedDict[str, bytes]" = OrderedDict()
        self._size = 0
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[bytes]:
        with self._lock:
            data = self._items.get(key)
            if data is not None:
                self._items.move_to_end(key)
            return data

    def put(self, key: str, data: bytes):
        if len(data) > self.max_bytes:
            return
        with self._lock:
            old = self._items.pop(key, None)
            if old is not None:
                self._size -= len(old)
            self._items[key] = data
            self._size += len(data)
            while self._size > self.max_bytes:
                _, dropped = self._items.popitem(last=False)
                self._size -= len(dropped)

    def clear(self):
        with self._lock:
            self._items.clear()
            self._size = 0


# All keyed by "<card id>_<size>"
_memory = _MemoryCache(MEMORY_CACHE_BYTES)
# Downloaded images still being written to the cache folder, so they aren't downloaded again
_saving: Dict[str, bytes] = {}
_missing: Dict[str, float] = {}
_unavailable: Dict[str, float] = {}
_locks: Dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()
# Taken without waiting: a slot for each request allowed to wait for a download
_download_slots = threading.BoundedSemaphore(MAX_DOWNLOADS_WAITING)


def image_cache_dir() -> str:
    """Where downloaded images are kept: $YGO_CACHE_DIR/images, or the user cache folder."""
    base = os.environ.get("YGO_CACHE_DIR")
    if not base:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
        base = os.path.join(local, "YGO-Calc")
    path = os.path.join(base, "images")
    # Without it images are still served, just not kept (reading and saving them handle that)
    try:
        os.makedirs(path, exist_ok=True)
    except OSError:
        logging.exception("Can't create the image cache folder %s", path)
    return path


def image_urls(card_id: str, size: str) -> List[str]:
    """Image URLs to try for a card ID, in order: YGOPRODeck, then EDOPro."""
    real_id = cache.aliases.get(card_id, card_id)
    urls = [YGOPRODECK_IMAGE_URLS[size].format(card_id=real_id)]
    if size == "small" and cache.image_urls.get(card_id):
        urls.insert(0, cache.image_urls[card_id])
    urls.append(EDOPRO_IMAGE_URL.format(card_id=real_id))
    return list(dict.fromkeys(urls))


async def get_card_image(card_id: str, size: str) -> Optional[bytes]:
    """A card's image for the API (see the module docstring for where it comes from). None if
    the card has no image; raises ImageUnavailable if it can't be had just now."""
    key = _key(card_id, size)
    data = _from_memory(key)
    if data is not None:
        return data
    if _known_missing(key):
        return None
    data = await run_in_threadpool(_from_disk, card_id, size)
    if data is not None:
        return data
    # Taken without waiting (a `with` block would wait for one), and released below
    if not _download_slots.acquire(blocking=False):  # pylint: disable=consider-using-with
        raise ImageUnavailable(BUSY_RETRY_SECONDS)
    try:
        return await run_in_threadpool(load_card_image, card_id, size)
    finally:
        _download_slots.release()


def load_card_image(card_id: str, size: str) -> Optional[bytes]:
    """A card's image from memory, the cache folder, or (downloaded, then saved in the
    background) the image sites, blocking until it has it. None if the card has no image;
    raises ImageUnavailable if the sites can't be reached just now."""
    key = _key(card_id, size)
    data = _from_memory(key)
    if data is None:
        data = _from_disk(card_id, size)
    if data is not None or _known_missing(key):
        return data
    # One download per image, even when several requests for it arrive at once
    with _locks_guard:
        lock = _locks.setdefault(key, threading.Lock())
    try:
        with lock:
            # Another request may have just downloaded it, or found the sites unavailable
            data = _from_memory(key)
            if data is not None or _known_missing(key):
                return data
            return _download(card_id, size)
    finally:
        with _locks_guard:
            if _locks.get(key) is lock and not lock.locked():
                del _locks[key]


def _key(card_id: str, size: str) -> str:
    return f"{card_id}_{size}"


def _from_memory(key: str) -> Optional[bytes]:
    """The image if it's in memory (never blocks, so it is safe on the event loop)."""
    data = _memory.get(key)
    return data if data is not None else _saving.get(key)


def _known_missing(key: str) -> bool:
    """True if the card is known to have no image; raises ImageUnavailable while the image
    sites are being left alone for it. Never blocks."""
    now = time.monotonic()
    if now < _missing.get(key, 0):
        return True
    wait = _unavailable.get(key, 0) - now
    if wait > 0:
        raise ImageUnavailable(wait)
    return False


def _from_disk(card_id: str, size: str) -> Optional[bytes]:
    """The image from the cache folder (keeping a copy in memory), if it's there. Blocks."""
    key = _key(card_id, size)
    path = os.path.join(image_cache_dir(), f"{key}.jpg")
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return None
    except OSError:
        logging.exception("Failed to read cached image %s", path)
        return None
    _memory.put(key, data)
    return data


def _download(card_id: str, size: str) -> Optional[bytes]:
    """Download the image from the first site that has it, and save it in the background."""
    key = _key(card_id, size)
    not_found = True
    for url in image_urls(card_id, size):
        try:
            data = fetch_bytes(url, timeout=10, max_bytes=MAX_IMAGE_BYTES)
        except Exception as e:
            # Only a 404 says the image isn't there; anything else may work next time
            if getattr(e, "code", None) != 404:
                not_found = False
            logging.warning("Failed to load image for %s from %s: %s", card_id, url, e)
            continue
        _memory.put(key, data)
        _saving[key] = data
        path = os.path.join(image_cache_dir(), f"{key}.jpg")
        threading.Thread(target=_save, args=(key, path, data), daemon=True).start()
        return data
    if not_found:
        _remember(_missing, key, MISSING_FOR_SECONDS)
        return None
    _remember(_unavailable, key, UNAVAILABLE_FOR_SECONDS)
    raise ImageUnavailable(UNAVAILABLE_FOR_SECONDS)


def _save(key: str, path: str, data: bytes):
    """Write a downloaded image to the cache folder (in a background thread)."""
    temp = f"{path}.{threading.get_ident()}.part"
    try:
        with open(temp, "wb") as f:
            f.write(data)
        os.replace(temp, path)
    except OSError:
        logging.exception("Failed to cache image %s", path)
        try:
            os.remove(temp)
        except OSError:
            pass
    finally:
        # Only now: until the file is in place, requests are answered from memory
        _saving.pop(key, None)


def _remember(keys: Dict[str, float], key: str, seconds: float):
    """Note a key in _missing or _unavailable until seconds from now (keeping either bounded)."""
    now = time.monotonic()
    if len(keys) >= MAX_MISSING:
        for old in [old for old, until in keys.items() if until <= now] or list(keys)[:MAX_MISSING // 10]:
            keys.pop(old, None)
    keys[key] = now + seconds
