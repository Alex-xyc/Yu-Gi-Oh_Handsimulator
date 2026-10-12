"""Drawing simulated hands."""

import random
from typing import Dict, List, Optional, Tuple

from .categories import CardPool
from .deck import YuGiOhDeck


def draw_from_pool(pool: CardPool, hand_size: int = 5) -> Tuple[List[str], List[str], Optional[str]]:
    """Shuffle the pool and draw a hand.

    Returns (hand card names, hand categories, 6th card name or None). The 6th card is
    simply the next card of the shuffled deck, like a real draw going second.
    """
    pool = list(pool)
    random.shuffle(pool)
    hand = [name for name, _ in pool[:hand_size]]
    categories = [category for _, category in pool[:hand_size]]
    sixth_card = pool[hand_size][0] if len(pool) > hand_size else None
    return hand, categories, sixth_card


def draw_test_hand(deck: YuGiOhDeck, hand_size: int = 5) -> List[str]:
    """Draw a random test hand."""
    full_deck = deck.get_deck_list()
    random.shuffle(full_deck)
    return full_deck[:hand_size]


def analyze_hand(deck: YuGiOhDeck, hand: List[str]) -> Dict:
    """Analyze hand composition."""
    engine_in_hand = [c for c in hand if c in deck.engine_cards]
    non_engine_in_hand = [c for c in hand if c in deck.non_engine_cards]

    return {
        'engine_count': len(engine_in_hand),
        'non_engine_count': len(non_engine_in_hand)
    }


def simulate_6th_card(deck: YuGiOhDeck, hand: List[str]) -> Tuple[str, str]:
    """Simulate drawing a 6th card and return (card_name, category)."""
    full_deck = deck.get_deck_list()

    # Remove exact cards from hand
    temp_deck = full_deck.copy()
    for card in hand:
        if card in temp_deck:
            temp_deck.remove(card)

    if not temp_deck:
        return ("No cards left", "none")

    drawn = random.choice(temp_deck)

    if drawn in deck.engine_cards:
        category = "ENGINE"
    elif drawn in deck.non_engine_cards:
        category = "NON-ENGINE"
    elif drawn in deck.brick_cards:
        category = "BRICK"
    else:
        category = "UNCATEGORIZED"

    return drawn, category
