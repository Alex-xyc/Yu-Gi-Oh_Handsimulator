"""Creates the right-side statistics panel UI and exposes it to the app.

This module provides `create_stats_section(app, container)` which builds the
CTkFrame and `app.stats_textbox` used by `stats_manager.display_statistics`.
"""
from typing import Any
import customtkinter as ctk
import tkinter as tk


def create_stats_section(app: Any, container: Any):
    stats_frame = ctk.CTkFrame(container, fg_color="#2b2b2b", corner_radius=12,
                   border_width=1, border_color="#3a3a3a")
    stats_frame.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)
    stats_frame.grid_rowconfigure(0, weight=0)
    stats_frame.grid_rowconfigure(1, weight=1)
    stats_frame.grid_columnconfigure(0, weight=1)

    stats_title = ctk.CTkLabel(stats_frame, text="Probabilities & Statistics",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
    stats_title.grid(row=0, column=0, pady=(10, 5), sticky='ew')

    stats_textbox = ctk.CTkTextbox(stats_frame, font=ctk.CTkFont(family="Consolas", size=12),
                         width=560)
    stats_textbox.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
    stats_textbox.insert("1.0", "Statistics will appear here after drawing a hand...")
    stats_textbox.configure(state="disabled")

    app.stats_textbox = stats_textbox
    return stats_frame
