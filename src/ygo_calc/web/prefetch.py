"""Getting card data and images ahead of visitors, so a deck shows its pictures as soon as it's
loaded: a background thread started with the server loads YGOPRODeck's card list (see
cards/catalog.py), then downloads every card's image that isn't in the image cache yet, and
does both again every few hours (only new cards' images are downloaded then). Once the list is
loaded, IDs that aren't in it are never sent to YGOPRODeck, so it's checked for new cards often.

Images are downloaded slowly (YGO_PREFETCH_PER_SECOND, default 2), well inside the per-site
budget in cards/http.py, so visitors' own requests aren't held up; the first pass of the small
images (~15,000 at ~25 KB, about 370 MB) takes about two hours. Settings:

    YGO_PREFETCH=0                  off (e.g. when developing)
    YGO_PREFETCH_SIZES=small,full   which images; full-size ones (~160 KB) add about 2.4 GB
    YGO_PREFETCH_PER_SECOND=2       how fast images are downloaded
"""

import logging
import os
import threading

from ..cards import catalog
from . import images

ENABLED = os.environ.get("YGO_PREFETCH", "1") != "0"
SIZES = [size for size in os.environ.get("YGO_PREFETCH_SIZES", "small").replace(" ", "").split(",")
         if size in images.SIZES]
PER_SECOND = max(0.1, float(os.environ.get("YGO_PREFETCH_PER_SECOND", "2")))
# How often to look for a newer card list, and to try again sooner when there's none at all
CHECK_EVERY_SECONDS = 6 * 60 * 60
RETRY_SECONDS = 10 * 60


def _run(stop: threading.Event):
    while not stop.is_set():
        card_ids = []
        try:
            card_ids = catalog.refresh()
            for size in SIZES:
                count = images.prefetch_images(card_ids, size, PER_SECOND, stop)
                if count:
                    logging.info("Prefetched %d %s card images", count, size)
        except Exception:
            logging.exception("Prefetching cards failed")
        stop.wait(CHECK_EVERY_SECONDS if card_ids else RETRY_SECONDS)


def start() -> threading.Event:
    """Start the background thread; set the returned event to stop it."""
    stop = threading.Event()
    threading.Thread(target=_run, args=(stop,), name="card-prefetch", daemon=True).start()
    return stop
