"""Two side-by-side panels with a draggable divider between them.

While dragging, a greyed-out preview of both panels (no content) is drawn at the target
size; the real panels are resized once on release. Re-laying out the real panels (cards,
text, CTk frames) on every motion event costs ~100ms each, which made the drag stutter,
while redrawing a few preview shapes is instant.
"""

import tkinter as tk

import customtkinter as ctk

from . import theme
from .window import window_scaling


class SplitView(ctk.CTkFrame):
    """Holds a left and right panel; the divider sets the left panel's width.

    Panels may define preview_parts() -> widgets to draw inside them in the drag preview.
    """

    def __init__(self, master, left_ratio: float = 0.52, min_left: int = 380, min_right: int = 320):
        super().__init__(master, fg_color=theme.WINDOW_BG)
        self.left_ratio = left_ratio
        scale = window_scaling(master)
        self.min_left, self.min_right = int(min_left * scale), int(min_right * scale)
        self._preview_radius = int(theme.PANEL_CORNER_RADIUS * scale)
        self._drag = {'dragging': False, 'start_x': 0, 'start_left': 0}
        self.left = None
        self.right = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=0)  # Width set from the divider position
        self.grid_columnconfigure(1, weight=0, minsize=8)
        self.grid_columnconfigure(2, weight=1)

        # Invisible divider (no visible line) but still acts as a draggable handle
        self.divider = tk.Frame(self, bg=theme.WINDOW_BG, width=8, cursor="sb_h_double_arrow")
        self.divider.grid(row=0, column=1, sticky="ns", pady=6)
        self.divider.bind("<ButtonPress-1>", self._on_press)
        self.divider.bind("<ButtonRelease-1>", self._on_release)
        self.divider.bind("<B1-Motion>", self._on_motion)

        self.preview = tk.Canvas(self, bg=theme.WINDOW_BG, highlightthickness=0, bd=0,
                                 cursor="sb_h_double_arrow")
        self.bind('<Configure>', self._on_configure)

    def set_panels(self, left: tk.Widget, right: tk.Widget) -> None:
        """Place the two panels (both must be created with this view as their master)."""
        self.left, self.right = left, right
        left.grid(row=0, column=0, sticky="nsew", padx=(6, 2), pady=6)
        right.grid(row=0, column=2, sticky="nsew", padx=(2, 6), pady=6)

    # Sizing

    def _left_column_width(self) -> int:
        # Width of the whole column (panel + its padding), which is what minsize sets
        return self.grid_bbox(0, 0)[2]

    def _clamp_left_width(self, left_w) -> int:
        total_w = self.winfo_width()
        max_left = max(self.min_left, total_w - self.min_right - self.divider.winfo_width())
        return int(max(self.min_left, min(left_w, max_left)))

    def _apply_left_width(self, left_w) -> None:
        """Set the left panel width, keeping both panels above their minimum width."""
        if self.winfo_width() <= 1:
            return
        left_w = self._clamp_left_width(left_w)
        # Only touch the grid when the width changes: re-applying it makes the
        # CTk frame fire <Configure> again, which would loop forever
        if int(self.grid_columnconfigure(0, "minsize")) != left_w:
            self.grid_columnconfigure(0, minsize=left_w)

    def _on_configure(self, _event) -> None:
        # Re-apply the split ratio only when the width actually changed
        width = self.winfo_width()
        if not self._drag['dragging'] and width != self._drag.get('last_total'):
            self._drag['last_total'] = width
            self._apply_left_width(width * self.left_ratio)

    # Dragging

    def _on_press(self, event) -> None:
        self._drag['dragging'] = True
        self._drag['start_x'] = event.x_root
        self._drag['start_left'] = self._left_column_width()
        self._drag['target'] = self._left_column_width()
        self._start_preview()
        self._draw_preview(self._drag['target'])

    def _on_motion(self, event) -> None:
        if self._drag['dragging']:
            dx = event.x_root - self._drag['start_x']
            self._drag['target'] = self._clamp_left_width(self._drag['start_left'] + dx)
            self._draw_preview(self._drag['target'])

    def _on_release(self, _event) -> None:
        if not self._drag['dragging']:
            return
        self._drag['dragging'] = False
        self.preview.place_forget()
        self.preview.delete("all")
        target = self._drag['target']
        self._apply_left_width(target)
        total_w = self.winfo_width()
        if total_w > 1:
            # Remember the split as a ratio so it's kept when the window is resized
            self.left_ratio = max(0.1, min(0.9, target / total_w))

    # Greyed-out preview

    def _box(self, widget: tk.Widget):
        """Widget's (x, y, width, height) relative to this view."""
        return (widget.winfo_rootx() - self.winfo_rootx(),
                widget.winfo_rooty() - self.winfo_rooty(),
                widget.winfo_width(), widget.winfo_height())

    def _parts(self, panel):
        return [self._box(w) for w in getattr(panel, "preview_parts", lambda: [])()]

    def _start_preview(self) -> None:
        # Snapshot the current panel layout; the preview stretches it horizontally
        self._drag['layout'] = {
            'left': self._box(self.left),
            'left_parts': self._parts(self.left),
            'right': self._box(self.right),
            'right_parts': self._parts(self.right),
        }
        self.preview.place(x=0, y=0, relwidth=1, relheight=1)
        tk.Misc.tkraise(self.preview)  # Canvas.lift() raises canvas items, not the widget

    def _rounded_rect(self, x1, y1, x2, y2, r, **kwargs) -> None:
        r = max(0, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        points = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2,
                  x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        self.preview.create_polygon(points, smooth=True, **kwargs)

    def _draw_preview(self, left_w) -> None:
        layout = self._drag['layout']
        delta = left_w - self._drag['start_left']
        self.preview.delete("all")
        panel = {"fill": theme.PREVIEW_PANEL_FILL, "outline": theme.PREVIEW_PANEL_OUTLINE, "width": 1}
        part = {"fill": theme.PREVIEW_PART_FILL, "outline": ""}

        # Left panel grows/shrinks with the divider; its parts stretch with it
        x, y, w, h = layout['left']
        self._rounded_rect(x, y, x + w + delta, y + h, self._preview_radius, **panel)
        for px, py, pw, ph in layout['left_parts']:
            self.preview.create_rectangle(px, py, px + pw + delta, py + ph, **part)

        # Right panel moves with the divider and takes the remaining width
        x, y, w, h = layout['right']
        self._rounded_rect(x + delta, y, x + w, y + h, self._preview_radius, **panel)
        for px, py, pw, ph in layout['right_parts']:
            self.preview.create_rectangle(px + delta, py, px + pw, py + ph, **part)
