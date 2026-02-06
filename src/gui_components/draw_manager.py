"""Draw manager: encapsulates drawing logic and UI updates.

Functions operate on the `app` instance and replace the methods
`apply_and_draw`, `draw_hand`, and `draw_again` from `gui.py`.
"""
import random
from main import get_image_cache


def apply_and_draw(app):
    if not app.deck_loaded:
        try:
            from tkinter import messagebox
            messagebox.showwarning("Warning", "Please load a deck first.")
        except Exception:
            pass
        return

    try:
        brick_count = int(app.brick_entry.get() or 0)
        non_engine_count = int(app.non_engine_entry.get() or 0)
        engine_count = int(app.engine_entry.get() or 0)
    except Exception:
        try:
            from tkinter import messagebox
            messagebox.showerror("Error", "Please enter valid numbers for card counts.")
        except Exception:
            pass
        return

    deck_size = app.deck.get_deck_size()
    total = brick_count + non_engine_count + engine_count

    if total > deck_size:
        try:
            from tkinter import messagebox
            messagebox.showerror("Error", f"Total counts ({total}) exceed deck size ({deck_size}).")
        except Exception:
            pass
        return

    if brick_count < 0 or non_engine_count < 0 or engine_count < 0:
        try:
            from tkinter import messagebox
            messagebox.showerror("Error", "Card counts cannot be negative.")
        except Exception:
            pass
        return

    # Assign categories
    card_list = list(app.deck.cards.keys())
    app.deck.engine_cards.clear()
    app.deck.non_engine_cards.clear()
    app.deck.brick_cards.clear()

    remaining = brick_count
    for card_name in card_list:
        if remaining <= 0:
            break
        copies = app.deck.cards[card_name]
        if copies <= remaining:
            app.deck.brick_cards.add(card_name)
        remaining -= copies

    remaining = non_engine_count
    for card_name in card_list:
        if remaining <= 0:
            break
        if card_name in app.deck.brick_cards:
            continue
        copies = app.deck.cards[card_name]
        if copies <= remaining:
            app.deck.non_engine_cards.add(card_name)
        remaining -= copies

    remaining = engine_count
    for card_name in card_list:
        if remaining <= 0:
            break
        if card_name in app.deck.brick_cards or card_name in app.deck.non_engine_cards:
            continue
        copies = app.deck.cards[card_name]
        if copies <= remaining:
            app.deck.engine_cards.add(card_name)
        remaining -= copies

    # draw_again button removed; rely on the main Apply & Draw Hand button
    draw_hand(app)


