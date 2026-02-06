"""GUI for the Yu-Gi-Oh! Hand Simulator.

Provides a CustomTkinter-based desktop application to load decks,
draw simulated opening hands, and display probability statistics.

Copyright (c) 2026 Alex-xyc
"""

import sys
import ctypes
import logging
from typing import Dict

import tkinter as tk
from tkinter import messagebox

import customtkinter as ctk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import gui_components.image_manager as imagemgr
except Exception:
    pass
    imagemgr = None

try:
    import gui_components.deck_manager as deckmgr
except Exception:
    deckmgr = None

try:
    import gui_components.draw_manager as drawmgr
except Exception:
    drawmgr = None

try:
    import gui_components.stats_manager as statsmgr
except Exception:
    statsmgr = None

# Import common GUI component modules at module level to avoid import-outside-toplevel warnings
try:
    import gui_components.header_manager as headermgr
except Exception:
    headermgr = None

try:
    import gui_components.counts_manager as countsmgr
except Exception:
    countsmgr = None

try:
    import gui_components.layout_manager as layoutmgr
except Exception:
    layoutmgr = None

try:
    import gui_components.hand_manager as handmgr
except Exception:
    handmgr = None

try:
    import gui_components.stats_ui as statsui
except Exception:
    statsui = None

try:
    import gui_components.icon_manager as iconmgr
except Exception:
    iconmgr = None


from main import YuGiOhDeck



