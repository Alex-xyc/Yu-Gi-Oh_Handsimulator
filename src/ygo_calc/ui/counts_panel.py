"""Middle section: brick / non-engine / engine counts, action buttons and deck status."""

from typing import Callable, List, Optional, Tuple

import customtkinter as ctk

from ..core.categories import BRICK, ENGINE, NON_ENGINE, UNTAGGED


class CountsPanel(ctk.CTkFrame):
    """Count entries plus the "Apply & Draw Hand" and "Show Decklist" buttons."""

    def __init__(self, master, on_apply: Callable[[], None], on_show_decklist: Callable[[], None],
                 on_locked_click: Callable[[ctk.CTkEntry], None]):
        super().__init__(master)
        self.on_locked_click = on_locked_click
        # Create extra columns so we can center the inputs on wide screens
        for i in range(9):
            self.grid_columnconfigure(i, weight=0)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(8, weight=1)

        # Instructions (centered under title)
        instr_label = ctk.CTkLabel(self, text="Specify card counts:",
                                   font=ctk.CTkFont(size=16, weight="bold"))
        instr_label.grid(row=0, column=0, columnspan=9, pady=(10, 5))

        desc_label = ctk.CTkLabel(
            self,
            text="Bricks = cards you don't want to draw  |  Non-Engine = handtraps & board breakers  |  Engine = combo pieces",
            font=ctk.CTkFont(size=12), text_color="gray")
        desc_label.grid(row=1, column=0, columnspan=9, pady=(0, 10))

        # Inputs row centered using inner columns 1..6
        self.brick_entry = self._count_entry("Bricks:", column=1)
        self.non_engine_entry = self._count_entry("Non-Engine:", column=3)
        self.engine_entry = self._count_entry("Engine:", column=5)
        self._entries = {BRICK: self.brick_entry, NON_ENGINE: self.non_engine_entry,
                         ENGINE: self.engine_entry}

        # Apply and Show Decklist buttons placed next to Engine input (column 7)
        buttons_frame = ctk.CTkFrame(self, fg_color="transparent")
        buttons_frame.grid(row=2, column=7, padx=(10, 20), pady=10)
        self.draw_btn = ctk.CTkButton(buttons_frame, text="Apply & Draw Hand", width=165,
                                      command=on_apply, state="disabled",
                                      font=ctk.CTkFont(size=14, weight="bold"),
                                      fg_color="green", hover_color="darkgreen")
        self.draw_btn.grid(row=0, column=0)
        self.advanced_btn = ctk.CTkButton(buttons_frame, text="Show Decklist", width=110,
                                          command=on_show_decklist, state="disabled",
                                          font=ctk.CTkFont(size=14, weight="bold"))
        self.advanced_btn.grid(row=0, column=1, padx=(10, 0))

        # Deck info label, centered across the input area
        self.deck_info_label = ctk.CTkLabel(self, text="No deck loaded",
                                            font=ctk.CTkFont(size=13), text_color="orange")
        self.deck_info_label.grid(row=3, column=0, columnspan=9, pady=(0, 8))

    def _count_entry(self, label_text: str, column: int) -> ctk.CTkEntry:
        label = ctk.CTkLabel(self, text=label_text, font=ctk.CTkFont(size=15))
        label.grid(row=2, column=column, padx=(10, 5), pady=10)
        entry = ctk.CTkEntry(self, width=80, placeholder_text="0", font=ctk.CTkFont(size=14))
        entry.grid(row=2, column=column + 1, padx=5, pady=10)
        entry.bind("<Button-1>", lambda _e: self._on_entry_click(entry))
        return entry

    def _on_entry_click(self, entry: ctk.CTkEntry):
        # Entries are only locked while decklist tags are in use
        if entry.cget("state") == "disabled":
            self.on_locked_click(entry)

    def get_counts(self) -> Tuple[int, int, int]:
        """(bricks, non-engine, engine) as typed; raises ValueError for non-numbers."""
        return (int(self.brick_entry.get() or 0),
                int(self.non_engine_entry.get() or 0),
                int(self.engine_entry.get() or 0))

    def set_status(self, text: str, color: str) -> None:
        self.deck_info_label.configure(text=text, text_color=color)

    def enable_actions(self) -> None:
        self.draw_btn.configure(state="normal")
        self.advanced_btn.configure(state="normal")

    def show_tags(self, tags: Optional[List[str]]) -> None:
        """With tags: show the tagged totals and lock the entries. Without: unlock them."""
        for key, entry in self._entries.items():
            entry.configure(state="normal")
            if tags is not None:
                entry.delete(0, "end")
                if tags.count(key):  # Leave 0 empty so it shows the greyed-out placeholder
                    entry.insert(0, str(tags.count(key)))
                entry.configure(state="disabled")

    def reset_counts(self) -> None:
        """Empty every count entry (an empty entry shows the greyed-out 0 and counts as 0)."""
        for entry in self._entries.values():
            entry.configure(state="normal")
            entry.delete(0, "end")

    def show_deck_loaded(self, deck_size: int, tags: Optional[List[str]]) -> None:
        text = f"✓ Deck loaded: {deck_size} cards"
        if tags is not None:
            text += "  |  Using decklist tags"
            untagged = tags.count(UNTAGGED)
            if untagged:
                text += f" ({untagged} untagged)"
            text += " - click a count to switch to typed counts"
        self.set_status(text, "lightgreen")
