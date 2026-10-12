"""Loading a deck code (ydke:// or .ydk text) into a deck, shared by the desktop and web apps."""

from typing import Dict

from .cards import fetch_multiple_card_names
from .core.deck import YuGiOhDeck
from .core.deck_builder import count_cards, fill_deck
from .core.deck_parser import DeckParseError, extract_main_deck_ids


def load_main_deck(deck: YuGiOhDeck, deck_code: str) -> Dict[str, str]:
    """Fill deck with the code's main deck (looking up card names) and return name -> card ID.

    Raises DeckParseError if there are no main deck cards and TooManyCopiesError if a
    card appears too often (the deck is left empty then).
    """
    deck.clear_deck()
    card_ids = extract_main_deck_ids(deck_code)
    # Checked before looking anything up, so a huge code can't trigger huge lookups
    if len(card_ids) > YuGiOhDeck.MAX_DECK_SIZE:
        raise DeckParseError(f"The main deck has {len(card_ids)} cards; at most {YuGiOhDeck.MAX_DECK_SIZE} are allowed.")
    card_database = fetch_multiple_card_names(list(set(card_ids)), verbose=False)
    card_counts, card_id_map = count_cards(card_ids, card_database)
    fill_deck(deck, card_counts)
    return card_id_map
