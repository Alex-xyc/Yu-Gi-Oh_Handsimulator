"""Statistics rendering for the GUI.

Functions operate on the `app` instance and update `app.stats_textbox`.
"""
from main import comb, probability_at_least, hypergeometric_probability


def display_statistics(app):
    deck_size = app.deck.get_deck_size()
    engine_count = sum(app.deck.cards[c] for c in app.deck.engine_cards)
    non_engine_count = sum(app.deck.cards[c] for c in app.deck.non_engine_cards)
    brick_count = sum(app.deck.cards[c] for c in app.deck.brick_cards)
    hand_size = 5

    app.stats_textbox.configure(state="normal")
    app.stats_textbox.delete("1.0", "end")

    # Header
    app.stats_textbox.insert("end", "OPENING HAND PROBABILITIES\n")
    app.stats_textbox.insert("end", "=" * 50 + "\n\n")

    # Deck composition
    app.stats_textbox.insert("end", f"Deck: {deck_size} cards\n")
    app.stats_textbox.insert("end", f"  Engine: {engine_count} | Non-Engine: {non_engine_count} | Bricks: {brick_count}\n\n")

    # Engine x Non-Engine Matrix
    app.stats_textbox.insert("end", "Engine x Non-Engine Matrix:\n")
    app.stats_textbox.insert("end", "(E = Engine, NE = Non-Engine/Handtraps)\n\n")

    # Header row
    app.stats_textbox.insert("end", "       ")
    for ne in range(6):
        app.stats_textbox.insert("end", f" {ne}NE   ")
    app.stats_textbox.insert("end", "\n")

    # Matrix rows
    for eng in range(6):
        app.stats_textbox.insert("end", f"  {eng}E  ")
        for ne in range(6):
            if eng + ne <= 5:
                if eng <= engine_count and ne <= non_engine_count:
                    other_count = deck_size - engine_count - non_engine_count
                    other_in_hand = hand_size - eng - ne
                    if other_in_hand >= 0 and other_in_hand <= other_count:
                        prob = (comb(engine_count, eng) *
                               comb(non_engine_count, ne) *
                               comb(other_count, other_in_hand)) / comb(deck_size, hand_size)
                        prob *= 100
                        if prob > 0:
                            app.stats_textbox.insert("end", f"{prob:5.1f}% ")
                        else:
                            app.stats_textbox.insert("end", "   -  ")
                    else:
                        app.stats_textbox.insert("end", "   -  ")
                else:
                    app.stats_textbox.insert("end", "   -  ")
            else:
                app.stats_textbox.insert("end", "   -  ")
        app.stats_textbox.insert("end", "\n")

    # At Least Probabilities
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "'At Least' Probabilities:\n")
    app.stats_textbox.insert("end", "(Chance of drawing X OR MORE)\n\n")

    for i in [1, 2]:
        eng_prob = probability_at_least(deck_size, engine_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} engine:      {eng_prob:5.1f}%\n")
    for i in [1, 2]:
        ne_prob = probability_at_least(deck_size, non_engine_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} non-engine:  {ne_prob:5.1f}%\n")
    for i in [1, 2]:
        br_prob = probability_at_least(deck_size, brick_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} brick:       {br_prob:5.1f}%\n")

    # Brick Analysis
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "BRICK ANALYSIS\n\n")

    open_brick = probability_at_least(deck_size, brick_count, hand_size, 1) * 100
    no_brick_open = hypergeometric_probability(deck_size, brick_count, hand_size, 0)
    draw_brick_6th = (brick_count / (deck_size - 5)) * 100 if deck_size > 5 else 0
    brick_by_turn1 = open_brick + (no_brick_open * brick_count / (deck_size - 5) * 100) if deck_size > 5 else open_brick

    app.stats_textbox.insert("end", f"  Open with brick (5 cards):     {open_brick:5.1f}%\n")
    app.stats_textbox.insert("end", f"  Draw brick 6th (if none open): {draw_brick_6th:5.1f}%\n")
    app.stats_textbox.insert("end", f"  See brick by turn 1 (6 cards): {brick_by_turn1:5.1f}%\n")

    # 6th Card Odds
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "6TH CARD ODDS (based on current hand)\n\n")

    remaining_deck = deck_size - 5
    engine_in_hand = sum(1 for c in app.current_hand if c in app.deck.engine_cards)
    non_engine_in_hand = sum(1 for c in app.current_hand if c in app.deck.non_engine_cards)
    brick_in_hand = sum(1 for c in app.current_hand if c in app.deck.brick_cards)

    engine_remaining = engine_count - engine_in_hand
    non_engine_remaining = non_engine_count - non_engine_in_hand
    brick_remaining = brick_count - brick_in_hand

    app.stats_textbox.insert("end", f"  Engine:      {engine_remaining/remaining_deck*100:5.1f}% ({engine_remaining}/{remaining_deck})\n")
    app.stats_textbox.insert("end", f"  Non-Engine:  {non_engine_remaining/remaining_deck*100:5.1f}% ({non_engine_remaining}/{remaining_deck})\n")
    app.stats_textbox.insert("end", f"  Brick:       {brick_remaining/remaining_deck*100:5.1f}% ({brick_remaining}/{remaining_deck})\n")

    app.stats_textbox.configure(state="disabled")
