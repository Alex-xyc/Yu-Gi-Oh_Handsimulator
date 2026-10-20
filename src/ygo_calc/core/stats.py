"""Opening-hand statistics as plain data (for the web app; report.py formats the same as text)."""

from fractions import Fraction
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from .categories import BRICK, CATEGORIES, ENGINE, NON_ENGINE, REQUIREMENT, CardPool, count_categories
from .probability import (category_probability, engine_non_engine_probability,
                          exact_probability_at_least, probability_at_least)

# Draw counts are passed to each check as (engine, non-engine, brick, engine requirement)
Drawn = Tuple[int, int, int, int]


class HandOdds(NamedTuple):
    label: str
    accept: Callable[[Drawn], bool]
    higher_is_better: bool
    # Only shown for decks with engine requirements (the odds would just repeat engine ones)
    requirement: bool = False


# Opening-hand checks shown for one deck (here) and for two side by side (comparison.py)
HAND_ODDS = [
    HandOdds("At least 1 engine", lambda d: d[0] >= 1, True),
    HandOdds("At least 2 engine", lambda d: d[0] >= 2, True),
    HandOdds("At least 1 non-engine", lambda d: d[1] >= 1, True),
    HandOdds("At least 2 non-engine", lambda d: d[1] >= 2, True),
    HandOdds("At least 1 brick", lambda d: d[2] >= 1, False),
    HandOdds("No bricks", lambda d: d[2] == 0, True),
    HandOdds("1+ engine & 1+ non-engine", lambda d: d[0] >= 1 and d[1] >= 1, True),
    HandOdds("1+ engine & no bricks", lambda d: d[0] >= 1 and d[2] == 0, True),
    HandOdds("1+ engine, 1+ NE, no bricks", lambda d: d[0] >= 1 and d[1] >= 1 and d[2] == 0, True),
    HandOdds("At least 1 engine req.", lambda d: d[3] >= 1, True, True),
    HandOdds("At least 2 engine req.", lambda d: d[3] >= 2, True, True),
    # A starter plus the piece its combo needs
    HandOdds("1+ engine & 1+ engine req.", lambda d: d[0] >= 1 and d[3] >= 1, True, True),
    # Able to start a combo: a starter, or two requirements (a two-card combo)
    HandOdds("1+ engine or 2+ engine req.", lambda d: d[0] >= 1 or d[3] >= 2, True, True),
]


def shown_hand_odds(*pools: CardPool) -> List[bool]:
    """Per HAND_ODDS entry, whether it applies to these decks (requirement odds need one with
    engine requirements)."""
    has_requirement = any(category == REQUIREMENT for pool in pools for _, category in pool)
    return [has_requirement or not odds.requirement for odds in HAND_ODDS]


def pool_hand_odds(pool: CardPool, hand_size: int) -> List[float]:
    """Chance of each HAND_ODDS entry, in that order."""
    counts = count_categories(pool)
    category_counts = (counts[ENGINE], counts[NON_ENGINE], counts[BRICK], counts[REQUIREMENT])
    return [category_probability(len(pool), category_counts, hand_size, odds.accept)
            for odds in HAND_ODDS]


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
    # Exact fractions, rounded to float once at the end
    open_brick = exact_probability_at_least(deck_size, brick, hand_size, 1)
    sixth_brick = Fraction(brick, remaining) if remaining > 0 else Fraction(0)
    bricks = {
        "open": float(open_brick),
        "draw_sixth": float(sixth_brick),
        "by_turn_one": float(open_brick + (1 - open_brick) * sixth_brick),
    }

    sixth_card = None
    if hand_categories is not None and remaining > 0:
        sixth_card = {}
        for key in CATEGORIES:
            left = counts[key] - hand_categories.count(key)
            sixth_card[key] = {"remaining": left, "probability": left / remaining}
        sixth_card["deck_remaining"] = remaining

    # The combinations not already covered by at_least
    combinations = [{"label": odds.label, "probability": p}
                    for odds, p, shown in zip(HAND_ODDS, pool_hand_odds(pool, hand_size), shown_hand_odds(pool))
                    if shown and not odds.label.startswith("At least")]
    averages = {key: hand_size * counts[key] / deck_size if deck_size else 0.0 for key in CATEGORIES}

    return {
        "deck_size": deck_size,
        "hand_size": hand_size,
        "combinations": combinations,
        "averages": averages,
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
