import os
import sys
import unittest

# ensure src is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import main

class TestCornerCases(unittest.TestCase):
    def test_parse_ydke_invalid_prefix(self):
        with self.assertRaises(ValueError):
            main.parse_ydke_url('not-a-ydke')

    def test_simulate_6th_card_no_cards_left(self):
        deck = main.YuGiOhDeck()
        # add 5 cards and mark all as engine for variety
        deck.add_card('A', 2)
        deck.add_card('B', 3)
        # create hand equal to full deck
        full_deck = deck.get_deck_list()
        hand = full_deck.copy()
        drawn, category = main.simulate_6th_card(deck, hand)
        self.assertEqual(drawn, 'No cards left')
        self.assertEqual(category, 'none')

    def test_draw_test_hand_small_deck(self):
        deck = main.YuGiOhDeck()
        deck.add_card('X', 1)
        deck.add_card('Y', 2)
        hand = main.draw_test_hand(deck, hand_size=5)
        # should return available cards (3)
        self.assertEqual(len(hand), 3)

    def test_calculate_probabilities_sum(self):
        deck = main.YuGiOhDeck()
        # create a 40-card deck with 3 engines, 2 non-engine, 35 bricks
        deck.add_card('E1', 1)
        deck.add_card('E2', 1)
        deck.add_card('E3', 1)
        deck.add_card('N1', 1)
        deck.add_card('N2', 1)
        # fill bricks
        for i in range(35):
            deck.add_card(f'B{i}', 1)
        # mark categories
        deck.engine_cards.update({'E1', 'E2', 'E3'})
        deck.non_engine_cards.update({'N1', 'N2'})
        deck.brick_cards.update({f'B{i}' for i in range(35)})

        probs = main.calculate_probabilities(deck, hand_size=5)
        # engine_probs keys 0..5 should sum to ~1
        s = sum(probs['engine_probs'].values())
        self.assertAlmostEqual(s, 1.0, places=8)

    def test_hypergeometric_edge_cases(self):
        # target > successes -> 0
        self.assertEqual(main.hypergeometric_probability(40, 2, 5, 3), 0.0)
        # negative target -> 0
        self.assertEqual(main.hypergeometric_probability(40, 2, 5, -1), 0.0)

    def test_load_ydk_no_main(self):
        deck = main.YuGiOhDeck()
        ok = main.load_ydk_code(deck, "", use_api=False)
        self.assertFalse(ok)

    def test_get_deck_list_repeats(self):
        deck = main.YuGiOhDeck()
        deck.add_card('Z', 3)
        lst = deck.get_deck_list()
        self.assertEqual(lst.count('Z'), 3)

if __name__ == '__main__':
    unittest.main()