"""Statistics rendering for the GUI moved out of `gui.py`.

Functions operate on the `app` instance and update `app.stats_textbox`.
"""
from main import comb, probability_at_least, hypergeometric_probability


def display_statistics(app):
    deck_size = app.deck.get_deck_size()
    engine_count = sum(app.deck.cards[c] for c in app.deck.engine_cards)
    non_engine_count = sum(app.deck.cards[c] for c in app.deck.non_engine_cards)
    brick_count = sum(app.deck.cards[c] for c in app.deck.brick_cards)
    hand_size = 5

    app.stats_textbox.configure(state="normal")
    app.stats_textbox.delete("1.0", "end")

    # Header
    app.stats_textbox.insert("end", "OPENING HAND PROBABILITIES\n")
    app.stats_textbox.insert("end", "=" * 50 + "\n\n")

    # Deck composition
    app.stats_textbox.insert("end", f"Deck: {deck_size} cards\n")
    app.stats_textbox.insert("end", f"  Engine: {engine_count} | Non-Engine: {non_engine_count} | Bricks: {brick_count}\n\n")

    # Engine x Non-Engine Matrix
    app.stats_textbox.insert("end", "Engine x Non-Engine Matrix:\n")
    app.stats_textbox.insert("end", "(E = Engine, NE = Non-Engine/Handtraps)\n\n")

    # Header row
    app.stats_textbox.insert("end", "       ")
    for ne in range(6):
        app.stats_textbox.insert("end", f" {ne}NE   ")
    app.stats_textbox.insert("end", "\n")

    # Matrix rows
    for eng in range(6):
        app.stats_textbox.insert("end", f"  {eng}E  ")
        for ne in range(6):
            if eng + ne <= 5:
                if eng <= engine_count and ne <= non_engine_count:
                    other_count = deck_size - engine_count - non_engine_count
                    other_in_hand = hand_size - eng - ne
                    if other_in_hand >= 0 and other_in_hand <= other_count:
                        prob = (comb(engine_count, eng) *
                               comb(non_engine_count, ne) *
                               comb(other_count, other_in_hand)) / comb(deck_size, hand_size)
                        prob *= 100
                        if prob > 0:
                            app.stats_textbox.insert("end", f"{prob:5.1f}% ")
                        else:
                            app.stats_textbox.insert("end", "   -  ")
                    else:
                        app.stats_textbox.insert("end", "   -  ")
                else:
                    app.stats_textbox.insert("end", "   -  ")
            else:
                app.stats_textbox.insert("end", "   -  ")
        app.stats_textbox.insert("end", "\n")

    # At Least Probabilities
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "'At Least' Probabilities:\n")
    app.stats_textbox.insert("end", "(Chance of drawing X OR MORE)\n\n")

    for i in [1, 2]:
        eng_prob = probability_at_least(deck_size, engine_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} engine:      {eng_prob:5.1f}%\n")
    for i in [1, 2]:
        ne_prob = probability_at_least(deck_size, non_engine_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} non-engine:  {ne_prob:5.1f}%\n")
    for i in [1, 2]:
        br_prob = probability_at_least(deck_size, brick_count, hand_size, i) * 100
        app.stats_textbox.insert("end", f"  At least {i} brick:       {br_prob:5.1f}%\n")

    # Brick Analysis
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "BRICK ANALYSIS\n\n")

    open_brick = probability_at_least(deck_size, brick_count, hand_size, 1) * 100
    no_brick_open = hypergeometric_probability(deck_size, brick_count, hand_size, 0)
    draw_brick_6th = (brick_count / (deck_size - 5)) * 100 if deck_size > 5 else 0
    brick_by_turn1 = open_brick + (no_brick_open * brick_count / (deck_size - 5) * 100) if deck_size > 5 else open_brick

    app.stats_textbox.insert("end", f"  Open with brick (5 cards):     {open_brick:5.1f}%\n")
    app.stats_textbox.insert("end", f"  Draw brick 6th (if none open): {draw_brick_6th:5.1f}%\n")
    app.stats_textbox.insert("end", f"  See brick by turn 1 (6 cards): {brick_by_turn1:5.1f}%\n")

    # 6th Card Odds
    app.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
    app.stats_textbox.insert("end", "6TH CARD ODDS (based on current hand)\n\n")

    remaining_deck = deck_size - 5
    engine_in_hand = sum(1 for c in app.current_hand if c in app.deck.engine_cards)
    non_engine_in_hand = sum(1 for c in app.current_hand if c in app.deck.non_engine_cards)
    brick_in_hand = sum(1 for c in app.current_hand if c in app.deck.brick_cards)

    engine_remaining = engine_count - engine_in_hand
    non_engine_remaining = non_engine_count - non_engine_in_hand
    brick_remaining = brick_count - brick_in_hand

    app.stats_textbox.insert("end", f"  Engine:      {engine_remaining/remaining_deck*100:5.1f}% ({engine_remaining}/{remaining_deck})\n")
    app.stats_textbox.insert("end", f"  Non-Engine:  {non_engine_remaining/remaining_deck*100:5.1f}% ({non_engine_remaining}/{remaining_deck})\n")
    app.stats_textbox.insert("end", f"  Brick:       {brick_remaining/remaining_deck*100:5.1f}% ({brick_remaining}/{remaining_deck})\n")

    app.stats_textbox.configure(state="disabled")