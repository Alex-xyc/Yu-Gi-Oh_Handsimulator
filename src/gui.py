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
        self.image_cache: Dict[str, ImageTk.PhotoImage] = {}  # Cache loaded images
        self.card_image_labels = []  # Store image label references

        # Create UI
        self.create_widgets()

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

        # Apply button placed next to Engine input (column 7)
        self.draw_btn = ctk.CTkButton(counts_frame, text="Apply & Draw Hand", width=165,
                           command=self.apply_and_draw, state="disabled",
                           font=ctk.CTkFont(size=14, weight="bold"),
                           fg_color="green", hover_color="darkgreen")
        self.draw_btn.grid(row=2, column=7, padx=(10, 20), pady=10)

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
        container.grid_columnconfigure(0, weight=1)
        container.grid_columnconfigure(1, weight=0, minsize=8)
        container.grid_columnconfigure(2, weight=1)

        # Left panel - Hand display
        hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                      border_width=1, border_color="#3a3a3a")
        hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)
        hand_frame.grid_rowconfigure(1, weight=0)
        hand_frame.grid_rowconfigure(2, weight=1)
        hand_frame.grid_columnconfigure(0, weight=1)

        hand_title = ctk.CTkLabel(hand_frame, text="Test Hand",
                   font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
        hand_title.grid(row=0, column=0, pady=(10, 5), sticky='ew')


        # Card images frame with horizontal scrollbar using Canvas
        card_canvas = tk.Canvas(hand_frame, bg="#2b2b2b", highlightthickness=0, height=180)
        card_canvas.grid(row=1, column=0, padx=10, pady=6, sticky="ew")
        h_scroll = tk.Scrollbar(hand_frame, orient="horizontal", command=card_canvas.xview)
        h_scroll.grid(row=2, column=0, sticky="ew", padx=10)
        card_canvas.configure(xscrollcommand=h_scroll.set)
        # Frame inside the canvas for card images
        self.cards_frame = tk.Frame(card_canvas, bg="#2b2b2b")
        self.cards_frame_id = card_canvas.create_window((0, 0), window=self.cards_frame, anchor="nw")

        def _on_frame_configure(event):
            card_canvas.configure(scrollregion=card_canvas.bbox("all"))
        self.cards_frame.bind("<Configure>", _on_frame_configure)

        def _on_canvas_configure(event):
            # Make the canvas width fill the available space
            canvas_width = event.width
            card_canvas.itemconfig(self.cards_frame_id, width=canvas_width)
        card_canvas.bind("<Configure>", _on_canvas_configure)

        # Text display for card names (below images) - larger for readability
        # Let the textbox size naturally and expand; remove fixed height constraints
        self.hand_textbox = ctk.CTkTextbox(hand_frame, font=ctk.CTkFont(size=14), width=560)
        self.hand_textbox.grid(row=2, column=0, padx=10, pady=(6, 10), sticky="nsew")
        self.hand_textbox.insert("1.0", "Load a deck and click 'Apply & Draw Hand' to begin...")
        self.hand_textbox.configure(state="disabled")
        hand_frame.grid_rowconfigure(2, weight=1)

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

        # FOOTER: persistent area for actions so it doesn't reflow during panel resizing
        footer = ctk.CTkFrame(self, fg_color=self.bg_color)
        # reduce vertical gap between hand area and footer; keep small outer padding
        footer.grid(row=3, column=0, columnspan=2, sticky='ew', padx=10, pady=(2, 8))
        footer.grid_columnconfigure(0, weight=1)
        # larger button for easier tapping; stable placement so it doesn't reflow
        self.draw_again_btn = ctk.CTkButton(footer, text="Draw Again", width=210, height=42,
                            command=self.draw_again, state="disabled",
                            fg_color="#1976d2", hover_color="#165fb0",
                            font=ctk.CTkFont(size=14, weight="bold"))
        # small vertical padding to keep tight spacing
        self.draw_again_btn.grid(row=0, column=0, pady=4)
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

            # Show deck list in hand textbox
            self.hand_textbox.configure(state="normal")
            self.hand_textbox.delete("1.0", "end")
            self.hand_textbox.insert("1.0", "DECK LIST\n" + "=" * 40 + "\n\n")
            for card_name, copies in self.deck.cards.items():
                # Show counts before the card name (e.g. "3x Fallen of the White Dragon")
                self.hand_textbox.insert("end", f"{copies}x {card_name}\n")
            self.hand_textbox.insert("end", "\n" + "=" * 40)
            self.hand_textbox.insert("end", f"\nTotal: {deck_size} cards")
            self.hand_textbox.insert("end", "\n\nSet card counts and click 'Apply & Draw Hand'")
            self.hand_textbox.configure(state="disabled")

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load deck:\n{str(e)}")
            self.deck_info_label.configure(text="Failed to load deck", text_color="red")

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

        self.draw_again_btn.configure(state="normal")
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

                # Create frame for each card (bigger padding for larger thumbnails)
                card_frame = ctk.CTkFrame(self.cards_frame, fg_color=self.bg_color, corner_radius=6)
                card_frame.grid(row=0, column=i, padx=8, pady=6)

                if image_url:
                    self.load_and_display_image(image_url, card_frame, card)
                else:
                    # Fallback to text label (larger placeholder)
                    label = ctk.CTkLabel(card_frame, text=card[:15], width=168, height=246,
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

                if image_url:
                    self.load_and_display_image(image_url, card_frame, sixth_card, is_sixth=True)
                else:
                    label = ctk.CTkLabel(card_frame, text=sixth_card[:15], width=168, height=246,
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

    def load_and_display_image(self, url: str, parent_frame, card_name: str, is_sixth: bool = False):
        """Load image from URL and display it"""
        try:
            # Check if already cached
            if url in self.image_cache:
                img_tk = self.image_cache[url]
            else:
                # Download image
                req = urllib.request.Request(url)
                req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
                with urllib.request.urlopen(req, timeout=10) as response:
                    image_data = response.read()

                # Open and resize image
                img = Image.open(BytesIO(image_data))
                # Small images are 168x246; show them at native small-thumb size
                img = img.resize((168, 246), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                self.image_cache[url] = img_tk

            # Create label with image
            label = ctk.CTkLabel(parent_frame, image=img_tk, text="")
            label.image = img_tk  # Keep reference
            label.grid(row=0, column=0)
            # Add subtle border to image
            try:
                label.configure(border_width=1, border_color="#3a3a3a", corner_radius=6)
            except Exception:
                pass
            self.card_image_labels.append(label)

        except Exception as e:
            # Fallback to text (larger placeholder)
            label = ctk.CTkLabel(parent_frame, text=card_name[:12], width=168, height=246,
                                 fg_color="gray30", corner_radius=5)
            label.grid(row=0, column=0)

    def draw_again(self):
        """Draw another hand"""
        self.draw_hand()

    def display_statistics(self):
        """Calculate and display probability statistics"""
        deck_size = self.deck.get_deck_size()
        engine_count = sum(self.deck.cards[c] for c in self.deck.engine_cards)
        non_engine_count = sum(self.deck.cards[c] for c in self.deck.non_engine_cards)
        brick_count = sum(self.deck.cards[c] for c in self.deck.brick_cards)
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
        engine_in_hand = sum(1 for c in self.current_hand if c in self.deck.engine_cards)
        non_engine_in_hand = sum(1 for c in self.current_hand if c in self.deck.non_engine_cards)
        brick_in_hand = sum(1 for c in self.current_hand if c in self.deck.brick_cards)

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
