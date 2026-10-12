"""Tests for the pure core/ui-layout modules split out of the GUI."""
import os
import sys
import unittest
from math import comb

ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

from ygo_calc.core.categories import (BRICK, ENGINE, NON_ENGINE, UNTAGGED, count_categories,
                                      pool_from_category_sets, pool_from_counts, pool_from_tags,
                                      sync_category_sets)
from ygo_calc.core.deck import YuGiOhDeck
from ygo_calc.core.deck_builder import TooManyCopiesError, count_cards, fill_deck
from ygo_calc.core.deck_parser import DeckParseError, extract_main_deck_ids
from ygo_calc.core.report import format_card_odds, format_statistics_report
from ygo_calc.core.simulation import draw_from_pool
from ygo_calc.ui.text_layout import deck_list_lines, fit_font_size, hand_lines


def make_deck():
    deck = YuGiOhDeck()
    deck.add_card('Ash', 3)
    deck.add_card('Veiler', 2)
    deck.add_card('Starter', 1)
    return deck


class TestCategories(unittest.TestCase):
    def test_counts_split_a_cards_copies(self):
        # 2 bricks: the first two Ash copies; the third Ash is non-engine
        pool = pool_from_counts(make_deck(), brick=2, non_engine=2, engine=1)
        self.assertEqual([c for _, c in pool], [BRICK, BRICK, NON_ENGINE, NON_ENGINE, ENGINE, UNTAGGED])
        self.assertEqual(count_categories(pool), {BRICK: 2, NON_ENGINE: 2, ENGINE: 1})

    def test_tags_and_category_sets_round_trip(self):
        deck = make_deck()
        pool = pool_from_tags(deck, [ENGINE] * 3 + [NON_ENGINE] * 2 + [BRICK])
        sync_category_sets(deck, pool)
        self.assertEqual(deck.engine_cards, {'Ash'})
        self.assertEqual(deck.brick_cards, {'Starter'})
        self.assertEqual(pool_from_category_sets(deck), pool)

    def test_draw_from_pool(self):
        pool = pool_from_counts(make_deck(), 1, 1, 1)
        hand, categories, sixth = draw_from_pool(pool)
        self.assertEqual(len(hand), 5)
        self.assertEqual(len(categories), 5)
        self.assertIsNotNone(sixth)
        hand, _, sixth = draw_from_pool(pool[:3])
        self.assertEqual(len(hand), 3)
        self.assertIsNone(sixth)


class TestDeckParsingAndBuilding(unittest.TestCase):
    def test_extract_ids_from_ydk_and_ydke(self):
        self.assertEqual(extract_main_deck_ids("#main\n100\n200\n#extra\n300\n"), ['100', '200'])
        self.assertEqual(extract_main_deck_ids("ydke://AQAAAAIAAAA=!!"), ['1', '2'])

    def test_extract_ids_errors(self):
        with self.assertRaises(DeckParseError):
            extract_main_deck_ids("#main\n#extra\n")
        with self.assertRaisesRegex(DeckParseError, "ydke"):
            extract_main_deck_ids("ydke://!!")

    def test_build_deck(self):
        counts, id_map = count_cards(['1', '1', '2'], {'1': 'Ash'})
        self.assertEqual(counts, {'Ash': 2, 'Card_2': 1})
        self.assertEqual(id_map, {'Ash': '1', 'Card_2': '2'})
        deck = YuGiOhDeck()
        fill_deck(deck, counts)
        self.assertEqual(deck.get_deck_size(), 3)

    def test_too_many_copies_clears_deck(self):
        deck = YuGiOhDeck()
        with self.assertRaisesRegex(TooManyCopiesError, "'Ash' has 4 copies. Max is 3."):
            fill_deck(deck, {'Veiler': 1, 'Ash': 4})
        self.assertEqual(deck.get_deck_size(), 0)


class TestReport(unittest.TestCase):
    def test_report_sections(self):
        report = format_statistics_report(40, {BRICK: 5, NON_ENGINE: 16, ENGINE: 19},
                                          [ENGINE, ENGINE, NON_ENGINE, BRICK, ENGINE])
        self.assertIn("Engine: 19 | Non-Engine: 16 | Bricks: 5", report)
        self.assertIn("At least 1 engine:       96.9%", report)
        self.assertIn("Engine:       45.7% (16/35)", report)
        for section in ("BRICK ANALYSIS", "6TH CARD ODDS", "Engine x Non-Engine Matrix"):
            self.assertIn(section, report)


class TestCardOdds(unittest.TestCase):
    def test_card_odds_values_and_groups(self):
        deck = YuGiOhDeck()
        deck.add_card('Ash', 3)
        deck.add_card('Starter', 1)
        deck.add_card('Split', 2)
        for i in range(34):
            deck.add_card(f'Filler{i}', 1)
        tags = [NON_ENGINE] * 3 + [ENGINE] + [ENGINE, BRICK] + [UNTAGGED] * 34
        text = format_card_odds(pool_from_tags(deck, tags), deck.get_deck_size())
        # 3 copies in 40: 1 - C(37,5)/C(40,5) going first, 1 - C(37,6)/C(40,6) going second
        first = (1 - comb(37, 5) / comb(40, 5)) * 100
        second = (1 - comb(37, 6) / comb(40, 6)) * 100
        self.assertIn(f"3x   {first:5.1f}%   {second:5.1f}%   Ash", text)
        # Grouped by tag, in group order; a card with mixed tags gets its own group
        order = [text.index(t) for t in ("Engine:", "Non-Engine:", "Mixed tags:", "Untagged:")]
        self.assertEqual(order, sorted(order))
        self.assertLess(text.index("Mixed tags:"), text.index("Split"))
        self.assertNotIn("Brick:", text)


class TestTextLayout(unittest.TestCase):
    def test_deck_list_columns(self):
        deck = make_deck()
        one_col = deck_list_lines(deck, line_chars=20)
        three_cols = deck_list_lines(deck, line_chars=200)
        self.assertEqual(one_col[3:6], ['3x Ash', '2x Veiler', '1x Starter'])
        self.assertIn('3x Ash', three_cols[3])
        self.assertIn('1x Starter', three_cols[3])
        self.assertIn("Total: 6 cards", three_cols)

    def test_hand_lines(self):
        self.assertEqual(hand_lines(['A', 'B'], 'C'),
                         ["OPENING HAND:", "  1. A", "  2. B", "", "6TH CARD (Going Second):", "  → C"])
        self.assertEqual(hand_lines(['A'], None), ["OPENING HAND:", "  1. A"])

    def test_fit_font_size(self):
        class FakeFont:
            def __init__(self, size):
                self.size = size

            def measure(self, text):
                return len(text) * self.size

            def metrics(self, _name):
                return self.size * 2

        lines = ["x" * 10] * 3
        # 3 lines at size s need height 6s and width 10s: fits up to s=20 in 200x120
        size, _ = fit_font_size(lambda f: lines, FakeFont, 200, 120, 14, 24)
        self.assertEqual(size, 20)
        # Too small for even the minimum: falls back to the minimum
        size, _ = fit_font_size(lambda f: lines, FakeFont, 50, 50, 14, 24)
        self.assertEqual(size, 14)


if __name__ == '__main__':
    unittest.main()
