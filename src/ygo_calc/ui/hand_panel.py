"""The "Test Hand" panel: the drawn cards (scaled to always fit) and the text under them."""

import logging
import tkinter as tk
import tkinter.font as tkfont
from typing import Callable, Dict, List, Optional, Sequence

import customtkinter as ctk

from ..core.deck import YuGiOhDeck
from . import theme
from .image_loader import PIL_AVAILABLE, ImageLoader
from .text_layout import deck_list_lines, fit_font_size, hand_lines
from .window import lighten_scrollbar, window_scaling

CARD_W, CARD_H = 140, 205  # Card aspect ratio (and the initial thumbnail size)


class HandPanel(ctk.CTkFrame):
    """Shows a hand (5 cards + the 6th card) and a text box for the hand or deck list.

    The cards scale so the whole hand always fits; the text uses the largest font size
    (FONT_MAX..FONT_MIN) at which it fits. Both refit whenever the panel is resized.
    """

    # Font size range for the text under the cards
    FONT_MIN = 14
    FONT_MAX = 24

    def __init__(self, master, image_loader: ImageLoader,
                 get_image_urls: Callable[[str], List[str]]):
        super().__init__(master, fg_color=theme.PANEL_BG, corner_radius=theme.PANEL_CORNER_RADIUS,
                         border_width=1, border_color=theme.PANEL_BORDER)
        self.image_loader = image_loader
        self.get_image_urls = get_image_urls

        self.card_image_labels = []  # Image labels currently shown (for resizing)
        self.card_text_labels = []  # Name placeholders for cards without an image
        self._slots = 0  # Cards shown in the hand area (5 + the 6th card)
        self._thumb = (CARD_W, CARD_H)  # Current thumbnail size in pixels
        self._relayout_job = None  # Pending throttled refit of cards/text

        self._text_mode = "lines"  # "lines" (plain text) or "deck" (deck list in columns)
        self._text_lines = ["Load a deck and click 'Apply & Draw Hand' to begin..."]
        self._text_deck: Optional[YuGiOhDeck] = None
        self._text_rendered = None

        # Fixed split: card images get 3/5 of the height, the text 2/5
        # (uniform keeps the ratio exact regardless of what each part requests)
        self.grid_rowconfigure(1, weight=3, uniform="hand_split")
        self.grid_rowconfigure(2, weight=2, uniform="hand_split")
        self.grid_columnconfigure(0, weight=1)

        self._build_header()
        self._build_card_area()
        self._build_text_area()
        self._render_text()

    # Layout

    def _build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=(8, 4), padx=10, sticky='ew')
        header_frame.grid_columnconfigure(0, weight=1)
        hand_title = ctk.CTkLabel(header_frame, text="Test Hand",
                                  font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
        hand_title.grid(row=0, column=0, sticky='ew')

    def _build_card_area(self):
        self.cards_pane = tk.Frame(self, bg=theme.PANEL_BG)
        self.cards_pane.grid(row=1, column=0, padx=10, pady=(6, 0), sticky="nsew")
        self.cards_pane.grid_rowconfigure(0, weight=1)
        self.cards_pane.grid_columnconfigure(0, weight=1)

        # Canvas holding the cards (they scale so the whole hand + 6th card always fit)
        self.card_canvas = tk.Canvas(self.cards_pane, bg=theme.CARD_AREA_BG,
                                     highlightthickness=0, bd=0, relief="flat")
        self.card_canvas.grid(row=0, column=0, sticky="nsew")
        # Frame inside the canvas for card images (anchored at its centre so the hand is centred)
        self.cards_frame = tk.Frame(self.card_canvas, bg=theme.CARD_AREA_BG)
        self.cards_frame_id = self.card_canvas.create_window((0, 0), window=self.cards_frame, anchor="center")

        def _on_canvas_configure(event):
            # Keep the hand centred now; rescale the cards once resizing pauses
            self.card_canvas.coords(self.cards_frame_id, event.width / 2, event.height / 2)
            self.schedule_relayout()
        self.card_canvas.bind("<Configure>", _on_canvas_configure)

    def _build_text_area(self):
        self.text_frame = tk.Frame(self, bg=theme.TEXT_BG)
        self.text_frame.grid(row=2, column=0, padx=10, pady=(8, 10), sticky="nsew")
        self.text_frame.grid_rowconfigure(0, weight=1)
        self.text_frame.grid_columnconfigure(0, weight=1)

        self.font = tkfont.Font(family=theme.MONO_FONT, size=self.FONT_MIN)
        # width/height=1: a large font must never make the text box push the layout around
        self.textbox = tk.Text(
            self.text_frame,
            font=self.font,
            width=1,
            height=1,
            wrap="word",
            bg=theme.TEXT_BG,
            fg=theme.TEXT_FG,
            insertbackground=theme.TEXT_FG,
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            selectbackground=theme.TEXT_SELECT_BG,
            selectforeground="#ffffff",
            padx=8,
            pady=6,
        )
        self.textbox.grid(row=0, column=0, sticky="nsew")
        try:
            y_scroll = ctk.CTkScrollbar(self.text_frame, orientation="vertical", command=self.textbox.yview)
            lighten_scrollbar(y_scroll)
            y_scroll.grid(row=0, column=1, sticky="ns")
            try:
                y_scroll.configure(fg_color=theme.SCROLLBAR_BG, border_color=theme.SCROLLBAR_BG, corner_radius=6)
            except Exception:
                try:
                    y_scroll.configure(bg=theme.SCROLLBAR_BG)
                except Exception:
                    pass
        except Exception:
            y_scroll = tk.Scrollbar(self.text_frame, orient="vertical", command=self.textbox.yview)
            y_scroll.grid(row=0, column=1, sticky="ns")
            try:
                y_scroll.configure(bg=theme.SCROLLBAR_BG, troughcolor=theme.SCROLLBAR_BG,
                                   activebackground=theme.SCROLLBAR_BG)
            except Exception:
                pass
        self.textbox.configure(yscrollcommand=y_scroll.set)

        # Re-fit the text (font size, deck list columns) when the text area is resized
        self.textbox.bind("<Configure>", lambda _e: self.schedule_relayout())

    def preview_parts(self) -> List[tk.Widget]:
        """Areas drawn in the greyed-out layout preview while the divider is dragged."""
        return [self.cards_pane, self.text_frame]

    # Content

    def show_hand(self, hand: Sequence[str], sixth_card: Optional[str], card_id_map: Dict[str, str]):
        """Show the drawn hand's card images and its text."""
        # Clear previous card images
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_image_labels.clear()
        self.card_text_labels.clear()
        thumb_w, thumb_h = self._thumb

        if PIL_AVAILABLE:
            for i, card in enumerate(hand):
                # Frame for each card (padding around thumbnail)
                card_frame = ctk.CTkFrame(self.cards_frame, fg_color=theme.WINDOW_BG, corner_radius=6)
                card_frame.grid(row=0, column=i, padx=4, pady=6)
                self._show_card(card_frame, card, card_id_map, thumb_w, thumb_h)

            if sixth_card:
                # Separator, then the 6th card (going second)
                sep_label = ctk.CTkLabel(self.cards_frame, text="→", font=ctk.CTkFont(size=26))
                sep_label.grid(row=0, column=5, padx=6)
                card_frame = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
                card_frame.grid(row=0, column=6, padx=4, pady=6)
                self._show_card(card_frame, sixth_card, card_id_map, thumb_w, thumb_h)

        # Scale the cards so all of them (including the 6th) fit the card area
        self._slots = len(hand) + (1 if sixth_card else 0)
        self.fit_cards()

        self.show_lines(hand_lines(hand, sixth_card))

    def show_deck_list(self, deck: YuGiOhDeck):
        """Show the deck list (in as many columns as fit) in the text box."""
        self._text_mode = "deck"
        self._text_deck = deck
        self._render_text()

    def show_lines(self, lines: List[str]):
        """Show plain lines of text (e.g. the drawn hand) in the text box."""
        self._text_mode = "lines"
        self._text_lines = lines
        self._render_text()

    def _show_card(self, parent, card_name: str, card_id_map: Dict[str, str], tw: int, th: int):
        """Display the first image that loads for the card; otherwise show its name."""
        for url in self.get_image_urls(card_id_map.get(card_name, '')):
            try:
                img_tk = self.image_loader.photo(url, tw, th)
            except Exception:
                logging.warning("Failed to load image for %s from %s", card_name, url)
                continue

            # corner_radius=0: CTkLabel pads its content by the corner radius, which
            # would add empty space around every card
            label = ctk.CTkLabel(parent, image=img_tk, text="", corner_radius=0)
            label.image = img_tk  # Keep reference
            # Tag label with source url for responsive resizing
            label._image_url = url
            label.grid(row=0, column=0)
            self.card_image_labels.append(label)
            return

        # No image source worked: show the card name instead
        label = ctk.CTkLabel(parent, text=card_name, fg_color=theme.CARD_PLACEHOLDER_BG, corner_radius=5)
        self._size_text_label(label, tw, th)
        label.grid(row=0, column=0)
        self.card_text_labels.append(label)

    @staticmethod
    def _size_text_label(label, tw: int, th: int):
        """Size a name placeholder to tw x th pixels (CTk sizes are logical, so unscale)."""
        scale = window_scaling(label)
        label.configure(width=max(1, int(tw / scale)), height=max(1, int(th / scale)),
                        wraplength=max(1, int((tw - 12) / scale)))

    # Fitting to the available space

    def schedule_relayout(self):
        """Refit cards and text at most every ~30ms while resizing (smooth, no flicker).

        Resize events arrive far faster than that; batching them means one refit per
        frame, and the pending refit always sees the latest size.
        """
        if self._relayout_job is None:
            self._relayout_job = self.after(30, self.relayout)

    def relayout(self):
        self._relayout_job = None
        try:
            self.fit_cards()
            self._render_text()
        except Exception:
            logging.exception("Failed to refit the test hand")

    def fit_cards(self):
        """Size the thumbnails so every card (including the 6th) fits the card area."""
        canvas_w, canvas_h = self.card_canvas.winfo_width(), self.card_canvas.winfo_height()
        if self._slots == 0 or canvas_w <= 1 or canvas_h <= 1:
            return

        # The space taken by padding, the arrow and card frames is measured from the
        # current layout (it doesn't depend on card size); the cards get the rest
        self.cards_frame.update_idletasks()
        thumb_w, thumb_h = self._thumb
        extra_w = max(0, self.cards_frame.winfo_reqwidth() - self._slots * thumb_w)
        extra_h = max(0, self.cards_frame.winfo_reqheight() - thumb_h)
        by_width = (canvas_w - extra_w) / self._slots * CARD_H / CARD_W
        by_height = canvas_h - extra_h
        new_h = max(20, int(min(by_width, by_height)))
        new_size = (int(new_h * CARD_W / CARD_H), new_h)
        if new_size != self._thumb:
            self._resize_thumbnails(*new_size)

    def _resize_thumbnails(self, thumb_w: int, thumb_h: int):
        """Resize all displayed thumbnails (and name placeholders) to thumb_w x thumb_h."""
        self._thumb = (thumb_w, thumb_h)

        for lbl in list(self.card_image_labels):
            url = getattr(lbl, '_image_url', None)
            if not url:
                continue
            try:
                img_tk = self.image_loader.photo(url, thumb_w, thumb_h)
                lbl.configure(image=img_tk)
                lbl.image = img_tk
            except Exception:
                continue

        for lbl in self.card_text_labels:
            self._size_text_label(lbl, thumb_w, thumb_h)

    def _render_text(self):
        """Render the text box at the largest font size (FONT_MAX..FONT_MIN) that fits.

        If even the minimum size doesn't fit, it stays at the minimum and the box scrolls.
        """
        tb = self.textbox
        avail_w = tb.winfo_width() - 2 * int(tb.cget("padx")) - 4
        avail_h = tb.winfo_height() - 2 * int(tb.cget("pady")) - 4

        if self._text_mode == "deck" and self._text_deck is not None:
            deck = self._text_deck

            def lines_for(font):
                return deck_list_lines(deck, avail_w // max(1, font.measure("0")))
        else:
            def lines_for(_font):
                return self._text_lines
        size, lines = fit_font_size(
            lines_for, lambda size: tkfont.Font(family=theme.MONO_FONT, size=size),
            avail_w, avail_h, self.FONT_MIN, self.FONT_MAX)

        # Skip if nothing changed: re-applying the font makes Tk re-measure the widget,
        # which fires <Configure> and would trigger another relayout
        rendered = (size, self._text_mode, tuple(lines))
        if rendered == self._text_rendered:
            return
        self._text_rendered = rendered
        if int(self.font.cget("size")) != size:
            self.font.configure(size=size)
        tb.configure(state="normal", wrap="none" if self._text_mode == "deck" else "word")
        tb.delete("1.0", "end")
        tb.insert("1.0", "\n".join(lines))
        tb.configure(state="disabled")
