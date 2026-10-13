"""Hypergeometric probability maths for opening hands.

Everything is counted exactly in whole numbers of hands (Fractions) and only turned into a
float at the end, so results are as accurate as a float can hold, even for tiny chances.
"""

from fractions import Fraction
from itertools import product
from math import comb
from typing import Callable, Dict, List, Optional, Sequence, Tuple

from .deck import YuGiOhDeck


def _hands_with(population: int, successes_in_pop: int, draws: int, target_successes: int) -> int:
    """Number of hands with exactly target_successes of the successes_in_pop cards."""
    if target_successes < 0 or target_successes > successes_in_pop or target_successes > draws:
        return 0
    if draws - target_successes > population - successes_in_pop:
        return 0
    return comb(successes_in_pop, target_successes) * comb(population - successes_in_pop, draws - target_successes)


def exact_probability_at_least(population: int, successes_in_pop: int,
                               draws: int, min_successes: int) -> Fraction:
    """Exact chance of at least min_successes (as a Fraction)."""
    total = comb(population, draws) if 0 <= draws <= population else 0
    if total == 0:
        return Fraction(0)
    ways = sum(_hands_with(population, successes_in_pop, draws, k)
               for k in range(max(min_successes, 0), min(successes_in_pop, draws) + 1))
    return Fraction(ways, total)


def hypergeometric_probability(population: int, successes_in_pop: int,
                                draws: int, target_successes: int) -> float:
    """Calculate hypergeometric probability."""
    total = comb(population, draws) if 0 <= draws <= population else 0
    if total == 0:
        return 0.0
    return float(Fraction(_hands_with(population, successes_in_pop, draws, target_successes), total))


def probability_at_least(population: int, successes_in_pop: int,
                         draws: int, min_successes: int) -> float:
    """Calculate probability of at least N successes."""
    return float(exact_probability_at_least(population, successes_in_pop, draws, min_successes))


def engine_non_engine_probability(deck_size: int, engine_count: int, non_engine_count: int,
                                  engine_drawn: int, non_engine_drawn: int,
                                  hand_size: int = 5) -> Optional[float]:
    """Chance of exactly engine_drawn engine and non_engine_drawn non-engine cards in hand.

    Returns None when that combination is impossible for this deck.
    """
    if engine_drawn <= engine_count and non_engine_drawn <= non_engine_count:
        other_count = deck_size - engine_count - non_engine_count
        other_in_hand = hand_size - engine_drawn - non_engine_drawn
        if 0 <= other_in_hand <= other_count:
            return float(Fraction(comb(engine_count, engine_drawn) *
                                  comb(non_engine_count, non_engine_drawn) *
                                  comb(other_count, other_in_hand), comb(deck_size, hand_size)))
    return None


def category_probability(deck_size: int, counts: Sequence[int], hand_size: int,
                         accept: Callable[[Tuple[int, ...]], bool]) -> float:
    """Chance that the hand's per-category draw counts satisfy accept.

    counts: copies of each category (the rest of the deck counts as "other").
    accept: called with the number drawn from each category, in the order of counts.
    """
    other = deck_size - sum(counts)
    total = comb(deck_size, hand_size)
    if other < 0 or total == 0:
        return 0.0
    ways = 0
    for drawn in product(*(range(min(n, hand_size) + 1) for n in counts)):
        rest = hand_size - sum(drawn)
        if 0 <= rest <= other and accept(drawn):
            combos = comb(other, rest)
            for n, k in zip(counts, drawn):
                combos *= comb(n, k)
            ways += combos
    return float(Fraction(ways, total))


def calculate_probabilities(deck: YuGiOhDeck, hand_size: int = 5) -> Dict:
    """Calculate all probabilities for the deck."""
    deck_size = deck.get_deck_size()
    engine_count = sum(deck.cards[c] for c in deck.engine_cards)
    non_engine_count = sum(deck.cards[c] for c in deck.non_engine_cards)
    brick_count = sum(deck.cards[c] for c in deck.brick_cards)

    probs = {
        'deck_size': deck_size,
        'engine_total': engine_count,
        'non_engine_total': non_engine_count,
        'brick_total': brick_count,
        'engine_probs': {},
        'non_engine_probs': {},
        'brick_probs': {},
        'engine_at_least': {},
        'non_engine_at_least': {},
        'brick_at_least': {},
        'combinations': {}
    }

    for i in range(hand_size + 1):
        probs['engine_probs'][i] = hypergeometric_probability(deck_size, engine_count, hand_size, i)
        probs['non_engine_probs'][i] = hypergeometric_probability(deck_size, non_engine_count, hand_size, i)
        probs['brick_probs'][i] = hypergeometric_probability(deck_size, brick_count, hand_size, i)
        probs['engine_at_least'][i] = probability_at_least(deck_size, engine_count, hand_size, i)
        probs['non_engine_at_least'][i] = probability_at_least(deck_size, non_engine_count, hand_size, i)
        probs['brick_at_least'][i] = probability_at_least(deck_size, brick_count, hand_size, i)

    # Calculate all engine/non-engine combinations
    for eng in range(hand_size + 1):
        for non_eng in range(hand_size + 1 - eng):
            prob = engine_non_engine_probability(deck_size, engine_count, non_engine_count,
                                                 eng, non_eng, hand_size)
            if prob is not None:
                probs['combinations'][(eng, non_eng)] = prob

    return probs


def calculate_6th_card_odds(deck: YuGiOhDeck, hand: List[str]) -> Dict:
    """Calculate odds of drawing engine/non-engine/brick as 6th card."""
    deck_size = deck.get_deck_size()
    remaining_deck = deck_size - 5

    # Count what's left in deck
    engine_in_hand = sum(1 for c in hand if c in deck.engine_cards)
    non_engine_in_hand = sum(1 for c in hand if c in deck.non_engine_cards)
    brick_in_hand = sum(1 for c in hand if c in deck.brick_cards)

    engine_total = sum(deck.cards[c] for c in deck.engine_cards)
    non_engine_total = sum(deck.cards[c] for c in deck.non_engine_cards)
    brick_total = sum(deck.cards[c] for c in deck.brick_cards)

    engine_remaining = engine_total - engine_in_hand
    non_engine_remaining = non_engine_total - non_engine_in_hand
    brick_remaining = brick_total - brick_in_hand

    return {
        'remaining_deck': remaining_deck,
        'engine_remaining': engine_remaining,
        'non_engine_remaining': non_engine_remaining,
        'brick_remaining': brick_remaining,
        'engine_prob': engine_remaining / remaining_deck if remaining_deck > 0 else 0,
        'non_engine_prob': non_engine_remaining / remaining_deck if remaining_deck > 0 else 0,
        'brick_prob': brick_remaining / remaining_deck if remaining_deck > 0 else 0
    }