def draw_hand(app):
    full_deck = app.deck.get_deck_list()
    random.shuffle(full_deck)
    app.current_hand = full_deck[:5]

    # Clear previous card images
    try:
        for widget in app.cards_frame.winfo_children():
            widget.destroy()
    except Exception:
        pass
    app.card_image_labels.clear()

    # Display card images
    try:
        image_cache = get_image_cache()
    except Exception:
        image_cache = {}

    if getattr(app, 'PIL_AVAILABLE', True):
        for i, card in enumerate(app.current_hand):
            card_id = app.card_id_map.get(card, '')
            image_url = image_cache.get(card_id, '')

            # Create frame for each card (padding around thumbnail)
            try:
                card_frame = app.card_frame_factory(app.cards_frame)
            except Exception:
                import customtkinter as ctk
                card_frame = ctk.CTkFrame(app.cards_frame, fg_color=app.bg_color, corner_radius=6)
            try:
                card_frame.grid(row=0, column=i, padx=8, pady=6)
            except Exception:
                pass

            # Compute responsive thumbnail size based on canvas height
            try:
                canvas = app.cards_frame.master
                canvas_h = canvas.winfo_height() or 205
                thumb_h = max(100, min(205, canvas_h - 30))
                thumb_w = int(thumb_h * (140 / 205))
            except Exception:
                thumb_w, thumb_h = 140, 205

            if image_url:
                if hasattr(app, 'imagemgr') and app.imagemgr:
                    app.imagemgr.display_image_in_frame(image_url, target_size=(thumb_w, thumb_h), parent_frame=card_frame, card_name=card, app=app)
                else:
                    try:
                        app.load_and_display_image(image_url, card_frame, card, target_size=(thumb_w, thumb_h))
                    except Exception:
                        pass
            else:
                try:
                    import customtkinter as ctk
                    label = ctk.CTkLabel(card_frame, text=card[:15], width=thumb_w, height=thumb_h,
                                         fg_color="gray30", corner_radius=5)
                    label.grid(row=0, column=0)
                except Exception:
                    try:
                        import tkinter as tk
                        lbl = tk.Label(card_frame, text=card[:15], width=thumb_w, height=thumb_h, bg="gray30")
                        lbl.grid(row=0, column=0)
                    except Exception:
                        pass

    # 6th card simulation
    temp_deck = full_deck.copy()
    for card in app.current_hand:
        if card in temp_deck:
            temp_deck.remove(card)

    sixth_card = None
    if temp_deck:
        sixth_card = random.choice(temp_deck)

        # Show 6th card image
        try:
            image_cache = get_image_cache()
        except Exception:
            image_cache = {}
        card_id = app.card_id_map.get(sixth_card, '')
        image_url = image_cache.get(card_id, '')

        try:
            sep_label = app.sep_label_factory(app.cards_frame)
            sep_label.grid(row=0, column=5, padx=10)
        except Exception:
            pass

        try:
            card_frame = app.card_frame_factory(app.cards_frame)
            card_frame.grid(row=0, column=6, padx=6, pady=4)
        except Exception:
            pass

        try:
            canvas = app.cards_frame.master
            canvas_h = canvas.winfo_height() or 205
            thumb_h = max(100, min(205, canvas_h - 30))
            thumb_w = int(thumb_h * (140 / 205))
        except Exception:
            thumb_w, thumb_h = 140, 205

        if image_url:
            if hasattr(app, 'imagemgr') and app.imagemgr:
                app.imagemgr.display_image_in_frame(image_url, target_size=(thumb_w, thumb_h), parent_frame=card_frame, card_name=sixth_card, app=app, is_sixth=True)
            else:
                try:
                    app.load_and_display_image(image_url, card_frame, sixth_card, is_sixth=True, target_size=(thumb_w, thumb_h))
                except Exception:
                    pass
        else:
            try:
                import customtkinter as ctk
                label = ctk.CTkLabel(card_frame, text=sixth_card[:15], width=thumb_w, height=thumb_h,
                                     fg_color="gray30", corner_radius=5)
                label.grid(row=0, column=0)
            except Exception:
                try:
                    import tkinter as tk
                    lbl = tk.Label(card_frame, text=sixth_card[:15], width=thumb_w, height=thumb_h, bg="gray30")
                    lbl.grid(row=0, column=0)
                except Exception:
                    pass

    # Display hand text
    try:
        app.hand_textbox.configure(state="normal")
        app.hand_textbox.delete("1.0", "end")
        app.hand_textbox.insert("1.0", "OPENING HAND:\n")
        for i, card in enumerate(app.current_hand, 1):
            app.hand_textbox.insert("end", f"  {i}. {card}\n")

        if sixth_card:
            app.hand_textbox.insert("end", "\n6TH CARD (Going Second):\n")
            app.hand_textbox.insert("end", f"  → {sixth_card}\n")

        app.hand_textbox.configure(state="disabled")
    except Exception:
        pass

    # Calculate and display statistics
    try:
        if hasattr(app, 'statsmgr') and app.statsmgr:
            app.statsmgr.display_statistics(app)
        else:
            try:
                app.display_statistics()
            except Exception:
                pass
    except Exception:
        pass


def draw_again(app):
    draw_hand(app)
