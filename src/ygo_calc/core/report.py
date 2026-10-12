"""The "Probabilities & Statistics" text shown next to the test hand."""

from typing import Dict, List

from .categories import BRICK, ENGINE, NON_ENGINE, UNTAGGED, CardPool
from .probability import (engine_non_engine_probability, hypergeometric_probability,
                          probability_at_least)


def format_statistics_report(deck_size: int, counts: Dict[str, int],
                             hand_categories: List[str], hand_size: int = 5) -> str:
    """Opening-hand odds, brick analysis and 6th-card odds for the current hand.

    counts: copies per category (see categories.count_categories).
    hand_categories: the category of each card in the drawn hand.
    """
    engine_count = counts[ENGINE]
    non_engine_count = counts[NON_ENGINE]
    brick_count = counts[BRICK]
    out: List[str] = []

    # Header
    out.append("OPENING HAND PROBABILITIES\n")
    out.append("=" * 50 + "\n\n")

    # Deck composition
    out.append(f"Deck: {deck_size} cards\n")
    out.append(f"  Engine: {engine_count} | Non-Engine: {non_engine_count} | Bricks: {brick_count}\n\n")

    # Engine x Non-Engine Matrix
    out.append("Engine x Non-Engine Matrix:\n")
    out.append("(E = Engine, NE = Non-Engine/Handtraps)\n\n")

    out.append("       ")
    for ne in range(6):
        out.append(f" {ne}NE   ")
    out.append("\n")

    for eng in range(6):
        out.append(f"  {eng}E  ")
        for ne in range(6):
            prob = None
            if eng + ne <= 5:
                prob = engine_non_engine_probability(deck_size, engine_count, non_engine_count,
                                                     eng, ne, hand_size)
            if prob is not None and prob * 100 > 0:
                out.append(f"{prob * 100:5.1f}% ")
            else:
                out.append("   -  ")
        out.append("\n")

    # At Least Probabilities
    out.append("\n" + "-" * 50 + "\n")
    out.append("'At Least' Probabilities:\n")
    out.append("(Chance of drawing X OR MORE)\n\n")

    for i in [1, 2]:
        eng_prob = probability_at_least(deck_size, engine_count, hand_size, i) * 100
        out.append(f"  At least {i} engine:      {eng_prob:5.1f}%\n")
    for i in [1, 2]:
        ne_prob = probability_at_least(deck_size, non_engine_count, hand_size, i) * 100
        out.append(f"  At least {i} non-engine:  {ne_prob:5.1f}%\n")
    for i in [1, 2]:
        br_prob = probability_at_least(deck_size, brick_count, hand_size, i) * 100
        out.append(f"  At least {i} brick:       {br_prob:5.1f}%\n")

    # Brick Analysis
    out.append("\n" + "-" * 50 + "\n")
    out.append("BRICK ANALYSIS\n\n")

    open_brick = probability_at_least(deck_size, brick_count, hand_size, 1) * 100
    no_brick_open = hypergeometric_probability(deck_size, brick_count, hand_size, 0)
    draw_brick_6th = (brick_count / (deck_size - 5)) * 100 if deck_size > 5 else 0
    brick_by_turn1 = open_brick + (no_brick_open * brick_count / (deck_size - 5) * 100) if deck_size > 5 else open_brick

    out.append(f"  Open with brick (5 cards):     {open_brick:5.1f}%\n")
    out.append(f"  Draw brick 6th (if none open): {draw_brick_6th:5.1f}%\n")
    out.append(f"  See brick by turn 1 (6 cards): {brick_by_turn1:5.1f}%\n")

    # 6th Card Odds
    out.append("\n" + "-" * 50 + "\n")
    out.append("6TH CARD ODDS (based on current hand)\n\n")

    remaining_deck = deck_size - 5
    engine_remaining = engine_count - hand_categories.count(ENGINE)
    non_engine_remaining = non_engine_count - hand_categories.count(NON_ENGINE)
    brick_remaining = brick_count - hand_categories.count(BRICK)

    out.append(f"  Engine:      {engine_remaining/remaining_deck*100:5.1f}% ({engine_remaining}/{remaining_deck})\n")
    out.append(f"  Non-Engine:  {non_engine_remaining/remaining_deck*100:5.1f}% ({non_engine_remaining}/{remaining_deck})\n")
    out.append(f"  Brick:       {brick_remaining/remaining_deck*100:5.1f}% ({brick_remaining}/{remaining_deck})\n")

    return "".join(out)


# Group order and titles for the per-card odds
_CARD_ODDS_GROUPS = [(ENGINE, "Engine"), (NON_ENGINE, "Non-Engine"), (BRICK, "Brick"),
                     ("mixed", "Mixed tags"), (UNTAGGED, "Untagged")]


def format_card_odds(pool: CardPool, deck_size: int, hand_size: int = 5) -> str:
    """Chance of opening with at least one copy of each card, going first (hand_size
    cards) and going second (hand_size + 1), grouped by the card's category.

    A card whose copies have different tags is listed under "Mixed tags".
    """
    copies: Dict[str, int] = {}
    categories: Dict[str, set] = {}
    for card_name, category in pool:
        copies[card_name] = copies.get(card_name, 0) + 1
        categories.setdefault(card_name, set()).add(category)

    groups: Dict[str, List[str]] = {key: [] for key, _ in _CARD_ODDS_GROUPS}
    for card_name in copies:  # deck order
        cats = categories[card_name]
        groups[next(iter(cats)) if len(cats) == 1 else "mixed"].append(card_name)

    out: List[str] = []
    out.append("\n" + "-" * 50 + "\n")
    out.append("CARD ODDS (at least 1 copy)\n\n")
    out.append(f"  Qty  1st ({hand_size})  2nd ({hand_size + 1})  Card\n")
    for key, title in _CARD_ODDS_GROUPS:
        if not groups[key]:
            continue
        out.append(f"\n  {title}:\n")
        for card_name in groups[key]:
            n = copies[card_name]
            first = probability_at_least(deck_size, n, hand_size, 1) * 100
            second = probability_at_least(deck_size, n, hand_size + 1, 1) * 100
            out.append(f"  {n}x   {first:5.1f}%   {second:5.1f}%   {card_name}\n")
    return "".join(out)
