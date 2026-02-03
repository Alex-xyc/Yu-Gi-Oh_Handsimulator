"""Deck loading and file handling helpers for the GUI.

Functions operate on the `app` instance (YuGiOhHandSimulator) so they can
update widgets and state directly.
"""
import os
import sys
from tkinter import filedialog, messagebox

from main import fetch_multiple_card_names, parse_ydke_url


def browse_file(app):
    """Browse for a .ydk file and load it into the app."""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        # when running from src/gui_components, step up one to src
        base_path = os.path.dirname(base_path)

    decklists_path = os.path.join(base_path, "decklists")
    if not os.path.exists(decklists_path):
        os.makedirs(decklists_path, exist_ok=True)
    initial_dir = decklists_path

    filepath = filedialog.askopenfilename(
        title="Select YDK File",
        initialdir=initial_dir,
        filetypes=[("YDK files", "*.ydk"), ("All files", "*")]
    )

    if filepath:
        try:
            app.file_path_label.configure(text=os.path.basename(filepath))
            with open(filepath, 'r', encoding='utf-8') as f:
                ydk_content = f.read()
            load_deck(app, ydk_content)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to read file: {e}")


def open_decklists_folder(app):
    """Open the decklists folder in file explorer"""
    if getattr(sys, 'frozen', False):
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        base_path = os.path.dirname(base_path)
    decklists_path = os.path.join(base_path, "decklists")
    if not os.path.exists(decklists_path):
        os.makedirs(decklists_path, exist_ok=True)
        messagebox.showinfo("Info", f"Created decklists folder at:\n{decklists_path}\n\nPlace your .ydk files here!")
    try:
        os.startfile(decklists_path)
    except Exception:
        # best-effort cross-platform fallback
        try:
            import subprocess
            subprocess.Popen(['explorer', decklists_path])
        except Exception:
            pass


def load_deck(app, ydk_code: str):
    """Load deck from YDK file or ydke URL and update the app state/widgets."""
    app.deck.clear_deck()
    ydk_code = (ydk_code or "").strip()

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

        app.deck_info_label.configure(text="Loading card names from API...", text_color="yellow")
        app.update()

        card_database = fetch_multiple_card_names(list(set(card_ids)), verbose=False)

        # Count cards and map names to IDs
        card_counts = {}
        for card_id in card_ids:
            card_name = card_database.get(card_id, f"Card_{card_id}")
            card_counts[card_name] = card_counts.get(card_name, 0) + 1
            app.card_id_map[card_name] = card_id

        for card_name, copies in card_counts.items():
            if copies > app.deck.MAX_COPIES:
                messagebox.showerror("Error", f"'{card_name}' has {copies} copies. Max is {app.deck.MAX_COPIES}.")
                app.deck.clear_deck()
                return
            app.deck.add_card(card_name, copies)

        app.deck_loaded = True
        deck_size = app.deck.get_deck_size()
        app.deck_info_label.configure(text=f"✓ Deck loaded: {deck_size} cards", text_color="lightgreen")
        app.draw_btn.configure(state="normal")

        # Show deck list in hand textbox
        app.hand_textbox.configure(state="normal")
        app.hand_textbox.delete("1.0", "end")
        app.hand_textbox.insert("1.0", "DECK LIST\n" + "=" * 40 + "\n\n")
        for card_name, copies in app.deck.cards.items():
            app.hand_textbox.insert("end", f"{copies}x {card_name}\n")
        app.hand_textbox.insert("end", "\n" + "=" * 40)
        app.hand_textbox.insert("end", f"\nTotal: {deck_size} cards")
        app.hand_textbox.insert("end", "\n\nSet card counts and click 'Apply & Draw Hand'")
        app.hand_textbox.configure(state="disabled")

    except Exception as e:
        messagebox.showerror("Error", f"Failed to load deck:\n{str(e)}")
        app.deck_info_label.configure(text="Failed to load deck", text_color="red")
