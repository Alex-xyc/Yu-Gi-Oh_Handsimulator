"""Card counts UI component.

Provides `create_counts_section(app)` which builds the Brick/Non-Engine/Engine
inputs and the Apply & Draw button, and exposes the entry widgets on `app`.
"""
from typing import Any
import customtkinter as ctk


def create_counts_section(app: Any):
    counts_frame = ctk.CTkFrame(app)
    counts_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=5, sticky="ew")
    for i in range(9):
        counts_frame.grid_columnconfigure(i, weight=0)
    counts_frame.grid_columnconfigure(0, weight=1)
    counts_frame.grid_columnconfigure(8, weight=1)

    instr_label = ctk.CTkLabel(counts_frame,
                    text="Specify card counts:",
                    font=ctk.CTkFont(size=16, weight="bold"))
    instr_label.grid(row=0, column=0, columnspan=9, pady=(10, 5))

    desc_label = ctk.CTkLabel(counts_frame,
                   text="Bricks = cards you don't want to draw  |  Non-Engine = handtraps & board breakers  |  Engine = combo pieces",
                   font=ctk.CTkFont(size=12), text_color="gray")
    desc_label.grid(row=1, column=0, columnspan=9, pady=(0, 10))

    brick_label = ctk.CTkLabel(counts_frame, text="Bricks:", font=ctk.CTkFont(size=15))
    brick_label.grid(row=2, column=1, padx=(10, 5), pady=10)

    app.brick_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                    font=ctk.CTkFont(size=14))
    app.brick_entry.grid(row=2, column=2, padx=5, pady=10)
    app.brick_entry.insert(0, "0")

    non_engine_label = ctk.CTkLabel(counts_frame, text="Non-Engine:", font=ctk.CTkFont(size=15))
    non_engine_label.grid(row=2, column=3, padx=(10, 5), pady=10)

    app.non_engine_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                         font=ctk.CTkFont(size=14))
    app.non_engine_entry.grid(row=2, column=4, padx=5, pady=10)
    app.non_engine_entry.insert(0, "0")

    engine_label = ctk.CTkLabel(counts_frame, text="Engine:", font=ctk.CTkFont(size=15))
    engine_label.grid(row=2, column=5, padx=(10, 5), pady=10)

    app.engine_entry = ctk.CTkEntry(counts_frame, width=80, placeholder_text="0",
                         font=ctk.CTkFont(size=14))
    app.engine_entry.grid(row=2, column=6, padx=(5, 5), pady=10)
    app.engine_entry.insert(0, "0")

    app.draw_btn = ctk.CTkButton(counts_frame, text="Apply & Draw Hand", width=165,
                       command=app.apply_and_draw, state="disabled",
                       font=ctk.CTkFont(size=14, weight="bold"),
                       fg_color="green", hover_color="darkgreen")
    app.draw_btn.grid(row=2, column=7, padx=(10, 20), pady=10)

    app.deck_info_label = ctk.CTkLabel(counts_frame, text="No deck loaded",
                 font=ctk.CTkFont(size=13), text_color="orange")
    app.deck_info_label.grid(row=3, column=0, columnspan=9, pady=(0, 8))

    return counts_frame
