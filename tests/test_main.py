import unittest
import os
import sys
from math import comb

# Ensure the src folder is importable during tests
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import main

YuGiOhDeck = main.YuGiOhDeck
load_ydk_code = main.load_ydk_code
hypergeometric_probability = main.hypergeometric_probability
probability_at_least = main.probability_at_least

class TestYuGiOhDeck(unittest.TestCase):
    def test_add_and_get(self):
        deck = YuGiOhDeck()
        deck.add_card("TestCard", 3)
        self.assertEqual(deck.get_deck_size(), 3)
        self.assertEqual(deck.get_deck_list(), ["TestCard"] * 3)

    def test_add_invalid_copies(self):
        deck = YuGiOhDeck()
        with self.assertRaises(ValueError):
            deck.add_card("TooMany", deck.MAX_COPIES + 1)

class TestProbabilities(unittest.TestCase):
    def test_hypergeometric_known(self):
        population = 40
        successes = 3
        draws = 5
        target = 1
        expected = comb(successes, target) * comb(population - successes, draws - target) / comb(population, draws)
        got = hypergeometric_probability(population, successes, draws, target)
        self.assertAlmostEqual(got, expected, places=12)

    def test_probability_at_least(self):
        population = 40
        successes = 4
        draws = 5
        min_successes = 1
        expected = sum(
            comb(successes, k) * comb(population - successes, draws - k) / comb(population, draws)
            for k in range(min_successes, min(successes, draws) + 1)
        )
        got = probability_at_least(population, successes, draws, min_successes)
        self.assertAlmostEqual(got, expected, places=12)

class TestLoadYdk(unittest.TestCase):
    def test_load_ydk_without_api(self):
        deck = YuGiOhDeck()
        # simple ydk text with numeric ids in main deck
        ydk = """
#main
100
100
200
#extra
#side
"""
        ok = load_ydk_code(deck, ydk, use_api=False)
        self.assertTrue(ok)
        self.assertEqual(deck.get_deck_size(), 3)
        # names should be Card_<id> when not using API
        self.assertEqual(deck.cards.get('Card_100'), 2)
        self.assertEqual(deck.cards.get('Card_200'), 1)

if __name__ == '__main__':
    unittest.main()