class YuGiOhHandSimulator(ctk.CTk):
    """Yu-Gi-Oh Hand Simulator GUI Application

    pylint: disable=too-many-instance-attributes, too-many-branches, too-many-statements
    """

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

        # Set application icon via component (keeps gui.py minimal)
        try:
            if iconmgr:
                iconmgr.set_app_icon(self)
        except Exception:
            logging.debug("icon manager failed to set icon")

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
        # Expose component references on the instance
        self.imagemgr = imagemgr
        self.statsmgr = statsmgr

        # Create UI
        self.create_widgets()

    def create_widgets(self):
        """Create all UI components"""

        # Main container with grid
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # TOP SECTION: Deck Loading (delegated)
        if headermgr:
            try:
                headermgr.create_top_section(self)
            except Exception:
                logging.debug("header_manager.create_top_section failed")
        else:
            try:
                from gui_components.header_manager import create_top_section
                create_top_section(self)
            except Exception:
                pass



        # MIDDLE SECTION: Card Counts (delegated)
        if countsmgr:
            try:
                countsmgr.create_counts_section(self)
            except Exception:
                logging.debug("counts_manager.create_counts_section failed")
        else:
            try:
                from gui_components.counts_manager import create_counts_section
                create_counts_section(self)
            except Exception:
                pass

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
        # Delegate container + divider creation to layout_manager
        if layoutmgr:
            try:
                self.bg_color = "#242424"
                container, divider = layoutmgr.create_container(self)

                # Create the left hand section (canvas + scrollbars + hand textbox)
                if handmgr:
                    hand_frame = handmgr.create_hand_section(self, container)
                else:
                    try:
                        from gui_components.hand_manager import create_hand_section
                        hand_frame = create_hand_section(self, container)
                    except Exception:
                        hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b")
                        hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)

                # Right panel - Statistics (delegated to stats_ui)
                if statsui:
                    stats_frame = statsui.create_stats_section(self, container)
                else:
                    stats_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                                   border_width=1, border_color="#3a3a3a")
                    stats_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)
                    stats_frame.grid_rowconfigure(0, weight=0)
                    stats_frame.grid_rowconfigure(1, weight=1)
                    stats_frame.grid_columnconfigure(0, weight=1)
                    stats_title = ctk.CTkLabel(stats_frame, text="Probabilities & Statistics",
                            font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
                    stats_title.grid(row=0, column=0, pady=(10, 5), sticky='ew')

                # Register divider handlers to manage dragging & resize behavior
                try:
                    layoutmgr.register_divider_handlers(container, divider, hand_frame, self)
                except Exception:
                    logging.debug("layoutmgr.register_divider_handlers failed")

                # Ensure stats_textbox exists (stats_ui should have set it)
                if not hasattr(self, 'stats_textbox'):
                    try:
                        self.stats_textbox = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(family="Consolas", size=12),
                                             width=560)
                        self.stats_textbox.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
                        self.stats_textbox.insert("1.0", "Statistics will appear here after drawing a hand...")
                        self.stats_textbox.configure(state="disabled")
                    except Exception:
                        txt = tk.Text(stats_frame, font=("Consolas", 12))
                        txt.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
                        txt.insert("1.0", "Statistics will appear here after drawing a hand...")
                        txt.configure(state="disabled")
                        self.stats_textbox = txt
            except Exception:
                # Minimal fallback when layout manager is unavailable: create
                # a simple container and delegate hand/stats sections to their
                # managers. Keep layout code small to reduce `gui.py` length.
                self.bg_color = "#242424"
                container = ctk.CTkFrame(self, fg_color=self.bg_color)
                container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
                self.grid_rowconfigure(2, weight=1)
                container.grid_rowconfigure(0, weight=1)
                container.grid_columnconfigure(0, weight=1)
                container.grid_columnconfigure(1, weight=0, minsize=8)
                container.grid_columnconfigure(2, weight=1)

                try:
                    import gui_components.hand_manager as handmgr
                    hand_frame = handmgr.create_hand_section(self, container)
                except Exception:
                    hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b")
                    hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)

                try:
                    import gui_components.stats_ui as statsui
                    stats_frame = statsui.create_stats_section(self, container)
                except Exception:
                    stats_frame = ctk.CTkFrame(container, fg_color="#2b2b2b")
                    stats_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)
                except Exception:
                    # Minimal fallback when layout manager is unavailable: create
                    # a simple container and delegate hand/stats sections to their
                    # managers. Keep layout code small to reduce `gui.py` length.
                    self.bg_color = "#242424"
                    container = ctk.CTkFrame(self, fg_color=self.bg_color)
                    container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
                    self.grid_rowconfigure(2, weight=1)
                    container.grid_rowconfigure(0, weight=1)
                    container.grid_columnconfigure(0, weight=1)
                    container.grid_columnconfigure(1, weight=0, minsize=8)
                    container.grid_columnconfigure(2, weight=1)

                    try:
                        import gui_components.hand_manager as handmgr
                        hand_frame = handmgr.create_hand_section(self, container)
                    except Exception:
                        hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b")
                        hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)

                    try:
                        import gui_components.stats_ui as statsui
                        stats_frame = statsui.create_stats_section(self, container)
                    except Exception:
                        stats_frame = ctk.CTkFrame(container, fg_color="#2b2b2b")
                        stats_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)

                # Draw again button moved to persistent footer (created below)

                # Ensure a divider exists (layout_manager normally provides one).
                if 'divider' not in locals():
                    divider = tk.Frame(container, bg=self.bg_color, width=8, cursor="sb_h_double_arrow")
                    divider.grid(row=0, column=1, sticky="ns", pady=6)

        # `stats_ui.create_stats_section` is expected to set `self.stats_textbox`.
        # If the import failed and we used the fallback above, ensure `self.stats_textbox` exists.
        if not hasattr(self, 'stats_textbox'):
            try:
                self.stats_textbox = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(family="Consolas", size=12),
                                     width=560)
                self.stats_textbox.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
                self.stats_textbox.insert("1.0", "Statistics will appear here after drawing a hand...")
                self.stats_textbox.configure(state="disabled")
            except Exception:
                # Last-resort: create a standard tk.Text if CTkTextbox isn't available
                txt = tk.Text(stats_frame, font=("Consolas", 12))
                txt.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
                txt.insert("1.0", "Statistics will appear here after drawing a hand...")
                txt.configure(state="disabled")
                self.stats_textbox = txt

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
        if deckmgr:
            return deckmgr.browse_file(self)
        messagebox.showerror("Error", "Deck manager not available; cannot browse files.")
        return None

    def open_decklists_folder(self):
        """Open the decklists folder in file explorer"""
        if deckmgr:
            return deckmgr.open_decklists_folder(self)
        messagebox.showerror("Error", "Deck manager not available; cannot open decklists folder.")
        return None

    def load_deck(self, ydk_code: str):
        """Load deck from YDK file or ydke URL"""
        if deckmgr:
            return deckmgr.load_deck(self, ydk_code)
        messagebox.showerror("Error", "Deck manager not available; cannot load deck.")
        return None

    def apply_and_draw(self):
        """Apply card counts and draw a hand"""
        if drawmgr:
            return drawmgr.apply_and_draw(self)
        messagebox.showwarning("Warning", "Draw manager not available; cannot apply counts and draw.")
        return None

    def draw_hand(self):
        """Draw a test hand and display results"""
        if drawmgr:
            return drawmgr.draw_hand(self)
        messagebox.showerror("Error", "Draw manager not available; cannot draw hand.")
        return None

    def load_and_display_image(self, url: str, parent_frame, card_name: str, is_sixth: bool = False, target_size: tuple = None):
        """Load image from URL and display it"""
        if imagemgr:
            return imagemgr.display_image_in_frame(url, target_size=target_size, parent_frame=parent_frame, card_name=card_name, app=self, is_sixth=is_sixth)
        # Minimal placeholder when image manager isn't available
        try:
            tw, th = (target_size if target_size else (140, 205))
        except Exception:
            tw, th = (140, 205)
        label = ctk.CTkLabel(parent_frame, text=card_name[:12], width=tw, height=th,
                             fg_color="gray30", corner_radius=5)
        label.grid(row=0, column=0)
        self.card_image_labels.append(label)
        return None

    def draw_again(self):
        """Draw another hand"""
        if drawmgr:
            return drawmgr.draw_again(self)
        return self.draw_hand()

    def _resize_thumbnails(self, canvas_height: int):
        """Resize all displayed thumbnails to fit the given canvas height while keeping padding."""
        # Delegate to image manager if available (keeps existing behavior as fallback)
        # expose imagemgr/statsmgr to child modules (already set in __init__)
        if imagemgr:
            try:
                imagemgr.resize_thumbnails_for_canvas_height(canvas_height, self)
                return
            except Exception:
                logging.debug("imagemgr.resize_thumbnails_for_canvas_height failed")
        # No-op fallback: leave existing thumbnails as-is when no image manager

    def display_statistics(self):
        """Calculate and display probability statistics"""
        if statsmgr:
            return statsmgr.display_statistics(self)
        # Minimal fallback: indicate statistics unavailable
        try:
            self.stats_textbox.configure(state="normal")
            self.stats_textbox.delete("1.0", "end")
            self.stats_textbox.insert("end", "Statistics unavailable (stats manager not loaded)")
            self.stats_textbox.configure(state="disabled")
        except Exception:
            pass


def main():
    app = YuGiOhHandSimulator()
    app.mainloop()


if __name__ == "__main__":
    main()
