"""Turning a list of card IDs (plus their looked-up names) into a deck."""

from typing import Dict, List, Tuple

from .deck import YuGiOhDeck


class TooManyCopiesError(ValueError):
    """A card appears more times than the deck allows."""

    def __init__(self, card_name: str, copies: int, max_copies: int):
        self.card_name = card_name
        self.copies = copies
        super().__init__(f"'{card_name}' has {copies} copies. Max is {max_copies}.")


def count_cards(card_ids: List[str], names: Dict[str, str]) -> Tuple[Dict[str, int], Dict[str, str]]:
    """Copies per card name, plus a name -> card ID map (for image lookups).

    IDs without a known name are named "Card_<id>".
    """
    card_counts: Dict[str, int] = {}
    card_id_map: Dict[str, str] = {}
    for card_id in card_ids:
        card_name = names.get(card_id, f"Card_{card_id}")
        card_counts[card_name] = card_counts.get(card_name, 0) + 1
        card_id_map[card_name] = card_id
    return card_counts, card_id_map


def fill_deck(deck: YuGiOhDeck, card_counts: Dict[str, int]) -> None:
    """Add every card to the deck; on too many copies, clear the deck and raise."""
    for card_name, copies in card_counts.items():
        if copies > deck.MAX_COPIES:
            deck.clear_deck()
            raise TooManyCopiesError(card_name, copies, deck.MAX_COPIES)
        deck.add_card(card_name, copies)
