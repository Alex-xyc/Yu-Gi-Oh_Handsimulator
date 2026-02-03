"""Hand panel component: left-side card display and hand textbox.

This module creates the canvas holding card thumbnails, the horizontal
scrollbar and the hand text area, and attaches them to the provided
application object (`app`). It sets `app.hand_frame`, `app.cards_frame`,
`app.cards_frame_id` and `app.hand_textbox` so the rest of the GUI can
interact with them as before.
"""
from typing import Any
import tkinter as tk
import customtkinter as ctk


def create_hand_section(app: Any, container: Any):
    """Create the left hand display section inside `container`.

    Returns the created `hand_frame` so callers can bind divider logic.
    """
    # Left panel - Hand display (responsive)
    hand_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                  border_width=1, border_color="#3a3a3a")
    hand_frame.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)
    hand_frame.grid_rowconfigure(1, weight=1)  # Card images area expands
    hand_frame.grid_rowconfigure(2, weight=0)  # Horizontal scrollbar (fixed size)
    hand_frame.grid_rowconfigure(3, weight=2)  # Text area expands more
    hand_frame.grid_columnconfigure(0, weight=1)

    # Header with title (Draw button removed)
    header_frame = ctk.CTkFrame(hand_frame, fg_color="transparent")
    header_frame.grid(row=0, column=0, pady=(8, 4), padx=10, sticky='ew')
    header_frame.grid_columnconfigure(0, weight=1)
    header_frame.grid_columnconfigure(1, weight=0)

    hand_title = ctk.CTkLabel(header_frame, text="Test Hand",
           font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
    hand_title.grid(row=0, column=0, sticky='ew')

    # Card images frame with horizontal scrollbar using Canvas (responsive)
    card_canvas = tk.Canvas(hand_frame, bg="#23272b", highlightthickness=0, bd=0, relief="flat")
    card_canvas.grid(row=1, column=0, padx=10, pady=(6, 0), sticky="nsew")
    # Frame inside the canvas for card images
    cards_frame = tk.Frame(card_canvas, bg="#23272b")
    cards_frame_id = card_canvas.create_window((0, 0), window=cards_frame, anchor="nw")

    def _on_frame_configure(event):
        card_canvas.configure(scrollregion=card_canvas.bbox("all"))

    cards_frame.bind("<Configure>", _on_frame_configure)

    def _on_canvas_configure(event):
        # Make the canvas height fill the available space
        canvas_height = event.height
        card_canvas.itemconfig(cards_frame_id, height=canvas_height)
        # Update thumbnails to match new canvas height so they scale responsively
        try:
            app._resize_thumbnails(canvas_height)
        except Exception:
            pass

    card_canvas.bind("<Configure>", _on_canvas_configure)

    # Horizontal scrollbar between images and text (styled to match CTk theme)
    try:
        h_scroll = ctk.CTkScrollbar(hand_frame, orientation="horizontal", command=card_canvas.xview)
        h_scroll.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 0))
        try:
            h_scroll.configure(fg_color="#23272b")
            h_scroll.configure(border_color="#23272b")
            h_scroll.configure(corner_radius=6)
        except Exception:
            try:
                h_scroll.configure(bg="#23272b")
            except Exception:
                pass
        card_canvas.configure(xscrollcommand=h_scroll.set)
    except Exception:
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
    hand_textbox = tk.Text(
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
    hand_textbox.grid(row=0, column=0, sticky="nsew")
    try:
        y_scroll = ctk.CTkScrollbar(text_frame, orientation="vertical", command=hand_textbox.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        try:
            y_scroll.configure(fg_color="#23272b", border_color="#23272b", corner_radius=6)
        except Exception:
            try:
                y_scroll.configure(bg="#23272b")
            except Exception:
                pass
    except Exception:
        y_scroll = tk.Scrollbar(text_frame, orient="vertical", command=hand_textbox.yview)
        y_scroll.grid(row=0, column=1, sticky="ns")
        try:
            y_scroll.configure(bg="#23272b", troughcolor="#23272b", activebackground="#23272b")
        except Exception:
            pass
    hand_textbox.configure(yscrollcommand=y_scroll.set)
    hand_textbox.insert("1.0", "Load a deck and click 'Apply & Draw Hand' to begin...")
    hand_textbox.configure(state="disabled")

    # Attach to app so other modules can use these widgets
    app.hand_frame = hand_frame
    app.cards_frame = cards_frame
    app.cards_frame_id = cards_frame_id
    app.hand_textbox = hand_textbox

    return hand_frame
