"""Text-based (console) version of the hand simulator.

Copyright (c) 2026 Alex-xyc
"""

import os
from typing import Dict, List

from ..cards import fetch_multiple_card_names
from ..core.deck import YuGiOhDeck
from ..core.deck_builder import TooManyCopiesError, count_cards, fill_deck
from ..core.deck_parser import parse_ydk_main_ids, parse_ydke_url
from ..core.probability import calculate_6th_card_odds, calculate_probabilities
from ..core.simulation import draw_test_hand, simulate_6th_card
from ..paths import source_decklists_dir


def load_ydk_code(deck: YuGiOhDeck, ydk_code: str, use_api: bool = True) -> bool:
    """Load deck from YDK code or ydke:// URL."""
    deck.clear_deck()
    ydk_code = ydk_code.strip()

    if ydk_code.startswith("ydke://"):
        print("Detected ydke:// format...")
        try:
            main_ids, _, _ = parse_ydke_url(ydk_code)
            card_ids = main_ids
            if not card_ids:
                print("No main deck cards found.")
                return False
            print(f"Found {len(card_ids)} cards in main deck.")
        except Exception as e:
            print(f"Error: {e}")
            return False
    else:
        card_ids = parse_ydk_main_ids(ydk_code)

        if not card_ids:
            print("No main deck cards found.")
            return False

    if use_api:
        card_database = fetch_multiple_card_names(list(set(card_ids)))
    else:
        card_database = {}

    card_counts, _ = count_cards(card_ids, card_database)
    try:
        fill_deck(deck, card_counts)
    except TooManyCopiesError as e:
        print(f"Error: {e}")
        return False

    print(f"Loaded {deck.get_deck_size()} cards.")

    # Print deck list for verification
    print("\n" + "-" * 50)
    print("DECK LIST")
    print("-" * 50)
    for i, (card_name, copies) in enumerate(deck.cards.items(), 1):
        print(f"  {i:2}. {card_name} x{copies}")
    print("-" * 50)

    return True


