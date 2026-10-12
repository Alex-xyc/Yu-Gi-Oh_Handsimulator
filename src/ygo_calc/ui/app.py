"""The main window: builds the panels and connects them to the deck state.

Panels (each in its own module):
    DeckInputPanel  ydke:// code / .ydk file loading          (deck_input_panel.py)
    CountsPanel     category counts, buttons, deck status       (counts_panel.py)
    SplitView       resizable split holding the two panels:     (split_view.py)
        HandPanel   the drawn hand and its text                 (hand_panel.py)
        StatsPanel  probabilities & statistics                  (stats_panel.py)
    AdvancedDeckView  "Show Decklist" overlay for tagging cards (advanced_view.py)

Copyright (c) 2026 Alex-xyc
"""

from tkinter import messagebox
from typing import Dict, List, Optional

import customtkinter as ctk

from ..cards import fetch_multiple_card_names, get_card_image_urls
from ..core.categories import (BRICK, ENGINE, NON_ENGINE, CardPool, count_categories, pool_from_category_sets, pool_from_counts,
                               pool_from_tags, sync_category_sets)
from ..core.deck import YuGiOhDeck
from ..core.deck_builder import TooManyCopiesError, count_cards, fill_deck
from ..core.deck_parser import DeckParseError, extract_main_deck_ids
from ..core.report import format_card_odds, format_statistics_report
from ..core.simulation import draw_from_pool
from . import theme
from .advanced_view import AdvancedDeckView
from .counts_panel import CountsPanel
from .deck_input_panel import DeckInputPanel
from .hand_panel import HandPanel
from .image_loader import ImageLoader
from .split_view import SplitView
from .stats_panel import StatsPanel
from .window import apply_window_icon, maximize, set_app_user_model_id, set_default_geometry


