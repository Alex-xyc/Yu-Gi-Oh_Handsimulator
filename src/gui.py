"""GUI for the Yu-Gi-Oh! Hand Simulator.

Provides a CustomTkinter-based desktop application to load decks,
draw simulated opening hands, and display probability statistics.

Copyright (c) 2026 Alex-xyc
"""

import os
import sys
import ctypes
import random
import urllib.request
import math
from io import BytesIO
from typing import Dict, List, Optional, Tuple

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox

import customtkinter as ctk
import logging


try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


from main import (
    YuGiOhDeck,
    fetch_multiple_card_names,
    parse_ydke_url,
    hypergeometric_probability,
    probability_at_least,
    comb,
    get_card_image_urls
)
from advanced_view import AdvancedDeckView


def _lighten_scrollbar(scrollbar: ctk.CTkScrollbar):
    """Stop a CTkScrollbar forcing a full layout pass on every scroll update.

    CTkScrollbar._draw() ends with canvas.update_idletasks(), and the attached text box
    calls set() -> _draw() whenever its view changes, so every resize step processed the
    whole window's pending layout synchronously (100-400ms). Tk redraws on idle anyway.
    """
    canvas = getattr(scrollbar, "_canvas", None)
    if canvas is not None:
        canvas.update_idletasks = lambda: None


