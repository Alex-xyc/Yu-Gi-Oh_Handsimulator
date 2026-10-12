"""Side-by-side opening-hand odds for two decks (the "Compare Decks" window)."""

from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from .categories import BRICK, ENGINE, NON_ENGINE, CardPool, count_categories
from .probability import category_probability, probability_at_least

# Draw counts are passed to each check as (engine, non-engine, brick)
Drawn = Tuple[int, int, int]


class HandOdds(NamedTuple):
    label: str
    accept: Callable[[Drawn], bool]
    higher_is_better: bool


HAND_ODDS = [
    HandOdds("At least 1 engine", lambda d: d[0] >= 1, True),
    HandOdds("At least 2 engine", lambda d: d[0] >= 2, True),
    HandOdds("At least 1 non-engine", lambda d: d[1] >= 1, True),
    HandOdds("At least 2 non-engine", lambda d: d[1] >= 2, True),
    HandOdds("At least 1 brick", lambda d: d[2] >= 1, False),
    HandOdds("No bricks", lambda d: d[2] == 0, True),
    HandOdds("1+ engine & 1+ non-engine", lambda d: d[0] >= 1 and d[1] >= 1, True),
    HandOdds("1+ engine & no bricks", lambda d: d[0] >= 1 and d[2] == 0, True),
    HandOdds("1+ engine, 1+ NE, no bricks", lambda d: d[0] >= 1 and d[1] >= 1 and d[2] == 0, True),
]

LABEL_W = 30
COL_W = 10


class DeckSummary(NamedTuple):
    """What the comparison needs from one deck."""
    name: str
    pool: CardPool

    @property
    def size(self) -> int:
        return len(self.pool)

    def copies(self) -> Dict[str, int]:
        """Copies per card name, in deck order."""
        result: Dict[str, int] = {}
        for card_name, _ in self.pool:
            result[card_name] = result.get(card_name, 0) + 1
        return result


def hand_odds(deck: DeckSummary, hand_size: int) -> List[float]:
    """Chance of each HAND_ODDS entry, in that order."""
    counts = count_categories(deck.pool)
    category_counts = (counts[ENGINE], counts[NON_ENGINE], counts[BRICK])
    return [category_probability(deck.size, category_counts, hand_size, odds.accept)
            for odds in HAND_ODDS]


def _better(diff: float, higher_is_better: Optional[bool], deck_1: str, deck_2: str) -> str:
    if higher_is_better is None or abs(diff) < 0.05:
        return ""
    return deck_2 if (diff > 0) == higher_is_better else deck_1


def _row(label: str, value_1: str, value_2: str, diff: str = "", better: str = "") -> str:
    return (f"  {label:<{LABEL_W}}{value_1:>{COL_W}}{value_2:>{COL_W}}{diff:>{COL_W}}"
            f"   {better}".rstrip() + "\n")


def _count_row(label: str, count_1: int, count_2: int) -> str:
    diff = count_2 - count_1
    return _row(label, str(count_1), str(count_2), f"{diff:+d}" if diff else "")


def _percent_row(label: str, p_1: float, p_2: float, higher_is_better: Optional[bool],
                 deck_1: str, deck_2: str) -> str:
    diff = (p_2 - p_1) * 100
    return _row(label, f"{p_1 * 100:.1f}%", f"{p_2 * 100:.1f}%",
                f"{diff:+.1f}" if abs(diff) >= 0.05 else "",
                _better(diff, higher_is_better, deck_1, deck_2))


