import os
import sys
import unittest
from unittest.mock import patch

# ensure src is importable
ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_PATH = os.path.join(ROOT, 'src')
if SRC_PATH not in sys.path:
    sys.path.insert(0, SRC_PATH)

import main
import gui

class TestGUISmoke(unittest.TestCase):
    def setUp(self):
        # Patch messagebox so tests don't show modal dialogs
        self.msg_patcher = patch('tkinter.messagebox.showwarning')
        self.mock_msg = self.msg_patcher.start()

    def tearDown(self):
        self.msg_patcher.stop()

    def test_instantiate_and_draw_hand(self):
        # Create app but do not run mainloop; perform programmatic calls
        app = gui.YuGiOhHandSimulator()
        try:
            # Build a larger deck programmatically (avoid zero remaining_deck)
            deck = main.YuGiOhDeck()
            # Add a few engines/non-engines and fill the rest with bricks to reach 40
            deck.add_card('CardA', 3)
            deck.add_card('CardB', 2)
            # fill to 40 total cards with unique bricks
            total = deck.get_deck_size()
            i = 0
            while total < 40:
                name = f'Brick{i}'
                deck.add_card(name, 1)
                total += 1
                i += 1
            # assign categories
            deck.engine_cards.update({'CardA'})
            deck.non_engine_cards.update({'CardB'})
            deck.brick_cards.update({f'Brick{j}' for j in range(i)})
            app.deck = deck
            app.deck_loaded = True
            # call draw_hand and ensure no exceptions and reasonable results
            app.draw_hand()
            self.assertTrue(len(app.current_hand) <= 5)
            # Ensure stats textbox was populated
            content = app.stats_textbox.get('1.0', 'end').strip()
            self.assertIn('OPENING HAND PROBABILITIES', content)
        finally:
            # Clean up Tk root created by CTk
            try:
                app.destroy()
            except Exception:
                pass

if __name__ == '__main__':
    unittest.main()
