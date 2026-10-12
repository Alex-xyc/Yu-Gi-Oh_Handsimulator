"""Tests for the deck comparison odds and report."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from ygo_calc.core.categories import BRICK, ENGINE, NON_ENGINE, UNTAGGED
from ygo_calc.core.comparison import HAND_ODDS, DeckSummary, format_comparison, hand_odds
from ygo_calc.core.probability import (category_probability, engine_non_engine_probability,
                                       probability_at_least)


def make_pool(engine, non_engine, brick, size=40, prefix=""):
    pool = [(f"{prefix}E{i // 3}", ENGINE) for i in range(engine)]
    pool += [(f"{prefix}N{i // 3}", NON_ENGINE) for i in range(non_engine)]
    pool += [(f"{prefix}B{i // 3}", BRICK) for i in range(brick)]
    pool += [(f"{prefix}X{i // 3}", UNTAGGED) for i in range(size - len(pool))]
    return pool


class TestCategoryProbability(unittest.TestCase):
    def test_matches_single_category(self):
        for k in (1, 2, 3):
            self.assertAlmostEqual(
                category_probability(40, (12, 9, 4), 5, lambda d, k=k: d[0] >= k),
                probability_at_least(40, 12, 5, k))

    def test_matches_engine_non_engine_matrix(self):
        self.assertAlmostEqual(
            category_probability(40, (12, 9), 5, lambda d: d == (2, 1)),
            engine_non_engine_probability(40, 12, 9, 2, 1))

    def test_all_outcomes_sum_to_one(self):
        self.assertAlmostEqual(category_probability(40, (12, 9, 4), 6, lambda d: True), 1.0)

    def test_counts_larger_than_deck(self):
        self.assertEqual(category_probability(10, (8, 8), 5, lambda d: True), 0.0)


class TestComparison(unittest.TestCase):
    def test_hand_odds_order_and_values(self):
        odds = hand_odds(DeckSummary("A", make_pool(12, 9, 4)), 5)
        self.assertEqual(len(odds), len(HAND_ODDS))
        self.assertAlmostEqual(odds[0], probability_at_least(40, 12, 5, 1))
        # "At least 1 brick" and "No bricks" are complements
        self.assertAlmostEqual(odds[4] + odds[5], 1.0)

    def test_report_names_better_deck(self):
        deck_1 = DeckSummary("Deck 1", make_pool(12, 9, 4))
        deck_2 = DeckSummary("Deck 2", make_pool(15, 9, 2))
        report = format_comparison(deck_1, deck_2)
        self.assertIn("DECK COMPARISON (going first)", report)
        engine_line = next(line for line in report.splitlines() if "At least 1 engine" in line)
        self.assertTrue(engine_line.rstrip().endswith("Deck 2"))
        brick_line = next(line for line in report.splitlines() if "At least 1 brick" in line)
        self.assertTrue(brick_line.rstrip().endswith("Deck 2"))  # fewer bricks is better

    def test_identical_decks_have_no_diffs(self):
        pool = make_pool(12, 9, 4)
        report = format_comparison(DeckSummary("Deck 1", pool), DeckSummary("Deck 2", pool), 6)
        self.assertIn("DECK COMPARISON (going second)", report)
        self.assertNotIn("Different between the decks", report)
        self.assertNotRegex(report, r"[+-]\d")

    def test_card_section_lists_changed_cards_first(self):
        pool_1 = make_pool(12, 9, 4)
        pool_2 = pool_1[:-1] + [("New Card", ENGINE)]
        report = format_comparison(DeckSummary("Deck 1", pool_1), DeckSummary("Deck 2", pool_2))
        changed = report.split("Different between the decks:")[1].split("Same copies in both:")[0]
        self.assertIn("New Card", changed)
        self.assertIn("X4", changed)  # lost a copy


if __name__ == '__main__':
    unittest.main()
