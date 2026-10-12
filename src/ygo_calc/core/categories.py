"""Card categories (brick / non-engine / engine), tracked per copy in a "card pool".

A pool is a list of (card_name, category) with one entry per copy in the deck, so a
card's copies can be split across categories (e.g. 2 Ash as non-engine, 1 as a brick).
"""

from typing import Dict, List, Tuple

from .deck import YuGiOhDeck

BRICK = "brick"
NON_ENGINE = "non_engine"
ENGINE = "engine"
UNTAGGED = ""
CATEGORIES = (BRICK, NON_ENGINE, ENGINE)

CardPool = List[Tuple[str, str]]


def pool_from_counts(deck: YuGiOhDeck, brick: int, non_engine: int, engine: int) -> CardPool:
    """Assign categories per copy, in deck-list order, so the counts are met exactly
    even when a card's copies span two categories."""
    categories = [BRICK] * brick + [NON_ENGINE] * non_engine + [ENGINE] * engine
    deck_list = deck.get_deck_list()
    categories += [UNTAGGED] * (len(deck_list) - len(categories))
    return list(zip(deck_list, categories))


def pool_from_tags(deck: YuGiOhDeck, tags: List[str]) -> CardPool:
    """Pool from per-copy tags (aligned with deck.get_deck_list())."""
    return list(zip(deck.get_deck_list(), tags))


def pool_from_category_sets(deck: YuGiOhDeck) -> CardPool:
    """Build a per-copy card pool from the deck's per-name category sets."""
    pool = []
    for card_name, copies in deck.cards.items():
        if card_name in deck.brick_cards:
            category = BRICK
        elif card_name in deck.non_engine_cards:
            category = NON_ENGINE
        elif card_name in deck.engine_cards:
            category = ENGINE
        else:
            category = UNTAGGED
        pool.extend([(card_name, category)] * copies)
    return pool


def sync_category_sets(deck: YuGiOhDeck, pool: CardPool) -> None:
    """Mirror the per-copy card pool into the deck's per-name category sets."""
    deck.engine_cards.clear()
    deck.non_engine_cards.clear()
    deck.brick_cards.clear()
    category_sets = {BRICK: deck.brick_cards, NON_ENGINE: deck.non_engine_cards,
                     ENGINE: deck.engine_cards}
    for card_name, category in pool:
        if category:
            category_sets[category].add(card_name)


def count_categories(pool: CardPool) -> Dict[str, int]:
    """Number of copies in each category."""
    return {key: sum(1 for _, category in pool if category == key) for key in CATEGORIES}
