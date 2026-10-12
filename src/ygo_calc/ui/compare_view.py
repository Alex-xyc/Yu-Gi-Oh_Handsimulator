"""The "Compare Decks" overlay: two tabs to set up a deck each, and their odds side by side.

Each tab (DeckSetup) loads a deck and sets its categories the same way as the main
window: typed brick / non-engine / engine counts, or tags from "Show Decklist".

Copyright (c) 2026 Alex-xyc
"""

from tkinter import messagebox
from typing import Callable, Dict, List, Optional, Tuple

import customtkinter as ctk

from ..cards import get_card_image_urls
from ..core.categories import BRICK, ENGINE, NON_ENGINE, pool_from_counts, pool_from_tags
from ..core.comparison import DeckSummary, format_comparison
from ..core.deck import YuGiOhDeck
from ..core.deck_builder import TooManyCopiesError
from ..core.deck_parser import DeckParseError
from . import theme
from .advanced_view import AdvancedDeckView
from .counts_panel import CountsPanel
from .deck_input_panel import DeckInputPanel
from ..deck_loading import load_main_deck
from .image_loader import ImageLoader
from .window import lighten_scrollbar

DECK_NAMES = ("Deck 1", "Deck 2")
HAND_SIZES = {"Going first": 5, "Going second": 6}


class DeckSetup(ctk.CTkFrame):
    """One tab: load a deck, then give it typed counts or decklist tags."""

    def __init__(self, master, name: str, image_loader: ImageLoader):
        super().__init__(master, fg_color="transparent")
        self.name = name
        self.image_loader = image_loader
        self.deck = YuGiOhDeck()
        self.deck_loaded = False
        self.card_id_map: Dict[str, str] = {}
        # Per-copy tags from "Show Decklist" (aligned with deck.get_deck_list()); None = use counts
        self.manual_tags: Optional[List[str]] = None
        self.advanced_view: Optional[AdvancedDeckView] = None
        self._advanced_overlay = None

        self.grid_columnconfigure(0, weight=1)

        self.deck_input_panel = DeckInputPanel(self, on_load=self.load_deck, show_title=False)
        self.deck_input_panel.grid(row=0, column=0, padx=5, pady=(5, 5), sticky="ew")

        self.counts_panel = CountsPanel(self, on_apply=None, on_show_decklist=self.open_advanced_view,
                                        on_locked_click=self.switch_to_typed_counts)
        self.counts_panel.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

    # Loading

    def load_deck(self, deck_code: str):
        self.deck_loaded = False
        self._set_manual_tags(None)
        self.counts_panel.set_status("Loading card names from API...", "yellow")
        self.update()
        try:
            self.card_id_map.update(load_main_deck(self.deck, deck_code))
        except (DeckParseError, TooManyCopiesError) as e:
            messagebox.showerror("Error", str(e), parent=self)
            self.counts_panel.set_status("Failed to load deck", "red")
            return
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck:\n{e}", parent=self)
            self.counts_panel.set_status("Failed to load deck", "red")
            return
        self._loaded()
        self.counts_panel.reset_counts()

    def copy_from(self, deck: YuGiOhDeck, card_id_map: Dict[str, str], tags: Optional[List[str]],
                  counts: Tuple[int, int, int]):
        """Start from another deck's setup (the main window's), with its tags or typed counts."""
        self.deck.clear_deck()
        for card_name, copies in deck.cards.items():
            self.deck.add_card(card_name, copies)
        self.card_id_map.update(card_id_map)
        self._loaded()
        self._set_manual_tags(tags)
        if self.manual_tags is None:
            self.counts_panel.set_counts(*counts)

    def _loaded(self):
        self.deck_loaded = True
        self.counts_panel.show_deck_loaded(self.deck.get_deck_size(), self.manual_tags)
        self.counts_panel.enable_actions()

    # Categories

    def _set_manual_tags(self, tags: Optional[List[str]]):
        """Switch between decklist tags (count boxes locked) and typed counts."""
        self.manual_tags = tags if tags and any(tags) else None
        self.counts_panel.show_tags(self.manual_tags)
        if self.deck_loaded:
            self.counts_panel.show_deck_loaded(self.deck.get_deck_size(), self.manual_tags)

    def switch_to_typed_counts(self, entry: ctk.CTkEntry):
        """After confirmation, drop the decklist tags and unlock the count entries."""
        if self.manual_tags is None:
            return
        if not messagebox.askyesno(
                "Switch to typed counts?",
                "This removes the decklist tags of this deck. The counts will start from its "
                "current totals.\n\nSwitch to typed counts?", parent=self):
            return
        totals = [self.manual_tags.count(key) for key in (BRICK, NON_ENGINE, ENGINE)]
        self._set_manual_tags(None)
        self.counts_panel.set_counts(*totals)
        entry.focus_set()
        entry.select_range(0, "end")

    def summary(self) -> DeckSummary:
        """The deck with its categories; raises ValueError (with a message) if not set up."""
        if not self.deck_loaded:
            raise ValueError("No deck loaded.")
        if self.manual_tags is not None:
            return DeckSummary(self.name, pool_from_tags(self.deck, self.manual_tags))
        try:
            brick, non_engine, engine = self.counts_panel.get_counts()
        except ValueError:
            raise ValueError("Please enter valid numbers for card counts.") from None
        if min(brick, non_engine, engine) < 0:
            raise ValueError("Card counts cannot be negative.")
        deck_size = self.deck.get_deck_size()
        total = brick + non_engine + engine
        if total > deck_size:
            raise ValueError(f"Total counts ({total}) exceed deck size ({deck_size}).")
        return DeckSummary(self.name, pool_from_counts(self.deck, brick, non_engine, engine))

    # "Show Decklist" (tagging), overlaid on the whole window like the main decklist view

    def open_advanced_view(self):
        if not self.deck_loaded or self.advanced_view is not None:
            return
        if self.manual_tags is not None:
            tags = self.manual_tags
        else:
            # Start from the typed counts, if they're valid
            try:
                tags = [category for _, category in self.summary().pool]
            except ValueError:
                tags = []

        window = self.winfo_toplevel()
        self._advanced_overlay = ctk.CTkFrame(window, fg_color="transparent", corner_radius=0)
        self._advanced_overlay.place(x=0, y=0, relwidth=1, relheight=1)
        self._advanced_overlay.lift()
        self._advanced_overlay.grid_rowconfigure(0, weight=1)
        self._advanced_overlay.grid_columnconfigure(0, weight=1)
        window.update_idletasks()

        self.advanced_view = AdvancedDeckView(
            self._advanced_overlay, self.deck.get_deck_list(), tags, self.card_id_map,
            get_image_urls=get_card_image_urls,
            load_image=self.image_loader.download,
            on_done=self._close_advanced_view,
        )
        self.advanced_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def _close_advanced_view(self, tags: List[str]):
        if self.advanced_view is not None:
            self._advanced_overlay.destroy()
            self.advanced_view = None
        self._set_manual_tags(tags)
        if self.manual_tags is None:
            self.counts_panel.reset_counts()


