"""Advanced deck view for the Yu-Gi-Oh! Hand Simulator.

Shows the main deck as a grid of card images where each card can be tagged
as a brick, non-engine or engine card. Tagged cards are tinted with their
tag colour so the card art stays visible.

Copyright (c) 2026 Alex-xyc
"""

import logging
import math
import queue
import threading
import tkinter as tk
from typing import Callable, Dict, List, Optional

import customtkinter as ctk

from ..core.categories import BRICK, ENGINE, NON_ENGINE, UNTAGGED
from . import theme
from .image_loader import PIL_AVAILABLE

if PIL_AVAILABLE:
    from PIL import Image, ImageTk


# Tag key -> (label, tint colour)
TAGS = {
    BRICK: ("Brick", "#dc2626"),
    NON_ENGINE: ("Non-Engine", "#eab308"),
    ENGINE: ("Engine", "#16a34a"),
}
UNTAG = UNTAGGED
TINT_OPACITY = 0.45

CARD_W, CARD_H = 140, 205  # Card aspect ratio
GAP = 6
BORDER = 2  # Tag-coloured border around each tile
TILE_EXTRA = GAP + 2 * BORDER  # Pixels each tile takes beyond the card image
BG = theme.CARD_AREA_BG
UNTAGGED_TEXT_BG = theme.CARD_PLACEHOLDER_BG


