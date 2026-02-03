import random
import base64
import struct
import urllib.request
import json
import os
import html
from math import comb
from typing import Dict, List, Tuple


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


# Card name cache
_card_name_cache: Dict[str, str] = {}


def fetch_card_name(card_id: str) -> str:
    """Fetch card name from YGOPRODeck API."""
    global _card_name_cache
    
    if card_id in _card_name_cache:
        return _card_name_cache[card_id]
    
    try:
        url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?id={card_id}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            if 'data' in data and len(data['data']) > 0:
                card_name = html.unescape(data['data'][0]['name'])
                _card_name_cache[card_id] = card_name
                return card_name
    except Exception:
        pass
    
    return f"Unknown_{card_id}"


def fetch_multiple_card_names(card_ids: List[str], verbose: bool = True) -> Dict[str, str]:
    """Fetch multiple card names from API."""
    global _card_name_cache
    result = {}
    
    uncached_ids = [cid for cid in card_ids if cid not in _card_name_cache]
    
    for cid in card_ids:
        if cid in _card_name_cache:
            result[cid] = _card_name_cache[cid]
    
    if not uncached_ids:
        if verbose:
            print("All cards found in cache.")
        return result
    
    if verbose:
        print(f"Fetching {len(uncached_ids)} card names from API...")
    
    try:
        ids_param = ",".join(uncached_ids)
        url = f"https://db.ygoprodeck.com/api/v7/cardinfo.php?id={ids_param}"
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=20) as response:
            data = json.loads(response.read().decode())
            if 'data' in data:
                for card in data['data']:
                    card_id = str(card['id'])
                    card_name = html.unescape(card['name'])
                    _card_name_cache[card_id] = card_name
                    result[card_id] = card_name
                if verbose:
                    print(f"  Loaded {len(data['data'])} cards.")
    except Exception:
        if verbose:
            print("  Batch failed, trying individually...")
        
        import time
        for card_id in uncached_ids:
            if card_id not in result:
                name = fetch_card_name(card_id)
                result[card_id] = name
                _card_name_cache[card_id] = name
                time.sleep(0.1)
    
    return result


