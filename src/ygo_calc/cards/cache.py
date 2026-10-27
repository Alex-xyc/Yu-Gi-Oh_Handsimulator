"""In-memory caches shared by the card sources (filled as cards are looked up)."""

import time
from typing import Dict, List, Union

# Card ID -> card name
names: Dict[str, str] = {}
# Card ID -> small image URL
image_urls: Dict[str, str] = {}
# Deck IDs that stand in for another card's ID (e.g. a token ID -> the card that makes it)
aliases: Dict[str, str] = {}
# Card ID -> {"kind": "monster" / "spell_<subtype>" / "trap_<subtype>", "level": monster level}
info: Dict[str, Dict[str, Union[str, int]]] = {}

# Whether YGOPRODeck's whole card list is loaded (catalog.py): then it has nothing to tell about
# IDs that aren't in it, so they aren't sent to it
full_list = False

# Card IDs no source knew, until when they aren't looked up again (so made-up IDs can't make the
# server ask YGOPRODeck and EDOPro about them over and over)
UNKNOWN_FOR_SECONDS = 30 * 60
MAX_UNKNOWN = 10_000
unknown: Dict[str, float] = {}


def recently_unknown(card_id: str) -> bool:
    return time.monotonic() < unknown.get(card_id, 0)


def remember_unknown(card_ids: List[str]):
    now = time.monotonic()
    if len(unknown) + len(card_ids) > MAX_UNKNOWN:
        for key in [key for key, until in unknown.items() if until <= now] or list(unknown)[:MAX_UNKNOWN // 10]:
            unknown.pop(key, None)
    for card_id in card_ids:
        unknown[card_id] = now + UNKNOWN_FOR_SECONDS
