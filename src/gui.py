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
from io import BytesIO
from typing import Dict, List

import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk
import logging

# Delegate image loading/resizing to a smaller module
try:
    import gui_components.image_manager as imgmgr
    import gui_components.deck_manager as deckmgr
    import gui_components.stats_manager as statsmgr
except Exception:
    # When running `src/gui.py` directly, package imports may fail.
    # Ensure the `src` directory is on sys.path and fall back to top-level modules.
    base_dir = os.path.dirname(__file__)
    if base_dir not in sys.path:
        sys.path.insert(0, base_dir)
    try:
        import gui_components.image_manager as imgmgr
        import gui_components.deck_manager as deckmgr
        import gui_components.stats_manager as statsmgr
    except Exception:
        import importlib
        # Final fallback: try to import top-level compatibility modules if present.
        try:
            imgmgr = importlib.import_module("image_manager")
        except Exception:
            imgmgr = importlib.import_module("gui_components.image_manager")
        try:
            deckmgr = importlib.import_module("deck_manager")
        except Exception:
            deckmgr = importlib.import_module("gui_components.deck_manager")
        try:
            statsmgr = importlib.import_module("stats_manager")
        except Exception:
            statsmgr = importlib.import_module("gui_components.stats_manager")

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
    get_image_cache
)



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
        self.geometry("1024x768")
        self.minsize(1100, 800)

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
        self.card_id_map: Dict[str, str] = {}  # card_name -> card_id
        self.image_cache: Dict[str, ImageTk.PhotoImage] = {}  # Cache loaded images (keyed by url|WxH)
        self.orig_images: Dict[str, 'Image.Image'] = {}  # Store original PIL images by URL
        self.card_image_labels = []  # Store image label references

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        """Create all UI components"""

        # Main container with grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # TOP SECTION: Deck Loading (moved to gui_components.header_manager)
        import gui_components.header_manager as headermgr
        headermgr.create_top_section(self)



        # MIDDLE SECTION: Card Counts (moved to gui_components.counts_manager)
        import gui_components.counts_manager as countsmgr
        countsmgr.create_counts_section(self)

        # BOTTOM SECTION: Results (use a horizontal PanedWindow so panels are resizable)
        # Theme background color for paned/window elements
        self.bg_color = "#242424"
        # Use a container with a thin draggable divider (clean thin line)
        container = ctk.CTkFrame(self, fg_color=self.bg_color)
        container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
        self.grid_rowconfigure(2, weight=1)
        # Allow container to expand vertically
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0, minsize=8)
        container.grid_columnconfigure(2, weight=1)


        # Left panel - Hand display (responsive)
        hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                      border_width=1, border_color="#3a3a3a")
        hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)
        hand_frame.grid_rowconfigure(1, weight=1)  # Card images area expands
        hand_frame.grid_rowconfigure(2, weight=0)  # Horizontal scrollbar (fixed size)
        hand_frame.grid_rowconfigure(3, weight=2)  # Text area expands more
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


        # Card images frame with horizontal scrollbar using Canvas (responsive)
        card_canvas = tk.Canvas(hand_frame, bg="#23272b", highlightthickness=0, bd=0, relief="flat")
        card_canvas.grid(row=1, column=0, padx=10, pady=(6, 0), sticky="nsew")
        # Frame inside the canvas for card images
        self.cards_frame = tk.Frame(card_canvas, bg="#23272b")
        self.cards_frame_id = card_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        def _on_frame_configure(event):
            card_canvas.configure(scrollregion=card_canvas.bbox("all"))
        self.cards_frame.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(event):
            # Make the canvas height fill the available space
            canvas_height = event.height
            card_canvas.itemconfig(self.cards_frame_id, height=canvas_height)
            # Update thumbnails to match new canvas height so they scale responsively
            try:
                self._resize_thumbnails(canvas_height)
            except Exception:
                pass
        card_canvas.bind("<Configure>", _on_canvas_configure)

        # Horizontal scrollbar between images and text (styled to match CTk theme)
        try:
            h_scroll = ctk.CTkScrollbar(hand_frame, orientation="horizontal", command=card_canvas.xview)
            h_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 0))
            # Ensure the scrollbar background/trough matches the card canvas so it isn't white
            try:
                # preferred CTk styling
                h_scroll.configure(fg_color="#23272b")
                h_scroll.configure(border_color="#23272b")
                h_scroll.configure(corner_radius=6)
            except Exception:
                # best-effort: set underlying tk widget colors if available
                try:
                    h_scroll.configure(bg="#23272b")
                except Exception:
                    pass
            card_canvas.configure(xscrollcommand=h_scroll.set)
        except Exception:
            # Fallback to native Tk scrollbar if CTkScrollbar is unavailable
            h_scroll = tk.Scrollbar(hand_frame, orient="horizontal", command=card_canvas.xview)
            h_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 0))
            try:
                h_scroll.configure(bg="#23272b", troughcolor="#23272b", activebackground="#23272b")
            except Exception:
                pass
            card_canvas.configure(xscrollcommand=h_scroll.set)

        # Text display for card names (responsive, with vertical scrollbar, styled for dark theme)
        text_frame = tk.Frame(hand_frame, bg="#181a1b")
        text_frame.grid(row=3, column=0, padx=10, pady=(6, 10), sticky="nsew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)
        self.hand_textbox = tk.Text(
            text_frame,
            font=("Consolas", 10),
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
        self.hand_textbox.insert("1.0", "Load a deck and click 'Apply & Draw Hand' to begin...")
        self.hand_textbox.configure(state="disabled")

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

        def _on_divider_press(event):
            self._divider_drag['dragging'] = True
            self._divider_drag['start_x'] = event.x_root
            self._divider_drag['start_left'] = hand_frame.winfo_width()

        def _on_divider_release(event):
            self._divider_drag['dragging'] = False
            try:
                total_w = container.winfo_width() or (self.winfo_width() or 1200)
                left_w = hand_frame.winfo_width()
                self._left_ratio = max(0.1, min(0.9, left_w / total_w))
            except Exception:
                pass

        def _on_divider_motion(event):
            if not self._divider_drag.get('dragging'):
                return
            try:
                dx = event.x_root - self._divider_drag['start_x']
                new_left = self._divider_drag['start_left'] + dx
                total_w = container.winfo_width() or (self.winfo_width() or 1200)
                min_left = 320
                max_left = max(min_left, total_w - 320 - divider.winfo_width())
                new_left = max(min_left, min(new_left, max_left))
                container.grid_columnconfigure(0, minsize=int(new_left))
            except Exception:
                pass

        divider.bind("<ButtonPress-1>", _on_divider_press)
        divider.bind("<ButtonRelease-1>", _on_divider_release)
        divider.bind("<B1-Motion>", _on_divider_motion)

        # Set initial left panel width to ~52% of window and bind resize handler
        try:
            self.update_idletasks()
            total_w = container.winfo_width() or self.winfo_width() or 1400
            container.grid_columnconfigure(0, minsize=int(total_w * self._left_ratio))
        except Exception:
            pass

        def _on_container_configure(event):
            try:
                total_w = container.winfo_width() or (self.winfo_width() or 1200)
                new_left = int(total_w * self._left_ratio)
                new_left = max(320, min(new_left, max(320, total_w - 320 - divider.winfo_width())))
                container.grid_columnconfigure(0, minsize=new_left)
            except Exception:
                pass

        container.bind('<Configure>', _on_container_configure)

        self.stats_textbox = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(family="Consolas", size=12),
                             width=560)
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
        """Browse for a .ydk file (delegated to deck manager)"""
        deckmgr.browse_file(self)

    def open_decklists_folder(self):
        """Open the decklists folder in file explorer (delegated)"""
        deckmgr.open_decklists_folder(self)

    def load_deck(self, ydk_code: str):
        """Load deck from YDK file or ydke URL (delegated)"""
        deckmgr.load_deck(self, ydk_code)

    def apply_and_draw(self):
        """Apply card counts and draw a hand"""
        if not self.deck_loaded:
            messagebox.showwarning("Warning", "Please load a deck first.")
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

        # Assign categories
        card_list = list(self.deck.cards.keys())
        self.deck.engine_cards.clear()
        self.deck.non_engine_cards.clear()
        self.deck.brick_cards.clear()

        remaining = brick_count
        for card_name in card_list:
            if remaining <= 0:
                break
            copies = self.deck.cards[card_name]
            if copies <= remaining:
                self.deck.brick_cards.add(card_name)
            remaining -= copies

        remaining = non_engine_count
        for card_name in card_list:
            if remaining <= 0:
                break
            if card_name in self.deck.brick_cards:
                continue
            copies = self.deck.cards[card_name]
            if copies <= remaining:
                self.deck.non_engine_cards.add(card_name)
            remaining -= copies

        remaining = engine_count
        for card_name in card_list:
            if remaining <= 0:
                break
            if card_name in self.deck.brick_cards or card_name in self.deck.non_engine_cards:
                continue
            copies = self.deck.cards[card_name]
            if copies <= remaining:
                self.deck.engine_cards.add(card_name)
            remaining -= copies

        # draw_again button removed; rely on the main Apply & Draw Hand button
        self.draw_hand()

    def draw_hand(self):
        """Draw a test hand and display results"""
        # Draw hand
        full_deck = self.deck.get_deck_list()
        random.shuffle(full_deck)
        self.current_hand = full_deck[:5]

        # Clear previous card images
        for widget in self.cards_frame.winfo_children():
            widget.destroy()
        self.card_image_labels.clear()

        # Display card images
        if PIL_AVAILABLE:
            image_cache = get_image_cache()
            for i, card in enumerate(self.current_hand):
                card_id = self.card_id_map.get(card, '')
                image_url = image_cache.get(card_id, '')

                # Create frame for each card (padding around thumbnail)
                card_frame = ctk.CTkFrame(self.cards_frame, fg_color=self.bg_color, corner_radius=6)
                card_frame.grid(row=0, column=i, padx=8, pady=6)

                # Compute responsive thumbnail size based on canvas height
                try:
                    canvas = self.cards_frame.master  # the Canvas containing cards_frame
                    canvas_h = canvas.winfo_height() or 205
                    # leave some padding; clamp between 100 and 205
                    thumb_h = max(100, min(205, canvas_h - 30))
                    thumb_w = int(thumb_h * (140 / 205))
                except Exception:
                    thumb_w, thumb_h = 140, 205

                if image_url:
                    self.load_and_display_image(image_url, card_frame, card, target_size=(thumb_w, thumb_h))
                else:
                    # Fallback to text label sized to match thumbnails
                    label = ctk.CTkLabel(card_frame, text=card[:15], width=thumb_w, height=thumb_h,
                                         fg_color="gray30", corner_radius=5)
                    label.grid(row=0, column=0)

        # 6th card simulation
        temp_deck = full_deck.copy()
        for card in self.current_hand:
            if card in temp_deck:
                temp_deck.remove(card)

        sixth_card = None
        if temp_deck:
            sixth_card = random.choice(temp_deck)

            # Show 6th card image
            if PIL_AVAILABLE:
                image_cache = get_image_cache()
                card_id = self.card_id_map.get(sixth_card, '')
                image_url = image_cache.get(card_id, '')

                # Separator
                sep_label = ctk.CTkLabel(self.cards_frame, text="→", font=ctk.CTkFont(size=26))
                sep_label.grid(row=0, column=5, padx=10)

                card_frame = ctk.CTkFrame(self.cards_frame, fg_color="transparent")
                card_frame.grid(row=0, column=6, padx=6, pady=4)

                try:
                    canvas = self.cards_frame.master
                    canvas_h = canvas.winfo_height() or 205
                    thumb_h = max(100, min(205, canvas_h - 30))
                    thumb_w = int(thumb_h * (140 / 205))
                except Exception:
                    thumb_w, thumb_h = 140, 205

                if image_url:
                    self.load_and_display_image(image_url, card_frame, sixth_card, is_sixth=True, target_size=(thumb_w, thumb_h))
                else:
                    label = ctk.CTkLabel(card_frame, text=sixth_card[:15], width=thumb_w, height=thumb_h,
                                         fg_color="gray30", corner_radius=5)
                    label.grid(row=0, column=0)

        # Display hand text
        self.hand_textbox.configure(state="normal")
        self.hand_textbox.delete("1.0", "end")
        self.hand_textbox.insert("1.0", "OPENING HAND:\n")
        for i, card in enumerate(self.current_hand, 1):
            self.hand_textbox.insert("end", f"  {i}. {card}\n")

        if sixth_card:
            self.hand_textbox.insert("end", "\n6TH CARD (Going Second):\n")
            self.hand_textbox.insert("end", f"  → {sixth_card}\n")

        self.hand_textbox.configure(state="disabled")

        # Calculate and display statistics
        self.display_statistics()

    def load_and_display_image(self, url: str, parent_frame, card_name: str, is_sixth: bool = False, target_size: tuple = None):
        # Delegated to the image manager module to reduce file size
        imgmgr.load_and_display_image(self, url, parent_frame, card_name, is_sixth=is_sixth, target_size=target_size)

    def draw_again(self):
        """Draw another hand"""
        self.draw_hand()

    def _resize_thumbnails(self, canvas_height: int):
        # Delegated to the image manager module to reduce file size
        imgmgr.resize_thumbnails(self, canvas_height)

    def display_statistics(self):
        statsmgr.display_statistics(self)


def main():
    app = YuGiOhHandSimulator()
    app.mainloop()


if __name__ == "__main__":
    main()
