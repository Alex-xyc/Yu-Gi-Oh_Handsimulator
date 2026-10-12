"""The "Probabilities & Statistics" panel."""

import tkinter as tk
from typing import List

import customtkinter as ctk

from . import theme
from .window import lighten_scrollbar


class StatsPanel(ctk.CTkFrame):
    """A titled, read-only text box showing the statistics report."""

    def __init__(self, master):
        super().__init__(master, fg_color=theme.PANEL_BG, corner_radius=theme.PANEL_CORNER_RADIUS,
                         border_width=1, border_color=theme.PANEL_BORDER)
        self.grid_rowconfigure(0, weight=0)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        title = ctk.CTkLabel(self, text="Probabilities & Statistics",
                             font=ctk.CTkFont(size=16, weight="bold"), anchor="center", justify="center")
        title.grid(row=0, column=0, pady=(10, 5), sticky='ew')

        # width=200: a small requested width so this panel can be narrowed with the divider
        self.textbox = ctk.CTkTextbox(self, font=ctk.CTkFont(family=theme.MONO_FONT, size=12), width=200)
        for scrollbar in (getattr(self.textbox, "_y_scrollbar", None),
                          getattr(self.textbox, "_x_scrollbar", None)):
            if scrollbar is not None:
                lighten_scrollbar(scrollbar)
        self.textbox.grid(row=1, column=0, padx=10, pady=(5, 15), sticky="nsew")
        self.show_text("Statistics will appear here after drawing a hand...")

    def show_text(self, text: str) -> None:
        self.textbox.configure(state="normal")
        self.textbox.delete("1.0", "end")
        self.textbox.insert("1.0", text)
        self.textbox.configure(state="disabled")

    def preview_parts(self) -> List[tk.Widget]:
        """Areas drawn in the greyed-out layout preview while the divider is dragged."""
        return [self.textbox]