class YuGiOhHandSimulator(ctk.CTk):
    """Yu-Gi-Oh Hand Simulator GUI Application"""

    # Size that shows the full hand and all statistics without scrolling (logical px)
    DEFAULT_SIZE = (1400, 1090)
    MIN_SIZE = (1100, 800)

    def __init__(self):
        set_app_user_model_id()
        super().__init__()

        self.title(theme.APP_TITLE)
        set_default_geometry(self, self.DEFAULT_SIZE, self.MIN_SIZE, self._maximize)
        apply_window_icon(self)

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Deck state
        self.deck = YuGiOhDeck()
        self.deck_loaded = False
        self.current_hand: List[str] = []
        self.current_hand_categories: List[str] = []
        # One (card_name, category) entry per copy in the deck
        self.card_pool: CardPool = []
        # Per-copy tags from the Advanced view (aligned with deck.get_deck_list()); None = use counts
        self.manual_tags: Optional[List[str]] = None
        self.card_id_map: Dict[str, str] = {}  # card_name -> card_id
        self.image_loader = ImageLoader()
        self.advanced_view: Optional[AdvancedDeckView] = None
        self._advanced_overlay = None

        self.create_widgets()

    def _maximize(self):
        maximize(self)

    def create_widgets(self):
        """Create all UI components"""
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # TOP SECTION: Deck Loading
        self.deck_input_panel = DeckInputPanel(self, on_load=self.load_deck)
        self.deck_input_panel.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")

        # MIDDLE SECTION: Card Counts
        self.counts_panel = CountsPanel(self, on_apply=self.apply_and_draw,
                                        on_show_decklist=self.open_advanced_view,
                                        on_locked_click=self.switch_to_typed_counts)
        self.counts_panel.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")

        # BOTTOM SECTION: test hand and statistics, side by side with a draggable divider
        self.split_view = SplitView(self)
        self.split_view.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.hand_panel = HandPanel(self.split_view, self.image_loader, get_card_image_urls)
        self.stats_panel = StatsPanel(self.split_view)
        self.split_view.set_panels(self.hand_panel, self.stats_panel)

    # Loading a deck

    def load_deck(self, ydk_code: str):
        """Load deck from YDK file or ydke URL"""
        self.deck.clear_deck()
        self.card_pool = []
        self._set_manual_tags(None)

        try:
            try:
                card_ids = extract_main_deck_ids(ydk_code)
            except DeckParseError as e:
                messagebox.showerror("Error", str(e))
                return

            # Fetch card names
            self.counts_panel.set_status("Loading card names from API...", "yellow")
            self.update()
            card_database = fetch_multiple_card_names(list(set(card_ids)), verbose=False)

            # Count cards and remember each name's card ID (for image lookup)
            card_counts, card_id_map = count_cards(card_ids, card_database)
            self.card_id_map.update(card_id_map)
            try:
                fill_deck(self.deck, card_counts)
            except TooManyCopiesError as e:
                messagebox.showerror("Error", str(e))
                return

            self.deck_loaded = True
            self.counts_panel.show_deck_loaded(self.deck.get_deck_size(), None)
            self.counts_panel.enable_actions()

            # Show deck list in hand textbox
            self.hand_panel.show_deck_list(self.deck)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck:\n{str(e)}")
            self.counts_panel.set_status("Failed to load deck", "red")

    # Categories

    def _set_manual_tags(self, tags: Optional[List[str]]):
        """Switch between Advanced-view tags (count boxes locked) and typed counts."""
        self.manual_tags = tags if tags and any(tags) else None
        self.counts_panel.show_tags(self.manual_tags)
        if self.deck_loaded:
            self.counts_panel.show_deck_loaded(self.deck.get_deck_size(), self.manual_tags)

    def switch_to_typed_counts(self, entry: ctk.CTkEntry):
        """After confirmation, drop the decklist tags and unlock the count entries.

        The entries keep the tagged totals as a starting point. Which cards fill each
        category can't be known from counts alone, so they're assigned in deck-list order.
        """
        if self.manual_tags is None:
            return
        if not messagebox.askyesno(
                "Switch to typed counts?",
                "This removes your decklist tags. The counts will start from your current "
                "totals, but cards will no longer be assigned to categories by name.\n\n"
                "Switch to typed counts?"):
            return
        totals = [self.manual_tags.count(key) for key in (BRICK, NON_ENGINE, ENGINE)]
        self._set_manual_tags(None)
        self.card_pool = pool_from_counts(self.deck, *totals)
        sync_category_sets(self.deck, self.card_pool)
        entry.focus_set()
        entry.select_range(0, "end")

    def apply_and_draw(self):
        """Apply card counts and draw a hand"""
        if not self.deck_loaded:
            messagebox.showwarning("Warning", "Please load a deck first.")
            return

        if self.manual_tags is not None:
            # Categories come from the tags set in the Advanced view
            self.card_pool = pool_from_tags(self.deck, self.manual_tags)
            sync_category_sets(self.deck, self.card_pool)
            self.draw_hand()
            return

        try:
            brick_count, non_engine_count, engine_count = self.counts_panel.get_counts()
        except ValueError:
            messagebox.showerror("Error", "Please enter valid numbers for card counts.")
            return

        deck_size = self.deck.get_deck_size()
        total = brick_count + non_engine_count + engine_count

        if total > deck_size:
            messagebox.showerror("Error", f"Total counts ({total}) exceed deck size ({deck_size}).")
            return

        if brick_count < 0 or non_engine_count < 0 or engine_count < 0:
            messagebox.showerror("Error", "Card counts cannot be negative.")
            return

        self.card_pool = pool_from_counts(self.deck, brick_count, non_engine_count, engine_count)
        sync_category_sets(self.deck, self.card_pool)
        self.draw_hand()

    # Drawing

    def draw_hand(self):
        """Draw a test hand and display results"""
        pool = self.card_pool or pool_from_category_sets(self.deck)
        self.current_hand, self.current_hand_categories, sixth_card = draw_from_pool(pool)
        self.hand_panel.show_hand(self.current_hand, sixth_card, self.card_id_map)
        self.display_statistics()

    def display_statistics(self):
        """Calculate and display probability statistics"""
        pool = self.card_pool or pool_from_category_sets(self.deck)
        deck_size = self.deck.get_deck_size()
        # With typed counts, which cards fill each category is arbitrary (deck-list order),
        # so leave out everything that depends on a specific card's category
        tagged = self.manual_tags is not None
        report = format_statistics_report(deck_size, count_categories(pool),
                                          self.current_hand_categories if tagged else None)
        report += format_card_odds(pool, deck_size, grouped=tagged)
        self.stats_panel.show_text(report)

    # "Show Decklist" (Advanced view)

    def open_advanced_view(self):
        """Overlay the visual decklist for tagging cards on top of the main view."""
        if not self.deck_loaded or self.advanced_view is not None:
            return

        deck_list = self.deck.get_deck_list()
        if self.manual_tags is not None:
            tags = self.manual_tags
        else:
            # Start from the current categories so typed counts carry over
            pool = self.card_pool or pool_from_category_sets(self.deck)
            tags = [category for _, category in pool]

        # Overlay the view on top of the main GUI, filling the current window
        # (the cards scale to fit, so the window itself doesn't move or resize)
        self._advanced_overlay = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self._advanced_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._advanced_overlay.lift()
        self._advanced_overlay.grid_rowconfigure(0, weight=1)
        self._advanced_overlay.grid_columnconfigure(0, weight=1)
        self.update_idletasks()

        self.advanced_view = AdvancedDeckView(
            self._advanced_overlay, deck_list, tags, self.card_id_map,
            get_image_urls=get_card_image_urls,
            load_image=self.image_loader.download,
            on_done=self._close_advanced_view,
        )
        self.advanced_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def _close_advanced_view(self, tags: List[str]):
        """Remove the overlay and apply the tags from the Advanced view."""
        if self.advanced_view is not None:
            self._advanced_overlay.destroy()
            self.advanced_view = None

        self._set_manual_tags(tags)
        # With every tag cleared, this pool is all untagged, which wipes the old categories
        self.card_pool = pool_from_tags(self.deck, self.manual_tags or tags)
        sync_category_sets(self.deck, self.card_pool)
        if self.manual_tags is None:
            self.counts_panel.reset_counts()


def main():
    app = YuGiOhHandSimulator()
    app.mainloop()
