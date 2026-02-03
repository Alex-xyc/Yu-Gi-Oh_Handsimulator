"""Top/header UI for the hand simulator.

Exports `create_top_section(app)` which creates the deck loading frame and
attaches the relevant widgets to `app` (e.g., `ydke_entry`, `file_path_label`, `draw_btn`).
"""
import os
import tkinter as tk
import customtkinter as ctk


def create_top_section(app):
    # TOP SECTION: Deck Loading
    deck_frame = ctk.CTkFrame(app)
    deck_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
    deck_frame.grid_columnconfigure(1, weight=1)

    # Title
    title_label = ctk.CTkLabel(deck_frame, text="Yu-Gi-Oh Hand Simulator By Xin Yuan",
                                font=ctk.CTkFont(size=24, weight="bold"))
    title_label.grid(row=0, column=0, columnspan=3, pady=(10, 15))

    # YDKE Code input
    ydke_label = ctk.CTkLabel(deck_frame, text="YDKe Code:", font=ctk.CTkFont(size=14))
    ydke_label.grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")

    app.ydke_entry = ctk.CTkEntry(deck_frame, placeholder_text="Paste your ydke code here...",
                                    width=500)
    app.ydke_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    load_ydke_btn = ctk.CTkButton(deck_frame, text="Load Deck", width=100,
                                   command=app.load_from_ydke)
    load_ydke_btn.grid(row=1, column=2, padx=(5, 15), pady=5)

    # OR divider
    or_label = ctk.CTkLabel(deck_frame, text="— OR —", font=ctk.CTkFont(size=12))
    or_label.grid(row=2, column=0, columnspan=3, pady=5)

    # File selection
    file_label = ctk.CTkLabel(deck_frame, text="Load .ydk file:", font=ctk.CTkFont(size=14))
    file_label.grid(row=3, column=0, padx=(15, 5), pady=5, sticky="w")

    # Inline container so file name and Browse button sit next to each other
    file_container = ctk.CTkFrame(deck_frame, fg_color="transparent")
    file_container.grid(row=3, column=1, padx=5, pady=5, sticky="w")
    file_container.grid_columnconfigure(0, weight=0)

    app.file_path_label = ctk.CTkLabel(file_container, text="No file selected",
                         font=ctk.CTkFont(size=12), text_color="gray")
    app.file_path_label.grid(row=0, column=0, sticky="w")

    browse_btn = ctk.CTkButton(file_container, text="Browse...", width=100,
                    command=app.browse_file)
    browse_btn.grid(row=0, column=1, padx=(5, 0), sticky="w")

    return deck_frame
