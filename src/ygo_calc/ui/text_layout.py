"""Laying out the text under the test hand (pure functions, no Tk widgets)."""

import math
from typing import Callable, List, Sequence, Tuple

from ..core.deck import YuGiOhDeck


def deck_list_lines(deck: YuGiOhDeck, line_chars: int) -> List[str]:
    """Deck list laid out in as many columns as fit line_chars characters per line."""
    entries = [f"{copies}x {card_name}" for card_name, copies in deck.cards.items()]
    if not entries:
        return []
    line_chars = max(1, line_chars)

    gap = 4
    col_w = max(len(e) for e in entries) + gap
    columns = max(1, min(len(entries), (line_chars + gap) // col_w))
    rows = math.ceil(len(entries) / columns)
    # Fill column by column so the list reads top-to-bottom like the deck file
    body = []
    for r in range(rows):
        cells = [entries[c * rows + r] for c in range(columns) if c * rows + r < len(entries)]
        body.append("".join(cell.ljust(col_w) for cell in cells[:-1]) + cells[-1])

    rule = "=" * min(line_chars, max(len(line) for line in body))
    return (["DECK LIST", rule, ""] + body
            + ["", rule, f"Total: {deck.get_deck_size()} cards", "",
               "Set card counts and click 'Apply & Draw Hand'"])


def hand_lines(hand: Sequence[str], sixth_card) -> List[str]:
    """The drawn hand (and the 6th card going second) as text lines."""
    lines = ["OPENING HAND:"] + [f"  {i}. {card}" for i, card in enumerate(hand, 1)]
    if sixth_card:
        lines += ["", "6TH CARD (Going Second):", f"  → {sixth_card}"]
    return lines


def fit_font_size(lines_for: Callable[[object], List[str]], make_font: Callable[[int], object],
                  avail_w: int, avail_h: int, min_size: int, max_size: int) -> Tuple[int, List[str]]:
    """Largest font size (max_size..min_size) at which every line fits avail_w x avail_h.

    lines_for(font) gives the lines to show at that font (e.g. a deck list re-columned
    for its width); make_font(size) creates a font with .measure() and .metrics().
    Falls back to min_size (the text box then scrolls).
    """
    lines: List[str] = []
    size = min_size
    for size in range(max_size, min_size - 1, -1):
        font = make_font(size)
        lines = lines_for(font)
        fits_h = len(lines) * font.metrics("linespace") <= avail_h
        fits_w = all(font.measure(line) <= avail_w for line in lines)
        if fits_h and fits_w:
            break
    return size, lines
