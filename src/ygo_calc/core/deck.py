"""The deck model."""

from typing import Dict, List


class YuGiOhDeck:
    """Yu-Gi-Oh deck with simulation capabilities."""

    MIN_DECK_SIZE = 40
    MAX_DECK_SIZE = 60
    MAX_COPIES = 3
    HAND_SIZE = 5

    def __init__(self):
        self.cards: Dict[str, int] = {}
        self.engine_cards: set = set()
        self.non_engine_cards: set = set()
        self.brick_cards: set = set()

    def add_card(self, card_name: str, copies: int) -> None:
        if copies < 1 or copies > self.MAX_COPIES:
            raise ValueError(f"Error: '{card_name}' has {copies} copies. Max is {self.MAX_COPIES}.")
        self.cards[card_name] = copies

    def get_deck_size(self) -> int:
        return sum(self.cards.values())

    def clear_deck(self) -> None:
        self.cards.clear()
        self.engine_cards.clear()
        self.non_engine_cards.clear()
        self.brick_cards.clear()

    def get_deck_list(self) -> List[str]:
        deck = []
        for card_name, copies in self.cards.items():
            deck.extend([card_name] * copies)
        return deck