class CompareView(ctk.CTkFrame):
    """Overlay with two deck tabs plus a side-by-side comparison of their opening-hand odds."""

    def __init__(self, master, image_loader: ImageLoader, on_close: Callable[[], None]):
        super().__init__(master, fg_color=theme.PANEL_BG, corner_radius=theme.PANEL_CORNER_RADIUS,
                         border_width=1, border_color=theme.PANEL_BORDER)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)  # The tabs keep their size, results take the rest

        # Header: title and close
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 0))
        header.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(header, text="Compare Decks",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w")
        ctk.CTkButton(header, text="Close", width=120, fg_color="gray35", hover_color="gray25",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=on_close).grid(row=0, column=2)

        # Deck tabs
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, padx=10, pady=(0, 0), sticky="nsew")
        self.setups: List[DeckSetup] = []
        for name in DECK_NAMES:
            tab = self.tabview.add(name)
            tab.grid_columnconfigure(0, weight=1)
            setup = DeckSetup(tab, name, image_loader)
            setup.grid(row=0, column=0, sticky="nsew")
            self.setups.append(setup)

        # Comparison controls
        controls = ctk.CTkFrame(self, fg_color="transparent")
        controls.grid(row=2, column=0, padx=10, pady=8)
        self.hand_choice = ctk.CTkSegmentedButton(controls, values=list(HAND_SIZES),
                                                  command=lambda _value: self._recalculate())
        self.hand_choice.set(next(iter(HAND_SIZES)))
        self.hand_choice.grid(row=0, column=0, padx=(0, 15))
        ctk.CTkButton(controls, text="Calculate & Compare", width=190, command=self.compare,
                      font=ctk.CTkFont(size=14, weight="bold"),
                      fg_color="green", hover_color="darkgreen").grid(row=0, column=1)

        # Results
        results = ctk.CTkFrame(self, fg_color=theme.PANEL_BG, corner_radius=theme.PANEL_CORNER_RADIUS,
                               border_width=1, border_color=theme.PANEL_BORDER)
        results.grid(row=3, column=0, padx=10, pady=(0, 10), sticky="nsew")
        results.grid_columnconfigure(0, weight=1)
        results.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(results, text="Comparison", font=ctk.CTkFont(size=16, weight="bold")).grid(
            row=0, column=0, pady=(10, 5))
        self.results_text = ctk.CTkTextbox(results, font=ctk.CTkFont(family=theme.MONO_FONT, size=13))
        for scrollbar in (getattr(self.results_text, "_y_scrollbar", None),
                          getattr(self.results_text, "_x_scrollbar", None)):
            if scrollbar is not None:
                lighten_scrollbar(scrollbar)
        self.results_text.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
        self._compared = False
        self._show_results("Set up both decks in the tabs above, then click 'Calculate & Compare'.\n\n"
                           "Each deck can use typed counts or tags from 'Show Decklist'.")

    def compare(self):
        summaries = []
        for setup in self.setups:
            try:
                summaries.append(setup.summary())
            except ValueError as e:
                self.tabview.set(setup.name)
                messagebox.showerror("Error", f"{setup.name}: {e}", parent=self)
                return
        hand_size = HAND_SIZES[self.hand_choice.get()]
        self._show_results(format_comparison(*summaries, hand_size=hand_size))
        self._compared = True

    def _recalculate(self):
        # Switching first/second updates results that are already shown
        if self._compared:
            self.compare()

    def _show_results(self, text: str):
        self.results_text.configure(state="normal")
        self.results_text.delete("1.0", "end")
        self.results_text.insert("1.0", text)
        self.results_text.configure(state="disabled")