class AdvancedDeckView(ctk.CTkFrame):
    """Visual decklist where each card copy can be tagged by clicking it."""

    def __init__(self, master, deck_list: List[str], tags: List[str],
                 card_id_map: Dict[str, str],
                 get_image_urls: Callable[[str], List[str]],
                 load_image: Callable[[str], "Image.Image"],
                 on_done: Callable[[List[str]], None]):
        super().__init__(master, fg_color="#2b2b2b", corner_radius=12,
                         border_width=1, border_color="#3a3a3a")
        self.deck_list = deck_list
        self.tags = list(tags) if len(tags) == len(deck_list) else [UNTAG] * len(deck_list)
        self.card_id_map = card_id_map
        self.get_image_urls = get_image_urls
        self.load_image = load_image
        self.on_done = on_done

        # Thumbnails are real pixels, so scale them to match CTk's DPI scaling
        try:
            self.scale = ctk.ScalingTracker.get_widget_scaling(self)
        except Exception:
            self.scale = 1.0
        # Provisional size; the grid is refitted to its real area once laid out
        self.columns = 10
        self._set_card_size(int(CARD_H * self.scale * 0.6))
        self._resize_job = None

        self.originals: Dict[str, Optional["Image.Image"]] = {}  # card name -> image (None = no image)
        self.photo_cache: Dict[tuple, "ImageTk.PhotoImage"] = {}
        self.tiles: List[tk.Label] = []
        self._image_queue: "queue.Queue" = queue.Queue()
        self._closed = False

        self.tool = ctk.StringVar(value=BRICK)
        self.all_copies = ctk.BooleanVar(value=True)

        self._build()
        self._layout_tiles()
        self._refresh_all()
        self._start_image_loading()

    # Sizing (all in physical pixels, matching winfo sizes and image pixels)

    @staticmethod
    def best_fit(card_count: int, width: int, height: int) -> tuple:
        """Pick the column count giving the largest cards that all fit in width x height.

        Returns (columns, card_height).
        """
        best = (1, 1)
        for columns in range(1, max(1, card_count) + 1):
            rows = math.ceil(card_count / columns)
            by_width = (width / columns - TILE_EXTRA) * CARD_H / CARD_W
            by_height = height / rows - TILE_EXTRA
            card_h = int(min(by_width, by_height))
            if card_h > best[1]:
                best = (columns, card_h)
        return best

    def _set_card_size(self, card_h: int):
        self.card_h = max(1, card_h)
        self.card_w = max(1, int(self.card_h * CARD_W / CARD_H))

    def _on_resize(self, _event):
        # Debounce: refit once the user stops resizing
        if self._resize_job is not None:
            self.after_cancel(self._resize_job)
        self._resize_job = self.after(100, self._refit)

    def _refit(self):
        self._resize_job = None
        width, height = self.grid_area.winfo_width(), self.grid_area.winfo_height()
        if width <= 1 or height <= 1:
            return  # Not laid out yet
        columns, card_h = self.best_fit(len(self.deck_list), width, height)
        if (columns, card_h) == (self.columns, self.card_h):
            return
        self._set_card_size(card_h)
        self.photo_cache.clear()
        if columns != self.columns:
            self.columns = columns
            self._layout_tiles()
        for tile in self.tiles:
            tile.configure(wraplength=max(1, self.card_w - 10))
        self._refresh_all()

    def _layout_tiles(self):
        for index, tile in enumerate(self.tiles):
            tile.grid(row=index // self.columns, column=index % self.columns,
                      padx=GAP // 2, pady=GAP // 2)

    def _build(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)

        # Header: title, counts and navigation
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(10, 4))
        header.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(header, text="Advanced: Tag Your Decklist",
                     font=ctk.CTkFont(size=18, weight="bold")).grid(row=0, column=0, sticky="w")
        self.counts_label = ctk.CTkLabel(header, text="", font=ctk.CTkFont(size=14))
        self.counts_label.grid(row=0, column=1, padx=10)

        ctk.CTkButton(header, text="Clear All Tags", width=120, fg_color="gray35",
                      hover_color="gray25", command=self.clear_tags).grid(row=0, column=2, padx=5)
        ctk.CTkButton(header, text="Done", width=120, fg_color="green", hover_color="darkgreen",
                      font=ctk.CTkFont(size=14, weight="bold"),
                      command=self.finish).grid(row=0, column=3, padx=(5, 0))

        # Toolbar: which tag a click applies
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.grid(row=1, column=0, sticky="ew", padx=12, pady=(0, 6))

        ctk.CTkLabel(toolbar, text="Click a card to tag it as:",
                     font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 8))
        for key, (label, colour) in TAGS.items():
            # width=0 sizes each option to its text (default is a fixed 100px)
            ctk.CTkRadioButton(toolbar, text=label, variable=self.tool, value=key, width=0,
                               fg_color=colour, hover_color=colour).pack(side="left", padx=(0, 14))
        ctk.CTkCheckBox(toolbar, text="Tag all copies", variable=self.all_copies).pack(side="left", padx=(16, 6))
        ctk.CTkLabel(toolbar, text="(click again or right-click to untag)", text_color="gray",
                     font=ctk.CTkFont(size=12)).pack(side="left", padx=6)

        # Bulk actions: tag every untagged copy at once
        bulk_bar = ctk.CTkFrame(self, fg_color="transparent")
        bulk_bar.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 6))

        self.bulk_label = ctk.CTkLabel(bulk_bar, text="", font=ctk.CTkFont(size=13))
        self.bulk_label.pack(side="left", padx=(0, 8))
        self.bulk_buttons = []
        for key, (label, colour) in TAGS.items():
            button = ctk.CTkButton(bulk_bar, text=label, width=110, fg_color=colour,
                                   hover_color=colour, text_color="black" if key == NON_ENGINE else "white",
                                   font=ctk.CTkFont(size=13, weight="bold"),
                                   command=lambda k=key: self.tag_untagged(k))
            button.pack(side="left", padx=6)
            self.bulk_buttons.append(button)

        # Card grid: fills the remaining space (no scrolling), cards are sized to fit it.
        # grid_propagate(False) keeps the tiles from resizing the area they're measured from.
        self.grid_area = tk.Frame(self, bg=BG, highlightthickness=0)
        self.grid_area.grid(row=3, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.grid_area.grid_propagate(False)
        self.grid_area.bind("<Configure>", self._on_resize)
        cards_frame = tk.Frame(self.grid_area, bg=BG)
        cards_frame.place(relx=0.5, rely=0.5, anchor="center")

        for index in range(len(self.deck_list)):
            tile = tk.Label(cards_frame, bg=BG, fg="white", bd=0, cursor="hand2",
                            wraplength=self.card_w - 10, justify="center",
                            font=("Segoe UI", 9))
            tile.bind("<Button-1>", lambda _e, i=index: self.tag_card(i, self.tool.get()))
            tile.bind("<Button-3>", lambda _e, i=index: self.tag_card(i, UNTAG))
            self.tiles.append(tile)

    # Tagging

    def tag_card(self, index: int, tag: str):
        """Apply tag to a card copy (or all copies of that card).

        Clicking a card that already has the selected tag untags it instead.
        """
        if tag and self.tags[index] == tag:
            tag = UNTAG
        if self.all_copies.get():
            card_name = self.deck_list[index]
            indices = [i for i, name in enumerate(self.deck_list) if name == card_name]
        else:
            indices = [index]
        for i in indices:
            self.tags[i] = tag
            self._render_tile(i)
        self._update_counts()

    def tag_untagged(self, tag: str):
        """Give every still-untagged copy the given tag."""
        for i, current in enumerate(self.tags):
            if current == UNTAG:
                self.tags[i] = tag
                self._render_tile(i)
        self._update_counts()

    def clear_tags(self):
        self.tags = [UNTAG] * len(self.deck_list)
        self._refresh_all()

    def finish(self):
        self._closed = True
        self.on_done(list(self.tags))

    def destroy(self):
        self._closed = True
        super().destroy()

    def _update_counts(self):
        counts = {key: self.tags.count(key) for key in TAGS}
        untagged = self.tags.count(UNTAG)
        self.counts_label.configure(
            text=(f"Bricks: {counts['brick']}  |  Non-Engine: {counts['non_engine']}  |  "
                  f"Engine: {counts['engine']}  |  Untagged: {untagged}  "
                  f"(Total: {len(self.deck_list)})"))
        self.bulk_label.configure(text=f"Mark the rest ({untagged} untagged) as:")
        for key, button in zip(TAGS, self.bulk_buttons):
            colour = TAGS[key][1] if untagged else "gray30"
            button.configure(state="normal" if untagged else "disabled",
                             fg_color=colour, hover_color=colour)

    # Rendering

    def _refresh_all(self):
        for i in range(len(self.tiles)):
            self._render_tile(i)
        self._update_counts()

    def _render_tile(self, index: int):
        tile = self.tiles[index]
        card_name = self.deck_list[index]
        tag = self.tags[index]
        colour = TAGS[tag][1] if tag else None
        original = self.originals.get(card_name)

        if original is not None:
            photo = self._tinted_photo(card_name, original, tag)
            tile.configure(image=photo, text="", compound="none", bg=BG)
            tile.image = photo
        else:
            # No image (yet): show the card name on a tag-coloured background.
            # A blank image makes tk size the label in pixels, matching image tiles.
            if not hasattr(self, "_blank"):
                self._blank = tk.PhotoImage(width=1, height=1)
            tile.configure(image=self._blank, text=card_name, compound="center",
                           bg=colour or UNTAGGED_TEXT_BG)
            tile.image = self._blank
        tile.configure(width=self.card_w, height=self.card_h,
                       highlightthickness=BORDER, highlightbackground=colour or BG)

    def _tinted_photo(self, card_name: str, original: "Image.Image", tag: str):
        key = (card_name, tag, self.card_w, self.card_h)
        photo = self.photo_cache.get(key)
        if photo is None:
            img = original.convert("RGB").resize((self.card_w, self.card_h), Image.Resampling.LANCZOS)
            if tag:
                overlay = Image.new("RGB", img.size, TAGS[tag][1])
                img = Image.blend(img, overlay, TINT_OPACITY)
            photo = ImageTk.PhotoImage(img)
            self.photo_cache[key] = photo
        return photo

    # Image loading (downloads in a worker thread, Tk updates on the main thread)

    def _start_image_loading(self):
        if not PIL_AVAILABLE:
            return
        names = list(dict.fromkeys(self.deck_list))
        jobs = [(name, self.get_image_urls(self.card_id_map.get(name, ''))) for name in names]
        threading.Thread(target=self._load_images, args=(jobs,), daemon=True).start()
        self.after(100, self._poll_images)

    def _load_images(self, jobs):
        for card_name, urls in jobs:
            if self._closed:
                return
            image = None
            for url in urls:
                try:
                    image = self.load_image(url)
                    break
                except Exception:
                    logging.warning("Failed to load image for %s from %s", card_name, url)
            self._image_queue.put((card_name, image))
        self._image_queue.put(None)

    def _poll_images(self):
        if self._closed or not self.winfo_exists():
            return
        finished = False
        try:
            while True:
                item = self._image_queue.get_nowait()
                if item is None:
                    finished = True
                    break
                card_name, image = item
                self.originals[card_name] = image
                if image is not None:
                    for i, name in enumerate(self.deck_list):
                        if name == card_name:
                            self._render_tile(i)
        except queue.Empty:
            pass
        if not finished:
            self.after(100, self._poll_images)
