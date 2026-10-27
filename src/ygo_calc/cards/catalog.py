"""YGOPRODeck's whole card list, kept on disk and loaded into the caches up front, so a deck's
cards are known without asking YGOPRODeck about them when it's loaded.

The list is one request (~15,000 card IDs, alternate artworks included). It is saved, cut down
to what the app uses (a few MB), as $YGO_CACHE_DIR/cards.json and
only downloaded again when YGOPRODeck's database version changes (new cards, a new banlist).
"""

import html
import json
import logging
import os
import threading
from typing import Dict, List, Optional

from . import cache
from .http import fetch_json
from .ygoprodeck import card_info

ALL_CARDS_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php?misc=yes"
DB_VERSION_URL = "https://db.ygoprodeck.com/api/v7/checkDBVer.php"
# The full list is tens of MB of JSON; anything far bigger isn't it
MAX_LIST_BYTES = 150 * 1024 * 1024
# Bump when the saved file's layout changes, so an old one is downloaded again
FORMAT = 1


def cache_base_dir() -> str:
    """$YGO_CACHE_DIR, or the user cache folder (as for the image cache)."""
    base = os.environ.get("YGO_CACHE_DIR")
    if not base:
        local = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".cache")
        base = os.path.join(local, "YGO-Calc")
    return base


def _path() -> str:
    return os.path.join(cache_base_dir(), "cards.json")


def _read_saved() -> Optional[dict]:
    try:
        with open(_path(), encoding="utf-8") as f:
            saved = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        logging.exception("Can't read the saved card list; downloading it again")
        return None
    if isinstance(saved, dict) and saved.get("format") == FORMAT and isinstance(saved.get("cards"), dict):
        return saved
    return None


def _remote_version() -> Optional[str]:
    try:
        return str(fetch_json(DB_VERSION_URL, timeout=10)[0]["database_version"])
    except Exception:
        logging.warning("Couldn't check YGOPRODeck's card database version", exc_info=True)
        return None


def _parse(data: dict) -> Dict[str, dict]:
    """Card ID -> name, kind, level, status and small image URL, from the full card list."""
    cards: Dict[str, dict] = {}
    for card in data.get("data", []):
        entry = {"name": html.unescape(card["name"]), **card_info(card)}
        images = card.get("card_images") or []
        # Alternate artworks have their own IDs (deck files use them) and their own picture
        for art in images:
            art_id = str(art.get("id", ""))
            if art_id.isdigit():
                cards.setdefault(art_id, {**entry, "image": art.get("image_url_small", "")})
        cards[str(card["id"])] = {**entry, "image": images[0].get("image_url_small", "") if images else ""}
    return cards


def _download(version: Optional[str]) -> dict:
    cards = _parse(fetch_json(ALL_CARDS_URL, timeout=120, max_bytes=MAX_LIST_BYTES))
    saved = {"format": FORMAT, "version": version, "cards": cards}
    path = _path()
    temp = f"{path}.{threading.get_ident()}.part"
    # Without the file the list is still used, just downloaded again after a restart
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(temp, "w", encoding="utf-8") as f:
            json.dump(saved, f)
        os.replace(temp, path)
    except OSError:
        logging.exception("Failed to save the card list to %s", path)
        try:
            os.remove(temp)
        except OSError:
            pass
    logging.info("Downloaded YGOPRODeck's card list (version %s): %d card IDs", version, len(cards))
    return saved


def _apply(cards: Dict[str, dict]):
    """Put the cards into the shared caches, where the deck lookups find them."""
    cache.names.update({cid: card["name"] for cid, card in cards.items()})
    cache.info.update({cid: {"kind": card["kind"], "level": card["level"], "status": card["status"]}
                       for cid, card in cards.items()})
    cache.image_urls.update({cid: card["image"] for cid, card in cards.items() if card["image"]})
    cache.full_list = True


def refresh() -> List[str]:
    """Load the card list into the caches, downloading it first if there's none yet or YGOPRODeck
    has a newer one. Returns every card ID in it ([] if there's no list). Blocks; safe to call
    from a background thread."""
    saved = _read_saved()
    if saved:
        # Straight away, before asking whether there's a newer one
        _apply(saved["cards"])
    version = _remote_version()
    if saved is None or (version is not None and version != saved.get("version")):
        try:
            saved = _download(version)
            _apply(saved["cards"])
        except Exception:
            logging.exception("Failed to download YGOPRODeck's card list")
    return list(saved["cards"]) if saved else []