def parse_ydke_url(ydke_url: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse ydke:// URL into card ID lists."""
    if not ydke_url.startswith("ydke://"):
        raise ValueError("Invalid ydke:// format")
    
    data = ydke_url[7:]
    parts = data.split("!")
    
    def decode_section(b64_data: str) -> List[str]:
        if not b64_data:
            return []
        try:
            decoded = base64.b64decode(b64_data)
            card_ids = []
            for i in range(0, len(decoded), 4):
                if i + 4 <= len(decoded):
                    card_id = struct.unpack('<I', decoded[i:i+4])[0]
                    card_ids.append(str(card_id))
            return card_ids
        except Exception:
            return []
    
    main_ids = decode_section(parts[0]) if len(parts) >= 1 else []
    extra_ids = decode_section(parts[1]) if len(parts) >= 2 else []
    side_ids = decode_section(parts[2]) if len(parts) >= 3 else []
    
    return main_ids, extra_ids, side_ids


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
        card_ids = []
        in_main_deck = False
        for line in ydk_code.splitlines():
            line = line.strip()
            if not line:
                continue
            if line == "#main":
                in_main_deck = True
                continue
            elif line in ["#extra", "!side", "#side"]:
                in_main_deck = False
                continue
            elif line.startswith("#") or line.startswith("!"):
                continue
            if in_main_deck and line.isdigit():
                card_ids.append(line)
        
        if not card_ids:
            print("No main deck cards found.")
            return False
    
    if use_api:
        card_database = fetch_multiple_card_names(list(set(card_ids)))
    else:
        card_database = {}
    
    card_counts: Dict[str, int] = {}
    for card_id in card_ids:
        card_name = card_database.get(card_id, f"Card_{card_id}")
        card_counts[card_name] = card_counts.get(card_name, 0) + 1
    
    for card_name, copies in card_counts.items():
        if copies > deck.MAX_COPIES:
            print(f"Error: '{card_name}' has {copies} copies. Max is {deck.MAX_COPIES}.")
            deck.clear_deck()
            return False
        deck.add_card(card_name, copies)
    
    print(f"Loaded {deck.get_deck_size()} cards.")
    
    # Print deck list for verification
    print("\n" + "-" * 50)
    print("DECK LIST")
    print("-" * 50)
    for i, (card_name, copies) in enumerate(deck.cards.items(), 1):
        print(f"  {i:2}. {card_name} x{copies}")
    print("-" * 50)
    
    return True


def hypergeometric_probability(population: int, successes_in_pop: int, 
                                draws: int, target_successes: int) -> float:
    """Calculate hypergeometric probability."""
    if target_successes > successes_in_pop or target_successes > draws:
        return 0.0
    if target_successes < 0 or (draws - target_successes) > (population - successes_in_pop):
        return 0.0
    
    numerator = comb(successes_in_pop, target_successes) * comb(population - successes_in_pop, draws - target_successes)
    denominator = comb(population, draws)
    return numerator / denominator if denominator > 0 else 0.0


def probability_at_least(population: int, successes_in_pop: int, 
                         draws: int, min_successes: int) -> float:
    """Calculate probability of at least N successes."""
    prob = 0.0
    for k in range(min_successes, min(successes_in_pop, draws) + 1):
        prob += hypergeometric_probability(population, successes_in_pop, draws, k)
    return prob


def draw_test_hand(deck: YuGiOhDeck, hand_size: int = 5) -> List[str]:
    """Draw a random test hand."""
    full_deck = deck.get_deck_list()
    random.shuffle(full_deck)
    return full_deck[:hand_size]


def analyze_hand(deck: YuGiOhDeck, hand: List[str]) -> Dict:
    """Analyze hand composition."""
    engine_in_hand = [c for c in hand if c in deck.engine_cards]
    non_engine_in_hand = [c for c in hand if c in deck.non_engine_cards]
    
    return {
        'engine_count': len(engine_in_hand),
        'non_engine_count': len(non_engine_in_hand)
    }


def calculate_probabilities(deck: YuGiOhDeck, hand_size: int = 5) -> Dict:
    """Calculate all probabilities for the deck."""
    deck_size = deck.get_deck_size()
    engine_count = sum(deck.cards[c] for c in deck.engine_cards)
    non_engine_count = sum(deck.cards[c] for c in deck.non_engine_cards)
    brick_count = sum(deck.cards[c] for c in deck.brick_cards)
    
    probs = {
        'deck_size': deck_size,
        'engine_total': engine_count,
        'non_engine_total': non_engine_count,
        'brick_total': brick_count,
        'engine_probs': {},
        'non_engine_probs': {},
        'brick_probs': {},
        'engine_at_least': {},
        'non_engine_at_least': {},
        'brick_at_least': {},
        'combinations': {}
    }
    
    for i in range(hand_size + 1):
        probs['engine_probs'][i] = hypergeometric_probability(deck_size, engine_count, hand_size, i)
        probs['non_engine_probs'][i] = hypergeometric_probability(deck_size, non_engine_count, hand_size, i)
        probs['brick_probs'][i] = hypergeometric_probability(deck_size, brick_count, hand_size, i)
        probs['engine_at_least'][i] = probability_at_least(deck_size, engine_count, hand_size, i)
        probs['non_engine_at_least'][i] = probability_at_least(deck_size, non_engine_count, hand_size, i)
        probs['brick_at_least'][i] = probability_at_least(deck_size, brick_count, hand_size, i)
    
    # Calculate all engine/non-engine combinations
    for eng in range(hand_size + 1):
        for non_eng in range(hand_size + 1 - eng):
            if eng <= engine_count and non_eng <= non_engine_count:
                other_count = deck_size - engine_count - non_engine_count
                other_in_hand = hand_size - eng - non_eng
                if other_in_hand >= 0 and other_in_hand <= other_count:
                    prob = (comb(engine_count, eng) * 
                           comb(non_engine_count, non_eng) * 
                           comb(other_count, other_in_hand)) / comb(deck_size, hand_size)
                    probs['combinations'][(eng, non_eng)] = prob
    
    return probs


def calculate_6th_card_odds(deck: YuGiOhDeck, hand: List[str]) -> Dict:
    """Calculate odds of drawing engine/non-engine/brick as 6th card."""
    deck_size = deck.get_deck_size()
    remaining_deck = deck_size - 5
    
    # Count what's left in deck
    engine_in_hand = sum(1 for c in hand if c in deck.engine_cards)
    non_engine_in_hand = sum(1 for c in hand if c in deck.non_engine_cards)
    brick_in_hand = sum(1 for c in hand if c in deck.brick_cards)
    
    engine_total = sum(deck.cards[c] for c in deck.engine_cards)
    non_engine_total = sum(deck.cards[c] for c in deck.non_engine_cards)
    brick_total = sum(deck.cards[c] for c in deck.brick_cards)
    
    engine_remaining = engine_total - engine_in_hand
    non_engine_remaining = non_engine_total - non_engine_in_hand
    brick_remaining = brick_total - brick_in_hand
    
    return {
        'remaining_deck': remaining_deck,
        'engine_remaining': engine_remaining,
        'non_engine_remaining': non_engine_remaining,
        'brick_remaining': brick_remaining,
        'engine_prob': engine_remaining / remaining_deck if remaining_deck > 0 else 0,
        'non_engine_prob': non_engine_remaining / remaining_deck if remaining_deck > 0 else 0,
        'brick_prob': brick_remaining / remaining_deck if remaining_deck > 0 else 0
    }


def simulate_6th_card(deck: YuGiOhDeck, hand: List[str]) -> Tuple[str, str]:
    """Simulate drawing a 6th card and return (card_name, category)."""
    full_deck = deck.get_deck_list()
    
    # Remove exact cards from hand
    temp_deck = full_deck.copy()
    for card in hand:
        if card in temp_deck:
            temp_deck.remove(card)
    
    if not temp_deck:
        return ("No cards left", "none")
    
    drawn = random.choice(temp_deck)
    
    if drawn in deck.engine_cards:
        category = "ENGINE"
    elif drawn in deck.non_engine_cards:
        category = "NON-ENGINE"
    elif drawn in deck.brick_cards:
        category = "BRICK"
    else:
        category = "UNCATEGORIZED"
    
    return drawn, category


def display_results(deck: YuGiOhDeck, hand: List[str], probs: Dict) -> None:
    """Display test hand results."""
    analysis = analyze_hand(deck, hand)
    
    print("\n" + "=" * 60)
    print("TEST HAND RESULTS")
    print("=" * 60)
    
    print("\nCards Drawn:")
    for i, card in enumerate(hand, 1):
        print(f"  {i}. {card}")
    
    # 6th Card Analysis (Going Second)
    sixth_odds = calculate_6th_card_odds(deck, hand)
    sixth_card, sixth_category = simulate_6th_card(deck, hand)
    
    print("\n" + "-" * 60)
    print("6TH CARD (GOING SECOND)")
    print("-" * 60)
    print(f"\nSimulated Draw: {sixth_card}")
    print(f"\nOdds for 6th card:")
    print(f"  Engine:      {sixth_odds['engine_prob']*100:.1f}% ({sixth_odds['engine_remaining']}/{sixth_odds['remaining_deck']} remaining)")
    print(f"  Non-Engine:  {sixth_odds['non_engine_prob']*100:.1f}% ({sixth_odds['non_engine_remaining']}/{sixth_odds['remaining_deck']} remaining)")
    print(f"  Brick:       {sixth_odds['brick_prob']*100:.1f}% ({sixth_odds['brick_remaining']}/{sixth_odds['remaining_deck']} remaining)")
    
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
                    print(f"    -    ", end="")
            else:
                print(f"    -    ", end="")
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
    script_dir = os.path.dirname(os.path.abspath(__file__))
    decklist_path = os.path.join(script_dir, 'decklists')
    
    if not os.path.exists(decklist_path):
        os.makedirs(decklist_path, exist_ok=True)
    
    ydk_files = [f for f in os.listdir(decklist_path) if f.endswith('.ydk')]
    return ydk_files


def load_ydk_file(filename: str) -> str:
    """Load YDK file content from decklists folder."""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    decklist_path = os.path.join(script_dir, 'decklists')
    filepath = os.path.join(decklist_path, filename)
    
    with open(filepath, 'r') as f:
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


if __name__ == "__main__":
    run_simulator()
