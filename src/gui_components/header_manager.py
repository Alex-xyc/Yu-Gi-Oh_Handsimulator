"""Header (deck loading) UI component.

Provides `create_top_section(app)` which builds the title, ydke entry,
file browse button and exposes `app.ydke_entry`, `app.file_path_label`,
and `app.load_from_ydke` wiring.
"""
from typing import Any
import os
import tkinter as tk
import customtkinter as ctk


def create_top_section(app: Any):
    deck_frame = ctk.CTkFrame(app)
    deck_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="ew")
    deck_frame.grid_columnconfigure(1, weight=1)

    title_label = ctk.CTkLabel(deck_frame, text="Yu-Gi-Oh Hand Simulator By Xin Yuan",
                                font=ctk.CTkFont(size=24, weight="bold"))
    title_label.grid(row=0, column=0, columnspan=3, pady=(10, 15))

    ydke_label = ctk.CTkLabel(deck_frame, text="YDKe Code:", font=ctk.CTkFont(size=14))
    ydke_label.grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")

    app.ydke_entry = ctk.CTkEntry(deck_frame, placeholder_text="Paste your ydke code here...",
                                    width=500)
    app.ydke_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

    load_ydke_btn = ctk.CTkButton(deck_frame, text="Load Deck", width=100,
                                   command=app.load_from_ydke)
    load_ydke_btn.grid(row=1, column=2, padx=(5, 15), pady=5)

    or_label = ctk.CTkLabel(deck_frame, text="— OR —", font=ctk.CTkFont(size=12))
    or_label.grid(row=2, column=0, columnspan=3, pady=5)

    file_label = ctk.CTkLabel(deck_frame, text="Load .ydk file:", font=ctk.CTkFont(size=14))
    file_label.grid(row=3, column=0, padx=(15, 5), pady=5, sticky="w")

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
