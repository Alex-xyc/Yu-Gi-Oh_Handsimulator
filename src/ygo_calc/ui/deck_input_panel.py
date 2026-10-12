"""Top section: app title, ydke:// code entry and .ydk file picker."""

import os
from tkinter import filedialog, messagebox
from typing import Callable

import customtkinter as ctk

from ..paths import ensure_user_decklists_dir
from . import theme


class DeckInputPanel(ctk.CTkFrame):
    """Lets the user load a deck; calls on_load(deck_code) with the code or file text."""

    def __init__(self, master, on_load: Callable[[str], None], show_title: bool = True):
        super().__init__(master)
        self.on_load = on_load
        self.grid_columnconfigure(1, weight=1)

        # Title
        if show_title:
            title_label = ctk.CTkLabel(self, text=theme.HEADER_TITLE,
                                       font=ctk.CTkFont(size=24, weight="bold"))
            title_label.grid(row=0, column=0, columnspan=3, pady=(10, 15))
        else:
            self.grid_rowconfigure(0, minsize=8)

        # YDKE Code input
        ydke_label = ctk.CTkLabel(self, text="YDKe Code:", font=ctk.CTkFont(size=14))
        ydke_label.grid(row=1, column=0, padx=(15, 5), pady=5, sticky="w")

        self.ydke_entry = ctk.CTkEntry(self, placeholder_text="Paste your ydke code here...",
                                       width=500)
        self.ydke_entry.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        load_ydke_btn = ctk.CTkButton(self, text="Load Deck", width=100,
                                      command=self.load_from_ydke)
        load_ydke_btn.grid(row=1, column=2, padx=(5, 15), pady=5)

        # OR divider
        or_label = ctk.CTkLabel(self, text="— OR —", font=ctk.CTkFont(size=12))
        or_label.grid(row=2, column=0, columnspan=3, pady=5)

        # File selection
        file_label = ctk.CTkLabel(self, text="Load .ydk file:", font=ctk.CTkFont(size=14))
        file_label.grid(row=3, column=0, padx=(15, 5), pady=5, sticky="w")

        # Inline container so file name and Browse button sit next to each other
        file_container = ctk.CTkFrame(self, fg_color="transparent")
        # size to contents and stick to the left so button sits just after filename
        file_container.grid(row=3, column=1, padx=5, pady=5, sticky="w")
        file_container.grid_columnconfigure(0, weight=0)

        self.file_path_label = ctk.CTkLabel(file_container, text="No file selected",
                                            font=ctk.CTkFont(size=12), text_color="gray")
        self.file_path_label.grid(row=0, column=0, sticky="w")

        browse_btn = ctk.CTkButton(file_container, text="Browse...", width=100,
                                   command=self.browse_file)
        # small 5px gap between filename and button
        browse_btn.grid(row=0, column=1, padx=(5, 0), sticky="w")

    def load_from_ydke(self):
        """Load deck from ydke code"""
        ydke_code = self.ydke_entry.get().strip()
        if not ydke_code:
            messagebox.showwarning("Warning", "Please enter a ydke code.", parent=self)
            return

        if not ydke_code.startswith("ydke://"):
            messagebox.showerror("Error", "Invalid format. Code must start with 'ydke://'", parent=self)
            return

        self.on_load(ydke_code)

    def browse_file(self):
        """Browse for a .ydk file"""
        decklists_path = ensure_user_decklists_dir()

        filepath = filedialog.askopenfilename(
            parent=self.winfo_toplevel(),
            title="Select YDK File",
            initialdir=decklists_path,
            filetypes=[("YDK files", "*.ydk"), ("All files", "*.*")]
        )

        if filepath:
            self.file_path_label.configure(text=os.path.basename(filepath))
            with open(filepath, 'r') as f:
                ydk_content = f.read()
            self.on_load(ydk_content)