def format_comparison(deck_1: DeckSummary, deck_2: DeckSummary, hand_size: int = 5) -> str:
    """Deck composition, opening-hand odds and per-card odds of two decks side by side.

    Diff is deck 2 minus deck 1 (in percentage points for odds); "Better" names the
    deck with the better value where there is one (fewer bricks is better).
    """
    n1, n2 = deck_1.name, deck_2.name
    counts_1, counts_2 = count_categories(deck_1.pool), count_categories(deck_2.pool)
    width = 2 + LABEL_W + 3 * COL_W + 10
    out: List[str] = []

    turn = "going first" if hand_size == 5 else "going second"
    out.append(f"DECK COMPARISON ({turn}: {hand_size} cards)\n")
    out.append("=" * width + "\n")
    out.append(_row("", n1, n2, "Diff", "Better"))

    # Composition
    out.append("\nComposition:\n")
    out.append(_count_row("Deck size", deck_1.size, deck_2.size))
    for key, label in ((ENGINE, "Engine"), (NON_ENGINE, "Non-Engine"), (BRICK, "Bricks")):
        out.append(_count_row(label, counts_1[key], counts_2[key]))
    untagged_1 = deck_1.size - sum(counts_1.values())
    untagged_2 = deck_2.size - sum(counts_2.values())
    if untagged_1 or untagged_2:
        out.append(_count_row("Untagged", untagged_1, untagged_2))

    # Opening hand odds
    out.append("\n" + "-" * width + "\n")
    out.append("Opening hand:\n")
    for odds, p_1, p_2 in zip(HAND_ODDS, hand_odds(deck_1, hand_size), hand_odds(deck_2, hand_size)):
        out.append(_percent_row(odds.label, p_1, p_2, odds.higher_is_better, n1, n2))

    # Average cards per hand
    out.append("\nAverage per hand:\n")
    for key, label in ((ENGINE, "Engine"), (NON_ENGINE, "Non-Engine"), (BRICK, "Bricks")):
        avg_1 = hand_size * counts_1[key] / deck_1.size if deck_1.size else 0.0
        avg_2 = hand_size * counts_2[key] / deck_2.size if deck_2.size else 0.0
        diff = avg_2 - avg_1
        out.append(_row(label, f"{avg_1:.2f}", f"{avg_2:.2f}",
                        f"{diff:+.2f}" if abs(diff) >= 0.005 else ""))

    out.append(format_card_comparison(deck_1, deck_2, hand_size, width))
    return "".join(out)


def format_card_comparison(deck_1: DeckSummary, deck_2: DeckSummary, hand_size: int,
                           width: int) -> str:
    """Chance of opening at least one copy of each card, changed cards listed first."""
    copies_1, copies_2 = deck_1.copies(), deck_2.copies()
    names = list(copies_1) + [name for name in copies_2 if name not in copies_1]
    changed = [name for name in names if copies_1.get(name, 0) != copies_2.get(name, 0)]
    same = [name for name in names if name not in changed]

    out: List[str] = []
    out.append("\n" + "-" * width + "\n")
    out.append(f"CARD ODDS (at least 1 copy in {hand_size} cards)\n")
    out.append(f"\n  {deck_1.name[:11]:^11}   {deck_2.name[:11]:^11}\n")
    out.append(f"  {'Qty':>3} {'Odds':>7}   {'Qty':>3} {'Odds':>7}   {'Diff':>6}   Card\n")

    def card_row(name: str) -> str:
        q1, q2 = copies_1.get(name, 0), copies_2.get(name, 0)
        p1 = probability_at_least(deck_1.size, q1, hand_size, 1) * 100 if q1 else 0.0
        p2 = probability_at_least(deck_2.size, q2, hand_size, 1) * 100 if q2 else 0.0
        odds_1 = f"{p1:6.1f}%" if q1 else "      -"
        odds_2 = f"{p2:6.1f}%" if q2 else "      -"
        diff = p2 - p1
        diff_text = f"{diff:+.1f}" if abs(diff) >= 0.05 else ""
        return f"  {q1:>2}x {odds_1}   {q2:>2}x {odds_2}   {diff_text:>6}   {name}\n"

    if changed:
        out.append("\n  Different between the decks:\n")
        out.extend(card_row(name) for name in changed)
    if same:
        out.append("\n  Same copies in both:\n")
        out.extend(card_row(name) for name in same)
    return "".join(out)
