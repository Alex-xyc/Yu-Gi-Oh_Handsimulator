"""YGOPRODeck API: the primary source for card names and images."""

import html
import logging
from typing import Dict, List

from . import cache
from .edopro import fetch_edopro_card_names
from .http import fetch_json

CARDINFO_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php?id={ids}"
# A spell or trap card's "race" -> its subtype
SUBTYPES = {"Normal": "normal", "Quick-Play": "quick_play", "Continuous": "continuous", "Field": "field",
            "Equip": "equip", "Ritual": "ritual", "Counter": "counter"}


def card_info(card: dict) -> dict:
    """A YGOPRODeck card entry's kind (monster, spell_<subtype>, trap_<subtype>) and level."""
    frame = card.get('frameType', '')
    if frame in ('spell', 'trap'):
        return {"kind": f"{frame}_{SUBTYPES.get(card.get('race', ''), 'normal')}", "level": 0}
    if 'Monster' in card.get('type', ''):
        return {"kind": "monster", "level": int(card.get('level') or 0)}
    return {"kind": "", "level": 0}


def _remember_card(card: dict) -> str:
    """Cache a YGOPRODeck card entry's name, kind and small image; returns the name."""
    card_id = str(card['id'])
    card_name = html.unescape(card['name'])
    cache.names[card_id] = card_name
    cache.info[card_id] = card_info(card)
    if 'card_images' in card and len(card['card_images']) > 0:
        cache.image_urls[card_id] = card['card_images'][0].get('image_url_small', '')
    return card_name


def fetch_card_name(card_id: str) -> str:
    """Fetch card name from YGOPRODeck API, falling back to EDOPro."""
    if card_id in cache.names:
        return cache.names[card_id]

    try:
        data = fetch_json(CARDINFO_URL.format(ids=card_id), timeout=10)
        if 'data' in data and len(data['data']) > 0:
            return _remember_card(data['data'][0])
    except Exception:
        logging.exception("Failed to fetch card name for id %s", card_id)

    edopro = fetch_edopro_card_names([card_id])
    if card_id in edopro:
        return edopro[card_id]

    return f"Unknown_{card_id}"


def fetch_multiple_card_names(card_ids: List[str], verbose: bool = True) -> Dict[str, str]:
    """Fetch multiple card names from API."""
    result = {}

    uncached_ids = [cid for cid in card_ids if cid not in cache.names]

    for cid in card_ids:
        if cid in cache.names:
            result[cid] = cache.names[cid]

    if not uncached_ids:
        if verbose:
            print("All cards found in cache.")
        return result

    if verbose:
        print(f"Fetching {len(uncached_ids)} card names from API...")

    try:
        data = fetch_json(CARDINFO_URL.format(ids=",".join(uncached_ids)), timeout=20)
        if 'data' in data:
            for card in data['data']:
                result[str(card['id'])] = _remember_card(card)
            if verbose:
                print(f"  Loaded {len(data['data'])} cards.")
    except Exception:
        logging.exception("Failed to fetch multiple card names from API")

    # Fall back to EDOPro for anything YGOPRODeck didn't return
    missing = [cid for cid in uncached_ids if cid not in result]
    if missing:
        if verbose:
            print(f"Looking up {len(missing)} card(s) in EDOPro database...")
        result.update(fetch_edopro_card_names(missing))

        # IDs EDOPro resolved to another card: use that card's YGOPRODeck name and image
        aliased = {cid: cache.aliases[cid] for cid in missing if cid in cache.aliases}
        if aliased:
            real = fetch_multiple_card_names(list(set(aliased.values())), verbose=verbose)
            for cid, real_id in aliased.items():
                if real_id in real:
                    result[cid] = cache.names[cid] = real[real_id]
                if real_id in cache.info:
                    cache.info[cid] = cache.info[real_id]
                if cache.image_urls.get(real_id):
                    cache.image_urls[cid] = cache.image_urls[real_id]

    return result


def fetch_card_infos(card_ids: List[str]) -> Dict[str, dict]:
    """Each card's kind and level (see card_info), looking up the ones not cached yet.

    Unknown cards get kind "".
    """
    missing = [cid for cid in card_ids if cid not in cache.info and cid.isdigit()]
    if missing:
        try:
            data = fetch_json(CARDINFO_URL.format(ids=",".join(missing)), timeout=20)
            for card in data.get('data', []):
                _remember_card(card)
        except Exception:
            logging.exception("Failed to fetch card info from API")
        # EDOPro for anything YGOPRODeck didn't return (it caches the kind as it goes)
        still_missing = [cid for cid in missing if cid not in cache.info]
        if still_missing:
            fetch_edopro_card_names(still_missing)
    return {cid: cache.info.get(cid, {"kind": "", "level": 0}) for cid in card_ids}
