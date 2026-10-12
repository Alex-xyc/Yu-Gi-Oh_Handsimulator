"""Which image URLs to use for a card."""

from typing import Dict, List

from . import cache
from .edopro import EDOPRO_IMAGE_URL


def get_card_image_url(card_id: str) -> str:
    """Get cached image URL for a card ID."""
    return cache.image_urls.get(card_id, '')


def get_card_image_urls(card_id: str) -> List[str]:
    """Image URLs to try for a card, in order: YGOPRODeck, then EDOPro."""
    urls = []
    cached = cache.image_urls.get(card_id, '')
    if cached:
        urls.append(cached)
    card_id = cache.aliases.get(card_id, card_id)
    if card_id.isdigit():
        edopro = EDOPRO_IMAGE_URL.format(card_id=card_id)
        if edopro not in urls:
            urls.append(edopro)
    return urls


def get_image_cache() -> Dict[str, str]:
    """Get the entire image cache."""
    return cache.image_urls