def display_results(deck: YuGiOhDeck, hand: List[str], probs: Dict) -> None:
    """Display test hand results."""
    print("\n" + "=" * 60)
    print("TEST HAND RESULTS")
    print("=" * 60)

    print("\nCards Drawn:")
    for i, card in enumerate(hand, 1):
        print(f"  {i}. {card}")

    # 6th Card Analysis (Going Second)
    sixth_odds = calculate_6th_card_odds(deck, hand)
    sixth_card, _ = simulate_6th_card(deck, hand)

    print("\n" + "-" * 60)
    print("6TH CARD (GOING SECOND)")
    print("-" * 60)
    print(f"\nSimulated Draw: {sixth_card}")
    print("\nOdds for 6th card:")
    remaining = sixth_odds['remaining_deck']
    print(f"  Engine:      {sixth_odds['engine_prob']*100:.1f}% ({sixth_odds['engine_remaining']}/{remaining} remaining)")
    print(f"  Non-Engine:  {sixth_odds['non_engine_prob']*100:.1f}% ({sixth_odds['non_engine_remaining']}/{remaining} remaining)")
    print(f"  Brick:       {sixth_odds['brick_prob']*100:.1f}% ({sixth_odds['brick_remaining']}/{remaining} remaining)")

    # Opening Hand Probability Matrix
    print("\n" + "-" * 60)
    print("OPENING HAND PROBABILITIES")
    print("-" * 60)

    print("\nEngine x Non-Engine Matrix (E = Engine, NE = Non-Engine/Handtraps):")
    print("         ", end="")
    for ne in range(6):
        print(f"  {ne}NE   ", end="")
    print()

    for eng in range(6):
        print(f"  {eng}E   ", end="")
        for ne in range(6):
            if eng + ne <= 5:
                prob = probs['combinations'].get((eng, ne), 0) * 100
                if prob > 0:
                    print(f"{prob:6.1f}%  ", end="")
                else:
                    print("    -    ", end="")
            else:
                print("    -    ", end="")
        print()

    print("\n'At Least' Probabilities (chance of drawing X OR MORE of a category):")
    print(f"  At least 1 engine:      {probs['engine_at_least'].get(1, 0)*100:.1f}%")
    print(f"  At least 2 engine:      {probs['engine_at_least'].get(2, 0)*100:.1f}%")
    print(f"  At least 1 non-engine:  {probs['non_engine_at_least'].get(1, 0)*100:.1f}%")
    print(f"  At least 2 non-engine:  {probs['non_engine_at_least'].get(2, 0)*100:.1f}%")
    print(f"  At least 1 brick:       {probs['brick_at_least'].get(1, 0)*100:.1f}%")
    print(f"  At least 2 brick:       {probs['brick_at_least'].get(2, 0)*100:.1f}%")

    print("\nExact Count Probabilities (chance of drawing EXACTLY X of a category):")
    print(f"  Exactly 0 engine:       {probs['engine_probs'].get(0, 0)*100:.1f}%")
    print(f"  Exactly 1 engine:       {probs['engine_probs'].get(1, 0)*100:.1f}%")
    print(f"  Exactly 2 engine:       {probs['engine_probs'].get(2, 0)*100:.1f}%")
    print(f"  Exactly 0 brick:        {probs['brick_probs'].get(0, 0)*100:.1f}%")
    print(f"  Exactly 1 brick:        {probs['brick_probs'].get(1, 0)*100:.1f}%")
    print(f"  Exactly 2 brick:        {probs['brick_probs'].get(2, 0)*100:.1f}%")

    # Brick danger zone
    print("\n" + "-" * 60)
    print("BRICK ANALYSIS")
    print("-" * 60)
    open_brick = probs['brick_at_least'].get(1, 0) * 100
    no_brick_open = probs['brick_probs'].get(0, 0)
    # P(draw brick 6th | no brick in opening) = brick_count / (deck_size - 5)
    brick_total = probs.get('brick_total', 0)
    deck_size = probs.get('deck_size', 40)
    draw_brick_6th_given_no_open = (brick_total / (deck_size - 5)) * 100 if deck_size > 5 else 0
    # P(no brick open AND draw brick 6th)
    no_brick_then_draw = no_brick_open * (brick_total / (deck_size - 5)) * 100 if deck_size > 5 else 0
    # P(brick in opening OR draw brick 6th) = P(open) + P(no open)*P(draw 6th)
    brick_by_turn1 = open_brick + no_brick_then_draw

    print(f"  Open with brick (5 cards):     {open_brick:.1f}%")
    print(f"  Draw brick 6th (if none open): {draw_brick_6th_given_no_open:.1f}%")
    print(f"  See brick by turn 1 (6 cards): {brick_by_turn1:.1f}%")

    print("=" * 60)


def get_ydk_files() -> List[str]:
    """Get list of YDK files from decklists folder."""
    decklist_path = source_decklists_dir()

    if not os.path.exists(decklist_path):
        os.makedirs(decklist_path, exist_ok=True)

    ydk_files = [f for f in os.listdir(decklist_path) if f.endswith('.ydk')]
    return ydk_files


def load_ydk_file(filename: str) -> str:
    """Load YDK file content from decklists folder."""
    decklist_path = source_decklists_dir()
    filepath = os.path.join(decklist_path, filename)

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()


