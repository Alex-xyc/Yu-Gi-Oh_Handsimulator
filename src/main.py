"""Start the console (text) version of YGO Calc.

The code lives in the ygo_calc package. The names below are re-exported so existing
`import main` code keeps working.

Copyright (c) 2026 Alex-xyc
"""

from ygo_calc.cards import (fetch_card_name, fetch_edopro_card_names, fetch_multiple_card_names,
                            get_card_image_url, get_card_image_urls, get_image_cache)
from ygo_calc.cli.console import (display_results, get_ydk_files, load_ydk_code, load_ydk_file,
                                  run_simulator)
from ygo_calc.core.deck import YuGiOhDeck
from ygo_calc.core.deck_parser import parse_ydke_url
from ygo_calc.core.probability import (calculate_6th_card_odds, calculate_probabilities,
                                       hypergeometric_probability, probability_at_least)
from ygo_calc.core.simulation import analyze_hand, draw_test_hand, simulate_6th_card

__all__ = [
    "YuGiOhDeck", "parse_ydke_url", "load_ydk_code",
    "fetch_card_name", "fetch_multiple_card_names", "fetch_edopro_card_names",
    "get_card_image_url", "get_card_image_urls", "get_image_cache",
    "hypergeometric_probability", "probability_at_least", "calculate_probabilities",
    "calculate_6th_card_odds", "draw_test_hand", "analyze_hand", "simulate_6th_card",
    "display_results", "get_ydk_files", "load_ydk_file", "run_simulator",
]

if __name__ == "__main__":
    run_simulator()
