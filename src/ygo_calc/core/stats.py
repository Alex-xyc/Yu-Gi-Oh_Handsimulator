"""Opening-hand statistics as plain data (for the web app; report.py formats the same as text)."""

from typing import Dict, List, Optional

from .categories import BRICK, CATEGORIES, ENGINE, NON_ENGINE, CardPool, count_categories
from .probability import (engine_non_engine_probability, hypergeometric_probability,
                          probability_at_least)


def opening_stats(pool: CardPool, hand_categories: Optional[List[str]] = None,
                  hand_size: int = 5, grouped: bool = True) -> Dict:
    """Odds for a deck given as a card pool (one (name, category) per copy).

    hand_categories: categories of the drawn hand, for the 6th-card odds (None leaves
        them out, e.g. with typed counts, where it's unknown which cards are which).
    grouped: group the per-card odds by category (False with typed counts).
    """
    deck_size = len(pool)
    counts = count_categories(pool)
    engine, non_engine, brick = counts[ENGINE], counts[NON_ENGINE], counts[BRICK]

    # Engine x non-engine matrix: [engine drawn][non-engine drawn], None = impossible
    matrix = [[engine_non_engine_probability(deck_size, engine, non_engine, e, n, hand_size)
               if e + n <= hand_size else None
               for n in range(hand_size + 1)]
              for e in range(hand_size + 1)]

    # Chance of at least 1, 2, ... hand_size cards of each category
    at_least = {key: [probability_at_least(deck_size, counts[key], hand_size, k)
                      for k in range(1, hand_size + 1)]
                for key in CATEGORIES}

    remaining = deck_size - hand_size
    open_brick = probability_at_least(deck_size, brick, hand_size, 1)
    no_brick_open = hypergeometric_probability(deck_size, brick, hand_size, 0)
    sixth_brick = brick / remaining if remaining > 0 else 0.0
    bricks = {
        "open": open_brick,
        "draw_sixth": sixth_brick,
        "by_turn_one": open_brick + no_brick_open * sixth_brick,
    }

    sixth_card = None
    if hand_categories is not None and remaining > 0:
        sixth_card = {}
        for key in CATEGORIES:
            left = counts[key] - hand_categories.count(key)
            sixth_card[key] = {"remaining": left, "probability": left / remaining}
        sixth_card["deck_remaining"] = remaining

    return {
        "deck_size": deck_size,
        "hand_size": hand_size,
        "counts": {**counts, "untagged": deck_size - sum(counts.values())},
        "matrix": matrix,
        "at_least": at_least,
        "bricks": bricks,
        "sixth_card": sixth_card,
        "cards": card_odds(pool, hand_size, grouped),
    }


def card_odds(pool: CardPool, hand_size: int = 5, grouped: bool = True) -> List[Dict]:
    """Chance of opening at least one copy of each card, going first and second.

    group: the card's category, "mixed" when its copies have different tags, or
    "untagged" (every card, when grouped=False).
    """
    deck_size = len(pool)
    copies: Dict[str, int] = {}
    categories: Dict[str, set] = {}
    for card_name, category in pool:
        copies[card_name] = copies.get(card_name, 0) + 1
        categories.setdefault(card_name, set()).add(category)

    result = []
    for card_name, n in copies.items():  # deck order
        cats = categories[card_name]
        if not grouped:
            group = "untagged"
        elif len(cats) > 1:
            group = "mixed"
        else:
            group = next(iter(cats)) or "untagged"
        result.append({
            "name": card_name,
            "copies": n,
            "group": group,
            "first": probability_at_least(deck_size, n, hand_size, 1),
            "second": probability_at_least(deck_size, n, hand_size + 1, 1),
        })
    return result