def run_simulator():
    """Main simulator loop."""
    print("\n" + "=" * 50)
    print("YU-GI-OH TEST HAND SIMULATOR")
    print("=" * 50)
    print("Type 'quit' at any time to exit.")

    while True:
        print("\n" + "-" * 50)
        print("MAIN MENU")
        print("-" * 50)
        print("  1. Enter YDK code")
        print("  2. Select from decklists folder")

        choice = input("\nEnter 1 or 2: ").strip()

        if choice.lower() == 'quit':
            print("\nGoodbye!")
            return

        if choice == '1':
            ydk_code = input("\nPaste ydke:// code: ").strip()

            if ydk_code.lower() == 'quit':
                print("\nGoodbye!")
                return

            if not ydk_code:
                print("No code entered.")
                continue

        elif choice == '2':
            ydk_files = get_ydk_files()

            if not ydk_files:
                print("\nNo YDK files found in src/decklists folder.")
                continue

            print("\n" + "-" * 50)
            print("SELECT DECK")
            print("-" * 50)
            for i, filename in enumerate(ydk_files, 1):
                print(f"  {i}. {filename}")

            file_choice = input(f"\nEnter number (1-{len(ydk_files)}): ").strip()

            if file_choice.lower() == 'quit':
                print("\nGoodbye!")
                return

            try:
                file_idx = int(file_choice) - 1
                if 0 <= file_idx < len(ydk_files):
                    ydk_code = load_ydk_file(ydk_files[file_idx])
                    print(f"\nLoaded: {ydk_files[file_idx]}")
                else:
                    print("Invalid selection.")
                    continue
            except ValueError:
                print("Invalid selection.")
                continue
        else:
            print("Invalid choice. Please enter 1 or 2.")
            continue

        # Load deck
        deck = YuGiOhDeck()
        if not load_ydk_code(deck, ydk_code, use_api=True):
            print("Failed to load deck.")
            continue

        deck_size = deck.get_deck_size()

        # Get card counts
        print("\n" + "-" * 50)
        print("SPECIFY CARD COUNTS")
        print("-" * 50)
        print("  Bricks = cards you don't want to draw")
        print("  Non-Engine = handtraps & board breakers")
        print("  Engine = combo pieces (starters + extenders)")

        while True:
            brick_input = input(f"\nBrick cards (0-{deck_size}): ").strip()
            if brick_input.lower() == 'quit':
                print("\nGoodbye!")
                return
            try:
                brick_count = int(brick_input)
                if 0 <= brick_count <= deck_size:
                    break
                print(f"Enter a number between 0 and {deck_size}.")
            except ValueError:
                print("Enter a valid number.")

        while True:
            non_engine_input = input(f"Non-engine cards (0-{deck_size - brick_count}): ").strip()
            if non_engine_input.lower() == 'quit':
                print("\nGoodbye!")
                return
            try:
                non_engine_count = int(non_engine_input)
                if 0 <= non_engine_count <= deck_size - brick_count:
                    break
                print(f"Enter a number between 0 and {deck_size - brick_count}.")
            except ValueError:
                print("Enter a valid number.")

        while True:
            engine_input = input(f"Engine cards (0-{deck_size - brick_count - non_engine_count}): ").strip()
            if engine_input.lower() == 'quit':
                print("\nGoodbye!")
                return
            try:
                engine_count = int(engine_input)
                if 0 <= engine_count <= deck_size - brick_count - non_engine_count:
                    break
                print(f"Enter a number between 0 and {deck_size - brick_count - non_engine_count}.")
            except ValueError:
                print("Enter a valid number.")

        # Assign categories
        card_list = list(deck.cards.keys())
        deck.engine_cards.clear()
        deck.non_engine_cards.clear()
        deck.brick_cards.clear()

        remaining = engine_count
        for card_name in card_list:
            if remaining <= 0:
                break
            copies = deck.cards[card_name]
            if copies <= remaining:
                deck.engine_cards.add(card_name)
            remaining -= copies

        remaining = non_engine_count
        for card_name in card_list:
            if remaining <= 0:
                break
            if card_name in deck.engine_cards:
                continue
            copies = deck.cards[card_name]
            if copies <= remaining:
                deck.non_engine_cards.add(card_name)
            remaining -= copies

        remaining = brick_count
        for card_name in card_list:
            if remaining <= 0:
                break
            if card_name in deck.engine_cards or card_name in deck.non_engine_cards:
                continue
            copies = deck.cards[card_name]
            if copies <= remaining:
                deck.brick_cards.add(card_name)
            remaining -= copies

        print(f"\nDeck configured: {engine_count} engine, {non_engine_count} non-engine, {brick_count} bricks")

        # Draw hands
        print("\n" + "-" * 50)
        print("TEST HANDS")
        print("-" * 50)

        probs = calculate_probabilities(deck)

        while True:
            hand = draw_test_hand(deck)
            display_results(deck, hand, probs)

            draw_again = input("\nDraw again? (y/n): ").strip().lower()
            if draw_again == 'quit':
                print("\nGoodbye!")
                return
            if draw_again != 'y':
                break

        print("\nReturning to menu...")
