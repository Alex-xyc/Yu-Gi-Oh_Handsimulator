"""In-memory caches shared by the card sources (filled as cards are looked up)."""

from typing import Dict

# Card ID -> card name
names: Dict[str, str] = {}
# Card ID -> small image URL
image_urls: Dict[str, str] = {}
# Deck IDs that stand in for another card's ID (e.g. a token ID -> the card that makes it)
aliases: Dict[str, str] = {}