class YuGiOhHandSimulator(ctk.CTk):
    """Yu-Gi-Oh Hand Simulator GUI Application"""

    def __init__(self):
        # On Windows, set an explicit AppUserModelID before creating windows so
        # the taskbar associates our process with the application icon.
        if sys.platform == "win32":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("AlexXYC.YuGiOhHandSimulator")
            except Exception as e:
                logging.debug("Failed to set AppUserModelID: %s", e)

        super().__init__()

        # Configure window (larger default for bigger hands/images)
        self.title("Yu-Gi-Oh! Hand Simulator by Xin Yuan")
        self._set_default_geometry()

        # Load app icon from `icons/` folder (prefer .ico on Windows,
        # also set an iconphoto so the taskbar uses the same image)
        try:
            # Handle PyInstaller _MEIPASS for bundled .exe
            if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(__file__)

            icon_path = os.path.join(base_path, "icons", "ghattic.ico")
            if not os.path.exists(icon_path):
                alt_path = os.path.join(base_path, "icons", "ghattic.ic")
                if os.path.exists(alt_path):
                    icon_path = alt_path

            if os.path.exists(icon_path):
                # Primary: set iconbitmap (Windows)
                try:
                    self.iconbitmap(icon_path)
                except Exception as e:
                    logging.debug("iconbitmap failed: %s", e)

                # Secondary: set an iconphoto (some environments/taskbars prefer this)
                try:
                    if PIL_AVAILABLE:
                        img = Image.open(icon_path).convert("RGBA")
                        img = img.resize((64, 64), Image.LANCZOS)
                        tk_img = ImageTk.PhotoImage(img)
                        self.iconphoto(True, tk_img)
                        # keep reference to avoid GC
                        self._icon_img = tk_img
                    else:
                        png_path = os.path.splitext(icon_path)[0] + ".png"
                        if os.path.exists(png_path):
                            png_img = tk.PhotoImage(file=png_path)
                            self.iconphoto(True, png_img)
                            self._icon_img = png_img
                except Exception:
                    logging.exception("Failed to load icon image")
        except Exception:
            logging.exception("Unexpected error while setting application icon")

        # Set theme
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # Initialize deck
        self.deck = YuGiOhDeck()
        self.deck_loaded = False
        self.current_hand = []
        self.current_hand_categories: List[str] = []
        # One (card_name, category) entry per copy in the deck
        self.card_pool: List[Tuple[str, str]] = []
        # Per-copy tags from the Advanced view (aligned with deck.get_deck_list()); None = use counts
        self.manual_tags: Optional[List[str]] = None
        self.advanced_view: Optional[AdvancedDeckView] = None
        self.card_id_map: Dict[str, str] = {}  # card_name -> card_id
        self.image_cache: Dict[str, ImageTk.PhotoImage] = {}  # Cache loaded images (keyed by url|WxH)
        self.orig_images: Dict[str, 'Image.Image'] = {}  # Store original PIL images by URL
        self.card_image_labels = []  # Store image label references
        self.card_text_labels = []  # Name placeholders for cards without an image
        self._hand_slots = 0  # Cards shown in the hand area (5 + the 6th card)
        self._hand_thumb = (140, 205)  # Current thumbnail size in pixels
        self._relayout_job = None  # Pending debounced refit of cards/text

        # Create UI
        self.create_widgets()

    # Size that shows the full hand and all statistics without scrolling (logical px)
    DEFAULT_SIZE = (1400, 1090)
    MIN_SIZE = (1100, 800)

    def _set_default_geometry(self):
        """Open centred at DEFAULT_SIZE, or maximized if the screen is too small for it."""
        try:
            scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            scale = 1.0
        screen_w = int(self.winfo_screenwidth() / scale)
        screen_h = int(self.winfo_screenheight() / scale)
        # Leave room for the title bar and taskbar
        avail_w, avail_h = screen_w - 40, screen_h - 80
        width, height = self.DEFAULT_SIZE

        self.minsize(min(self.MIN_SIZE[0], avail_w), min(self.MIN_SIZE[1], avail_h))
        if width <= avail_w and height <= avail_h:
            x = (screen_w - width) // 2
            y = max(0, (screen_h - height) // 2 - 20)
            self.geometry(f"{width}x{height}+{x}+{y}")
        else:
            self.geometry(f"{min(width, avail_w)}x{min(height, avail_h)}+20+20")
            # CTk applies its own startup geometry, so maximize once the window is up
            self.after(0, self._maximize)

    def _maximize(self):
        try:
            self.state("zoomed")  # Windows / macOS
        except tk.TclError:
            try:
                self.attributes("-zoomed", True)  # Linux (X11)
            except tk.TclError:
                pass

    def create_widgets(self):
        """Create all UI components"""

        # Main container with grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # TOP SECTION: Deck Loading
        deck_frame = ctk.CTkFrame(self)
        deck_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
        deck_frame.grid_columnconfigure(1, weight=1)

        # Title
        title_label = ctk.CTkLabel(deck_frame, text="Yu-Gi-Oh Hand Simulator By Xin Yuan",
                                    font=ctk.CTkFont(size=24, weight="bold"))
        title_label.grid(row=0, column=0, columnspan=3, pady=(10, 15))

        # YDKE Code input
        ydke_label = ctk.CTkLabel(deck_frame, text="YDKe Code:", font=ctk.CTkFont(size=14))
        ydke_label.grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")

        self.ydke_entry = ctk.CTkEntry(deck_frame, placeholder_text="Paste your ydke code here...",
                                        width=500)
        self.ydke_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        load_ydke_btn = ctk.CTkButton(deck_frame, text="Load Deck", width=100,
                                       command=self.load_from_ydke)
        load_ydke_btn.grid(row=1, column=2, padx=(5, 15), pady=5)

        # OR divider
        or_label = ctk.CTkLabel(deck_frame, text="— OR —", font=ctk.CTkFont(size=12))
        or_label.grid(row=2, column=0, columnspan=3, pady=5)

        # File selection
        file_label = ctk.CTkLabel(deck_frame, text="Load .ydk file:", font=ctk.CTkFont(size=14))
        file_label.grid(row=3, column=0, padx=(15, 5), pady=5, sticky="w")

        # Inline container so file name and Browse button sit next to each other
        file_container = ctk.CTkFrame(deck_frame, fg_color="transparent")
        # size to contents and stick to the left so button sits just after filename
        file_container.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        file_container.grid_columnconfigure(0, weight=0)

        self.file_path_label = ctk.CTkLabel(file_container, text="No file selected",
                             font=ctk.CTkFont(size=12), text_color="gray")
        self.file_path_label.grid(row=0, column=0, sticky="w")

        browse_btn = ctk.CTkButton(file_container, text="Browse...", width=100,
                        command=self.browse_file)
        # small gap between filename and button
        # small 5px gap between filename and button
        browse_btn.grid(row=0, column=1, padx=(5, 0), sticky="w")



        # MIDDLE SECTION: Card Counts
        counts_frame = ctk.CTkFrame(self)
        counts_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
        # Create extra columns so we can center the inputs on wide screens
        for i in range(9):
            counts_frame.grid_columnconfigure(i, weight=0)
        counts_frame.grid_columnconfigure(0, weight=1)
        counts_frame.grid_columnconfigure(8, weight=1)

        # Instructions (centered under title)
        instr_label = ctk.CTkLabel(counts_frame,
                        text="Specify card counts:",
                        font=ctk.CTkFont(size=16, weight="bold"))
        instr_label.grid(row=0, column=0, columnspan=9, pady=(10, 5))

        desc_label = ctk.CTkLabel(counts_frame,
                       text="Bricks = cards you don't want to draw  |  Non-Engine = handtraps & board breakers  |  Engine = combo pieces",
                       font=ctk.CTkFont(size=12), text_color="gray")
        desc_label.grid(row=1, column=0, columnspan=9, pady=(0, 10))

        # Inputs row centered using inner columns 1..7
        # Brick count
        brick_label = ctk.CTkLabel(counts_frame, text="Bricks:", font=ctk.CTkFont(size=15))
        brick_label.grid(row=2, column=1, padx=(10, 5), pady=10)

        self.brick_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                        font=ctk.CTkFont(size=14))
        self.brick_entry.grid(row=2, column=2, padx=5, pady=10)
        self.brick_entry.insert(0, "0")

        # Non-engine count
        non_engine_label = ctk.CTkLabel(counts_frame, text="Non-Engine:", font=ctk.CTkFont(size=15))
        non_engine_label.grid(row=2, column=3, padx=(10, 5), pady=10)

        self.non_engine_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                             font=ctk.CTkFont(size=14))
        self.non_engine_entry.grid(row=2, column=4, padx=5, pady=10)
        self.non_engine_entry.insert(0, "0")

        # Engine count
        engine_label = ctk.CTkLabel(counts_frame, text="Engine:", font=ctk.CTkFont(size=15))
        engine_label.grid(row=2, column=5, padx=(10, 5), pady=10)

        self.engine_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                         font=ctk.CTkFont(size=14))
        self.engine_entry.grid(row=2, column=6, padx=(5, 5), pady=10)
        self.engine_entry.insert(0, "0")

        # Apply and Advanced buttons placed next to Engine input (column 7)
        buttons_frame = ctk.CTkFrame(counts_frame, fg_color="transparent")
        buttons_frame.grid(row=2, column=7, padx=(10, 20), pady=10)
        self.draw_btn = ctk.CTkButton(buttons_frame, text="Apply & Draw Hand", width=165,
                           command=self.apply_and_draw, state="disabled",
                           font=ctk.CTkFont(size=14, weight="bold"),
                           fg_color="green", hover_color="darkgreen")
        self.draw_btn.grid(row=0, column=0)
        self.advanced_btn = ctk.CTkButton(buttons_frame, text="Show Decklist", width=110,
                           command=self.open_advanced_view, state="disabled",
                           font=ctk.CTkFont(size=14, weight="bold"))
        self.advanced_btn.grid(row=0, column=1, padx=(10, 0))

        # Deck info label (below, left-aligned within centered area)
        self.deck_info_label = ctk.CTkLabel(counts_frame, text="No deck loaded",
                     font=ctk.CTkFont(size=13), text_color="orange")
        # Center the info label across the input area
        self.deck_info_label.grid(row=3, column=0, columnspan=9, pady=(0, 8))

        # BOTTOM SECTION: Results (use a horizontal PanedWindow so panels are resizable)
        # Theme background color for paned/window elements
        self.bg_color = "#242424"
        # Use a container with a thin draggable divider (clean thin line)
        container = ctk.CTkFrame(self, fg_color=self.bg_color)
        container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        # Allow container to expand vertically
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=0)  # Width set from the divider position
        container.grid_columnconfigure(1, weight=0, minsize=8)
        container.grid_columnconfigure(2, weight=1)


        # Left panel - Hand display (responsive)
        hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                      border_width=1, border_color="#3a3a3a")
        hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)
        # Fixed split: card images get 3/5 of the height, the text 2/5
        # (uniform keeps the ratio exact regardless of what each part requests)
        hand_frame.grid_rowconfigure(1, weight=3, uniform="hand_split")
        hand_frame.grid_rowconfigure(2, weight=2, uniform="hand_split")
        hand_frame.grid_columnconfigure(0, weight=1)

        # Header with title and compact Draw button
        header_frame = ctk.CTkFrame(hand_frame, fg_color="transparent")
        header_frame.grid(row=0, column=0, pady=(8, 4), padx=10, sticky='ew')
        header_frame.grid_columnconfigure(0, weight=1)
        header_frame.grid_columnconfigure(1, weight=0)

        hand_title = ctk.CTkLabel(header_frame, text="Test Hand",
               font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
        hand_title.grid(row=0, column=0, sticky='ew')

        # (Draw Again button removed — uses Apply & Draw Hand instead)


        cards_pane = tk.Frame(hand_frame, bg="#2b2b2b")
        cards_pane.grid(row=1, column=0, padx=10, pady=(6, 0), sticky="nsew")
        cards_pane.grid_rowconfigure(0, weight=1)
        cards_pane.grid_columnconfigure(0, weight=1)

        # Card images frame using Canvas (cards scale so the whole hand + 6th card always fit)
        card_canvas = tk.Canvas(cards_pane, bg="#23272b", highlightthickness=0, bd=0, relief="flat")
        card_canvas.grid(row=0, column=0, sticky="nsew")
        # Frame inside the canvas for card images (anchored at its centre so the hand is centred)
        self.cards_frame = tk.Frame(card_canvas, bg="#23272b")
        self.cards_frame_id = card_canvas.create_window((0, 0), window=self.cards_frame, anchor="center")

        def _on_canvas_configure(event):
            # Keep the hand centred now; rescale the cards once resizing pauses
            card_canvas.coords(self.cards_frame_id, event.width / 2, event.height / 2)
            self._schedule_hand_relayout()
        card_canvas.bind("<Configure>", _on_canvas_configure)

        # Text display for card names (responsive, with vertical scrollbar, styled for dark theme)
        text_frame = tk.Frame(hand_frame, bg="#181a1b")
        text_frame.grid(row=2, column=0, padx=10, pady=(8, 10), sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        self.hand_font = tkfont.Font(family="Consolas", size=self.HAND_FONT_MIN)
        self.hand_textbox = tk.Text(
            text_frame,
            font=self.hand_font,
            width=1,
            height=1,
            wrap="word",
            bg="#181a1b",
            fg="#c7c7c7",
            insertbackground="#c7c7c7",
            relief="flat",
            borderwidth=0,
            highlightthickness=0,
            selectbackground="#2b2b2b",
            selectforeground="#ffffff",
            padx=8,
            pady=6,
        )
        self.hand_textbox.grid(row=0, column=0, sticky="nsew")
        try:
            y_scroll = ctk.CTkScrollbar(text_frame, orientation="vertical", command=self.hand_textbox.yview)
            _lighten_scrollbar(y_scroll)
            y_scroll.grid(row=0, column=1, sticky="ns")
            try:
                y_scroll.configure(fg_color="#23272b", border_color="#23272b", corner_radius=6)
            except Exception:
                try:
                    y_scroll.configure(bg="#23272b")
                except Exception:
                    pass
        except Exception:
            y_scroll = tk.Scrollbar(text_frame, orient="vertical", command=self.hand_textbox.yview)
            y_scroll.grid(row=0, column=1, sticky="ns")
            try:
                y_scroll.configure(bg="#23272b", troughcolor="#23272b", activebackground="#23272b")
            except Exception:
                pass
        self.hand_textbox.configure(yscrollcommand=y_scroll.set)

        # Re-fit the text (font size, deck list columns) when the text area is resized
        self._hand_text_mode = "lines"
        self._hand_text_lines = ["Load a deck and click 'Apply & Draw Hand' to begin..."]
        self.hand_textbox.bind("<Configure>", lambda _e: self._schedule_hand_relayout())
        self._render_hand_text()

        # Draw again button moved to persistent footer (created below)

        # Thin divider between panels
        # Invisible divider (no visible line) but still acts as a draggable handle
        divider = tk.Frame(container, bg=self.bg_color, width=8, cursor="sb_h_double_arrow")
        divider.grid(row=0, column=1, sticky="ns", pady=6)

        # Right panel - Statistics
        stats_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                       border_width=1, border_color="#3a3a3a")
        stats_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)
        stats_frame.grid_rowconfigure(0, weight=0)
        stats_frame.grid_rowconfigure(1, weight=1)

        # Leave no persistent footer so the panels extend to the bottom of the window
        stats_frame.grid_columnconfigure(0, weight=1)

        stats_title = ctk.CTkLabel(stats_frame, text="Probabilities & Statistics",
                font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
        stats_title.grid(row=0, column=0, pady=(10, 5), sticky='ew')
        # Draggable divider behavior: store start positions on press, move by root-delta,
        # persist ratio on release, and adapt on container resize.
        self._divider_drag = {'dragging': False, 'start_x': 0, 'start_left': 0}
        self._left_ratio = 0.52

        try:
            ui_scale = ctk.ScalingTracker.get_window_scaling(self)
        except Exception:
            ui_scale = 1.0
        min_left, min_right = int(380 * ui_scale), int(320 * ui_scale)

        def _apply_left_width(left_w):
            """Set the hand panel width, keeping both panels above their minimum width."""
            if container.winfo_width() <= 1:
                return
            left_w = _clamp_left_width(left_w)
            # Only touch the grid when the width changes: re-applying it makes the
            # CTk frame fire <Configure> again, which would loop forever
            if int(container.grid_columnconfigure(0, "minsize")) != left_w:
                container.grid_columnconfigure(0, minsize=left_w)

        def _left_column_width():
            # Width of the whole column (panel + its padding), which is what minsize sets
            return container.grid_bbox(0, 0)[2]

        # While dragging, a greyed-out preview of both panels (no cards or text) is drawn at
        # the target size; the real panels are resized once on release. Re-laying out the
        # real panels (cards, text, CTk frames) on every motion event costs ~100ms each,
        # which made the drag stutter, while redrawing a few preview shapes is instant.
        drag_preview = tk.Canvas(container, bg=self.bg_color, highlightthickness=0, bd=0,
                                 cursor="sb_h_double_arrow")
        preview_radius = int(12 * ui_scale)

        def _clamp_left_width(left_w):
            total_w = container.winfo_width()
            max_left = max(min_left, total_w - min_right - divider.winfo_width())
            return int(max(min_left, min(left_w, max_left)))

        def _box(widget):
            """Widget's (x, y, width, height) relative to the container."""
            return (widget.winfo_rootx() - container.winfo_rootx(),
                    widget.winfo_rooty() - container.winfo_rooty(),
                    widget.winfo_width(), widget.winfo_height())

        def _rounded_rect(x1, y1, x2, y2, r, **kwargs):
            r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
            points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                      x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
            drag_preview.create_polygon(points, smooth=True, **kwargs)

        def _start_preview():
            # Snapshot the current panel layout; the preview stretches it horizontally
            self._divider_drag['layout'] = {
                'hand': _box(hand_frame),
                'hand_parts': [_box(cards_pane), _box(text_frame)],
                'stats': _box(stats_frame),
                'stats_parts': [_box(self.stats_textbox)],
            }
            drag_preview.place(x=0, y=0, relwidth=1, relheight=1)
            tk.Misc.tkraise(drag_preview)  # Canvas.lift() raises canvas items, not the widget

        def _draw_preview(left_w):
            layout = self._divider_drag['layout']
            delta = left_w - self._divider_drag['start_left']
            drag_preview.delete("all")
            panel = dict(fill="#2a2a2a", outline="#4a4a4a", width=1)
            part = dict(fill="#353535", outline="")

            # Hand panel grows/shrinks with the divider; its parts stretch with it
            x, y, w, h = layout['hand']
            _rounded_rect(x, y, x + w + delta, y + h, preview_radius, **panel)
            for px, py, pw, ph in layout['hand_parts']:
                drag_preview.create_rectangle(px, py, px + pw + delta, py + ph, **part)

            # Statistics panel moves with the divider and takes the remaining width
            x, y, w, h = layout['stats']
            _rounded_rect(x + delta, y, x + w, y + h, preview_radius, **panel)
            for px, py, pw, ph in layout['stats_parts']:
                drag_preview.create_rectangle(px + delta, py, px + pw, py + ph, **part)

        def _on_divider_press(event):
            self._divider_drag['dragging'] = True
            self._divider_drag['start_x'] = event.x_root
            self._divider_drag['start_left'] = _left_column_width()
            self._divider_drag['target'] = _left_column_width()
            _start_preview()
            _draw_preview(self._divider_drag['target'])

        def _on_divider_release(event):
            if not self._divider_drag.get('dragging'):
                return
            self._divider_drag['dragging'] = False
            drag_preview.place_forget()
            drag_preview.delete("all")
            target = self._divider_drag['target']
            _apply_left_width(target)
            total_w = container.winfo_width()
            if total_w > 1:
                # Remember the split as a ratio so it's kept when the window is resized
                self._left_ratio = max(0.1, min(0.9, target / total_w))

        def _on_divider_motion(event):
            if self._divider_drag.get('dragging'):
                dx = event.x_root - self._divider_drag['start_x']
                self._divider_drag['target'] = _clamp_left_width(self._divider_drag['start_left'] + dx)
                _draw_preview(self._divider_drag['target'])

        divider.bind("<ButtonPress-1>", _on_divider_press)
        divider.bind("<ButtonRelease-1>", _on_divider_release)
        divider.bind("<B1-Motion>", _on_divider_motion)

        def _on_container_configure(event):
            # Re-apply the split ratio only when the container's width actually changed
            width = container.winfo_width()
            if not self._divider_drag.get('dragging') and width != self._divider_drag.get('last_total'):
                self._divider_drag['last_total'] = width
                _apply_left_width(width * self._left_ratio)

        container.bind('<Configure>', _on_container_configure)

        self.stats_textbox = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(family="Consolas", size=12),
                             width=200)
        for scrollbar in (getattr(self.stats_textbox, "_y_scrollbar", None),
                          getattr(self.stats_textbox, "_x_scrollbar", None)):
            if scrollbar is not None:
                _lighten_scrollbar(scrollbar)
        self.stats_textbox.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
        self.stats_textbox.insert("1.0", "Statistics will appear here after drawing a hand...")
        self.stats_textbox.configure(state="disabled")

    def load_from_ydke(self):
        """Load deck from ydke code"""
        ydke_code = self.ydke_entry.get().strip()
        if not ydke_code:
            messagebox.showwarning("Warning", "Please enter a ydke code.")
            return

        if not ydke_code.startswith("ydke://"):
            messagebox.showerror("Error", "Invalid format. Code must start with 'ydke://'")
            return

        self.load_deck(ydke_code)

    def browse_file(self):
        """Browse for a .ydk file"""
        # Use {installed_path}\decklists
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        decklists_path = os.path.join(base_path, "decklists")
        if not os.path.exists(decklists_path):
            os.makedirs(decklists_path, exist_ok=True)
        initial_dir = decklists_path

        filepath = filedialog.askopenfilename(
            title="Select YDK File",
            initialdir=initial_dir,
            filetypes=[("YDK files", "*.ydk"), ("All files", "*.*")]
        )

        if filepath:
            self.file_path_label.configure(text=os.path.basename(filepath))
            with open(filepath, 'r') as f:
                ydk_content = f.read()
            self.load_deck(ydk_content)

    def open_decklists_folder(self):
        """Open the decklists folder in file explorer"""
        if getattr(sys, 'frozen', False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        decklists_path = os.path.join(base_path, "decklists")
        if not os.path.exists(decklists_path):
            os.makedirs(decklists_path, exist_ok=True)
            messagebox.showinfo("Info", f"Created decklists folder at:\n{decklists_path}\n\nPlace your .ydk files here!")
        os.startfile(decklists_path)

    def load_deck(self, ydk_code: str):
        """Load deck from YDK file or ydke URL"""
        self.deck.clear_deck()
        self.card_pool = []
        self._set_manual_tags(None)
        ydk_code = ydk_code.strip()

        try:
            if ydk_code.startswith("ydke://"):
                main_ids, _, _ = parse_ydke_url(ydk_code)
                card_ids = main_ids
                if not card_ids:
                    messagebox.showerror("Error", "No main deck cards found in ydke code.")
                    return
            else:
                # Parse YDK file format
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
                    messagebox.showerror("Error", "No main deck cards found.")
                    return

            # Fetch card names
            self.deck_info_label.configure(text="Loading card names from API...", text_color="yellow")
            self.update()

            card_database = fetch_multiple_card_names(list(set(card_ids)), verbose=False)

            # Count cards and map names to IDs
            card_counts: Dict[str, int] = {}
            for card_id in card_ids:
                card_name = card_database.get(card_id, f"Card_{card_id}")
                card_counts[card_name] = card_counts.get(card_name, 0) + 1
                # Store the card_id for this card_name (for image lookup)
                self.card_id_map[card_name] = card_id

            # Add to deck
            for card_name, copies in card_counts.items():
                if copies > self.deck.MAX_COPIES:
                    messagebox.showerror("Error", f"'{card_name}' has {copies} copies. Max is {self.deck.MAX_COPIES}.")
                    self.deck.clear_deck()
                    return
                self.deck.add_card(card_name, copies)

            self.deck_loaded = True
            deck_size = self.deck.get_deck_size()
            self.deck_info_label.configure(
                text=f"✓ Deck loaded: {deck_size} cards",
                text_color="lightgreen"
            )
            self.draw_btn.configure(state="normal")
            self.advanced_btn.configure(state="normal")

            # Show deck list in hand textbox
            self._show_deck_list()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck:\n{str(e)}")
            self.deck_info_label.configure(text="Failed to load deck", text_color="red")

    # Font size range for the text under the cards
    HAND_FONT_MIN = 14
    HAND_FONT_MAX = 24

    def _show_deck_list(self):
        """Show the loaded deck in the hand textbox."""
        self._hand_text_mode = "deck"
        self._render_hand_text()

    def _show_hand_lines(self, lines: List[str]):
        """Show plain lines of text (e.g. the drawn hand) in the hand textbox."""
        self._hand_text_mode = "lines"
        self._hand_text_lines = lines
        self._render_hand_text()

    def _deck_list_lines(self, font: tkfont.Font, avail_w: int) -> List[str]:
        """Deck list laid out in as many columns as fit avail_w at the given font."""
        entries = [f"{copies}x {card_name}" for card_name, copies in self.deck.cards.items()]
        if not entries:
            return []
        line_chars = max(1, avail_w // max(1, font.measure("0")))

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
                + ["", rule, f"Total: {self.deck.get_deck_size()} cards", "",
                   "Set card counts and click 'Apply & Draw Hand'"])

    def _render_hand_text(self):
        """Render the hand textbox at the largest font size (HAND_FONT_MAX..MIN) that fits.

        If even the minimum size doesn't fit, it stays at the minimum and the box scrolls.
        """
        tb = self.hand_textbox
        avail_w = tb.winfo_width() - 2 * int(tb.cget("padx")) - 4
        avail_h = tb.winfo_height() - 2 * int(tb.cget("pady")) - 4

        lines: List[str] = []
        size = self.HAND_FONT_MIN
        for size in range(self.HAND_FONT_MAX, self.HAND_FONT_MIN - 1, -1):
            font = tkfont.Font(family="Consolas", size=size)
            if self._hand_text_mode == "deck":
                lines = self._deck_list_lines(font, avail_w)
            else:
                lines = self._hand_text_lines
            fits_h = len(lines) * font.metrics("linespace") <= avail_h
            fits_w = all(font.measure(line) <= avail_w for line in lines)
            if fits_h and fits_w:
                break

        # Skip if nothing changed: re-applying the font makes Tk re-measure the widget,
        # which fires <Configure> and would trigger another relayout
        rendered = (size, self._hand_text_mode, tuple(lines))
        if rendered == getattr(self, "_hand_text_rendered", None):
            return
        self._hand_text_rendered = rendered
        if int(self.hand_font.cget("size")) != size:
            self.hand_font.configure(size=size)
        tb.configure(state="normal", wrap="none" if self._hand_text_mode == "deck" else "word")
        tb.delete("1.0", "end")
        tb.insert("1.0", "\n".join(lines))
        tb.configure(state="disabled")

    def apply_and_draw(self):
        """Apply card counts and draw a hand"""
        if not self.deck_loaded:
            messagebox.showwarning("Warning", "Please load a deck first.")
            return

        if self.manual_tags is not None:
            # Categories come from the tags set in the Advanced view
            self.card_pool = list(zip(self.deck.get_deck_list(), self.manual_tags))
            self._sync_category_sets()
            self.draw_hand()
            return

        try:
            brick_count = int(self.brick_entry.get() or 0)
            non_engine_count = int(self.non_engine_entry.get() or 0)
            engine_count = int(self.engine_entry.get() or 0)
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

        # Assign categories per copy, in deck-list order, so the entered counts are
        # met exactly even when a card's copies span two categories
        categories = (["brick"] * brick_count + ["non_engine"] * non_engine_count
                      + ["engine"] * engine_count)
        deck_list = self.deck.get_deck_list()
        categories += [""] * (len(deck_list) - len(categories))
        self.card_pool = list(zip(deck_list, categories))
        self._sync_category_sets()

        # draw_again button removed; rely on the main Apply & Draw Hand button
        self.draw_hand()

    def _sync_category_sets(self):
        """Mirror the per-copy card pool into the deck's per-name category sets."""
        self.deck.engine_cards.clear()
        self.deck.non_engine_cards.clear()
        self.deck.brick_cards.clear()
        category_sets = {"brick": self.deck.brick_cards, "non_engine": self.deck.non_engine_cards,
                         "engine": self.deck.engine_cards}
        for card_name, category in self.card_pool:
            if category:
                category_sets[category].add(card_name)

    def _set_manual_tags(self, tags: Optional[List[str]]):
        """Switch between Advanced-view tags (count boxes locked) and typed counts."""
        self.manual_tags = tags if tags and any(tags) else None
        entries = {"brick": self.brick_entry, "non_engine": self.non_engine_entry,
                   "engine": self.engine_entry}
        for key, entry in entries.items():
            entry.configure(state="normal")
            if self.manual_tags is not None:
                entry.delete(0, "end")
                entry.insert(0, str(self.manual_tags.count(key)))
                entry.configure(state="disabled")

        if self.deck_loaded:
            deck_size = self.deck.get_deck_size()
            text = f"✓ Deck loaded: {deck_size} cards"
            if self.manual_tags is not None:
                text += "  |  Using tags from Advanced view"
                untagged = self.manual_tags.count("")
                if untagged:
                    text += f" ({untagged} untagged)"
            self.deck_info_label.configure(text=text, text_color="lightgreen")

    def open_advanced_view(self):
        """Overlay the visual decklist for tagging cards on top of the main view."""
        if not self.deck_loaded or self.advanced_view is not None:
            return

        deck_list = self.deck.get_deck_list()
        if self.manual_tags is not None:
            tags = self.manual_tags
        else:
            # Start from the current categories so typed counts carry over
            pool = self.card_pool or self._pool_from_category_sets()
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
            load_image=self._download_image,
            on_done=self._close_advanced_view,
        )
        self.advanced_view.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

    def _close_advanced_view(self, tags: List[str]):
        """Remove the overlay and apply the tags from the Advanced view."""
        if self.advanced_view is not None:
            self._advanced_overlay.destroy()
            self.advanced_view = None

        self._set_manual_tags(tags)
        if self.manual_tags is not None:
            self.card_pool = list(zip(self.deck.get_deck_list(), self.manual_tags))
            self._sync_category_sets()

    def _pool_from_category_sets(self) -> List[Tuple[str, str]]:
        """Build a per-copy card pool from the deck's per-name category sets."""
        pool = []
        for card_name, copies in self.deck.cards.items():
            if card_name in self.deck.brick_cards:
                category = "brick"
            elif card_name in self.deck.non_engine_cards:
                category = "non_engine"
            elif card_name in self.deck.engine_cards:
                category = "engine"
            else:
                category = ""
            pool.extend([(card_name, category)] * copies)
        return pool

    def draw_hand(self):
        """Draw a test hand and display results"""
        # Draw hand
        pool = list(self.card_pool or self._pool_from_category_sets())
        random.shuffle(pool)
        self.current_hand = [name for name, _ in pool[:5]]
        self.current_hand_categories = [category for _, category in pool[:5]]

        # Clear previous card images
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_image_labels.clear()
        self.card_text_labels.clear()
        thumb_w, thumb_h = self._hand_thumb

        # Display card images
        if PIL_AVAILABLE:
            for i, card in enumerate(self.current_hand):
                image_urls = get_card_image_urls(self.card_id_map.get(card, ''))

                # Create frame for each card (padding around thumbnail)
                card_frame = ctk.CTkFrame(self.cards_frame, fg_color=self.bg_color, corner_radius=6)
                card_frame.grid(row=0, column=i, padx=4, pady=6)
                self.load_and_display_image(image_urls, card_frame, card, target_size=(thumb_w, thumb_h))

        # 6th card simulation (next card of the shuffled deck)
        sixth_card = None
        if len(pool) > 5:
            sixth_card = pool[5][0]

            # Show 6th card image
            if PIL_AVAILABLE:
                image_urls = get_card_image_urls(self.card_id_map.get(sixth_card, ''))

                # Separator
                sep_label = ctk.CTkLabel(self.cards_frame, text="→", font=ctk.CTkFont(size=26))
                sep_label.grid(row=0, column=5, padx=6)

                card_frame = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
                card_frame.grid(row=0, column=6, padx=4, pady=6)
                self.load_and_display_image(image_urls, card_frame, sixth_card, is_sixth=True, target_size=(thumb_w, thumb_h))

        # Scale the cards so all of them (including the 6th) fit the card area
        self._hand_slots = len(self.current_hand) + (1 if sixth_card else 0)
        self._fit_hand()

        # Display hand text
        lines = ["OPENING HAND:"] + [f"  {i}. {card}" for i, card in enumerate(self.current_hand, 1)]
        if sixth_card:
            lines += ["", "6TH CARD (Going Second):", f"  → {sixth_card}"]
        self._show_hand_lines(lines)

        # Calculate and display statistics
        self.display_statistics()

    def _download_image(self, url: str) -> 'Image.Image':
        """Download an image (or reuse a cached one) as a PIL image. Safe to call off the Tk thread."""
        orig = self.orig_images.get(url)
        if orig is None:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()
            # Open original PIL image and store it for future resizes
            orig = Image.open(BytesIO(image_data)).convert("RGBA")
            self.orig_images[url] = orig
        return orig

    def _get_image(self, url: str, tw: int, th: int):
        """Download (or reuse) an image and return it resized as a PhotoImage."""
        # Use cache key that includes size to avoid mismatched thumbnail sizes
        cache_key = f"{url}|{tw}x{th}"
        if cache_key in self.image_cache:
            return self.image_cache[cache_key]

        orig = self._download_image(url)
        img_tk = ImageTk.PhotoImage(orig.resize((tw, th), Image.Resampling.LANCZOS))
        # Drop other sizes of this image so resizing the window doesn't grow the cache
        prefix = f"{url}|"
        for key in [k for k in self.image_cache if k.startswith(prefix)]:
            del self.image_cache[key]
        self.image_cache[cache_key] = img_tk
        return img_tk

    def load_and_display_image(self, urls: List[str], parent_frame, card_name: str, is_sixth: bool = False, target_size: tuple = None):
        """Display the first image that loads from urls; otherwise show the card name."""
        if target_size and isinstance(target_size, tuple) and len(target_size) == 2:
            tw, th = target_size
        else:
            tw, th = (140, 205)

        for url in urls:
            try:
                img_tk = self._get_image(url, tw, th)
            except Exception:
                logging.warning("Failed to load image for %s from %s", card_name, url)
                continue

            # corner_radius=0: CTkLabel pads its content by the corner radius, which
            # would add empty space around every card
            label = ctk.CTkLabel(parent_frame, image=img_tk, text="", corner_radius=0)
            label.image = img_tk  # Keep reference
            # Tag label with source url for responsive resizing
            label._image_url = url
            label.grid(row=0, column=0)
            self.card_image_labels.append(label)
            return

        # No image source worked: show the card name instead
        label = ctk.CTkLabel(parent_frame, text=card_name, fg_color="gray30", corner_radius=5)
        self._size_text_label(label, tw, th)
        label.grid(row=0, column=0)
        self.card_text_labels.append(label)

    def _size_text_label(self, label, tw: int, th: int):
        """Size a name placeholder to tw x th pixels (CTk sizes are logical, so unscale)."""
        try:
            scale = ctk.ScalingTracker.get_widget_scaling(label)
        except Exception:
            scale = 1.0
        label.configure(width=max(1, int(tw / scale)), height=max(1, int(th / scale)),
                        wraplength=max(1, int((tw - 12) / scale)))

    def draw_again(self):
        """Draw another hand"""
        self.draw_hand()

    def _fit_hand(self):
        """Size the hand's thumbnails so every card (including the 6th) fits the card area."""
        canvas = self.cards_frame.master
        canvas_w, canvas_h = canvas.winfo_width(), canvas.winfo_height()
        if self._hand_slots == 0 or canvas_w <= 1 or canvas_h <= 1:
            return

        # The space taken by padding, the arrow and card frames is measured from the
        # current layout (it doesn't depend on card size); the cards get the rest
        self.cards_frame.update_idletasks()
        thumb_w, thumb_h = self._hand_thumb
        extra_w = max(0, self.cards_frame.winfo_reqwidth() - self._hand_slots * thumb_w)
        extra_h = max(0, self.cards_frame.winfo_reqheight() - thumb_h)
        by_width = (canvas_w - extra_w) / self._hand_slots * 205 / 140
        by_height = canvas_h - extra_h
        new_h = max(20, int(min(by_width, by_height)))
        new_size = (int(new_h * 140 / 205), new_h)
        if new_size != self._hand_thumb:
            self._resize_thumbnails(*new_size)

    def _schedule_hand_relayout(self):
        """Refit cards and text at most every ~30ms while resizing (smooth, no flicker).

        Resize events arrive far faster than that; batching them means one refit per
        frame, and the pending refit always sees the latest size.
        """
        if self._relayout_job is None:
            self._relayout_job = self.after(30, self._hand_relayout)

    def _hand_relayout(self):
        self._relayout_job = None
        try:
            self._fit_hand()
            self._render_hand_text()
        except Exception:
            logging.exception("Failed to refit the test hand")

    def _resize_thumbnails(self, thumb_w: int, thumb_h: int):
        """Resize all displayed hand thumbnails (and name placeholders) to thumb_w x thumb_h."""
        self._hand_thumb = (thumb_w, thumb_h)

        # Resize each labeled image if we have the original
        for lbl in list(self.card_image_labels):
            url = getattr(lbl, '_image_url', None)
            if not url:
                continue
            try:
                img_tk = self._get_image(url, thumb_w, thumb_h)
                lbl.configure(image=img_tk)
                lbl.image = img_tk
            except Exception:
                continue

        for lbl in self.card_text_labels:
            self._size_text_label(lbl, thumb_w, thumb_h)

    def display_statistics(self):
        """Calculate and display probability statistics"""
        deck_size = self.deck.get_deck_size()
        pool = self.card_pool or self._pool_from_category_sets()
        engine_count = sum(1 for _, category in pool if category == "engine")
        non_engine_count = sum(1 for _, category in pool if category == "non_engine")
        brick_count = sum(1 for _, category in pool if category == "brick")
        hand_size = 5

        self.stats_textbox.configure(state="normal")
        self.stats_textbox.delete("1.0", "end")

        # Header
        self.stats_textbox.insert("end", "OPENING HAND PROBABILITIES\n")
        self.stats_textbox.insert("end", "=" * 50 + "\n\n")

        # Deck composition
        self.stats_textbox.insert("end", f"Deck: {deck_size} cards\n")
        self.stats_textbox.insert("end", f"  Engine: {engine_count} | Non-Engine: {non_engine_count} | Bricks: {brick_count}\n\n")

        # Engine x Non-Engine Matrix
        self.stats_textbox.insert("end", "Engine x Non-Engine Matrix:\n")
        self.stats_textbox.insert("end", "(E = Engine, NE = Non-Engine/Handtraps)\n\n")

        # Header row
        self.stats_textbox.insert("end", "       ")
        for ne in range(6):
            self.stats_textbox.insert("end", f" {ne}NE   ")
        self.stats_textbox.insert("end", "\n")

        # Matrix rows
        for eng in range(6):
            self.stats_textbox.insert("end", f"  {eng}E  ")
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
                                self.stats_textbox.insert("end", f"{prob:5.1f}% ")
                            else:
                                self.stats_textbox.insert("end", "   -  ")
                        else:
                            self.stats_textbox.insert("end", "   -  ")
                    else:
                        self.stats_textbox.insert("end", "   -  ")
                else:
                    self.stats_textbox.insert("end", "   -  ")
            self.stats_textbox.insert("end", "\n")

        # At Least Probabilities
        self.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
        self.stats_textbox.insert("end", "'At Least' Probabilities:\n")
        self.stats_textbox.insert("end", "(Chance of drawing X OR MORE)\n\n")

        for i in [1, 2]:
            eng_prob = probability_at_least(deck_size, engine_count, hand_size, i) * 100
            self.stats_textbox.insert("end", f"  At least {i} engine:      {eng_prob:5.1f}%\n")
        for i in [1, 2]:
            ne_prob = probability_at_least(deck_size, non_engine_count, hand_size, i) * 100
            self.stats_textbox.insert("end", f"  At least {i} non-engine:  {ne_prob:5.1f}%\n")
        for i in [1, 2]:
            br_prob = probability_at_least(deck_size, brick_count, hand_size, i) * 100
            self.stats_textbox.insert("end", f"  At least {i} brick:       {br_prob:5.1f}%\n")

        # Brick Analysis
        self.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
        self.stats_textbox.insert("end", "BRICK ANALYSIS\n\n")

        open_brick = probability_at_least(deck_size, brick_count, hand_size, 1) * 100
        no_brick_open = hypergeometric_probability(deck_size, brick_count, hand_size, 0)
        draw_brick_6th = (brick_count / (deck_size - 5)) * 100 if deck_size > 5 else 0
        brick_by_turn1 = open_brick + (no_brick_open * brick_count / (deck_size - 5) * 100) if deck_size > 5 else open_brick

        self.stats_textbox.insert("end", f"  Open with brick (5 cards):     {open_brick:5.1f}%\n")
        self.stats_textbox.insert("end", f"  Draw brick 6th (if none open): {draw_brick_6th:5.1f}%\n")
        self.stats_textbox.insert("end", f"  See brick by turn 1 (6 cards): {brick_by_turn1:5.1f}%\n")

        # 6th Card Odds
        self.stats_textbox.insert("end", "\n" + "-" * 50 + "\n")
        self.stats_textbox.insert("end", "6TH CARD ODDS (based on current hand)\n\n")

        remaining_deck = deck_size - 5
        engine_in_hand = self.current_hand_categories.count("engine")
        non_engine_in_hand = self.current_hand_categories.count("non_engine")
        brick_in_hand = self.current_hand_categories.count("brick")

        engine_remaining = engine_count - engine_in_hand
        non_engine_remaining = non_engine_count - non_engine_in_hand
        brick_remaining = brick_count - brick_in_hand

        self.stats_textbox.insert("end", f"  Engine:      {engine_remaining/remaining_deck*100:5.1f}% ({engine_remaining}/{remaining_deck})\n")
        self.stats_textbox.insert("end", f"  Non-Engine:  {non_engine_remaining/remaining_deck*100:5.1f}% ({non_engine_remaining}/{remaining_deck})\n")
        self.stats_textbox.insert("end", f"  Brick:       {brick_remaining/remaining_deck*100:5.1f}% ({brick_remaining}/{remaining_deck})\n")

        self.stats_textbox.configure(state="disabled")


def main():
    app = YuGiOhHandSimulator()
    app.mainloop()


if __name__ == "__main__":
    main()
