"""Layout manager: creates the container and draggable divider and
exposes a helper to register divider handlers.

This keeps divider and resizing logic out of `gui.py`.
"""
from typing import Any, Tuple
import customtkinter as ctk
import tkinter as tk
import tkinter.font as tkfont

# Hand panel minimum (unscaled px); cards scroll horizontally below this
MIN_LEFT_WIDTH = 360
# Widest line in the stats text (matrix / probability tables), in characters
STATS_TEXT_COLUMNS = 56
DIVIDER_COLOR = "#242424"
DIVIDER_HOVER_COLOR = "#4a4a4a"


def _scaling(app: Any) -> float:
    try:
        return ctk.ScalingTracker.get_widget_scaling(app)
    except Exception:
        return 1.0


def _min_right_width(app: Any) -> int:
    """Smallest stats panel width that still shows a full table line."""
    scale = _scaling(app)
    try:
        # CTkFont(size=12) renders as a -12px font scaled by widget scaling
        font = tkfont.Font(family="Consolas", size=-round(12 * scale))
        text_w = font.measure("0" * STATS_TEXT_COLUMNS)
    except Exception:
        text_w = int(STATS_TEXT_COLUMNS * 9 * scale)
    # textbox padding + scrollbar + frame border/padding
    return text_w + int(60 * scale)


def create_container(app: Any) -> Tuple[Any, Any]:
    """Create the main container frame and a divider frame.

    Returns (container, divider).
    """
    bg_color = getattr(app, 'bg_color', '#242424')
    container = ctk.CTkFrame(app, fg_color=bg_color)
    container.grid(row=2, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")
    app.grid_rowconfigure(2, weight=1)
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=0)
    container.grid_columnconfigure(1, weight=0, minsize=8)
    container.grid_columnconfigure(2, weight=1)

    divider = tk.Frame(container, bg=DIVIDER_COLOR, width=8, cursor="sb_h_double_arrow")
    divider.grid(row=0, column=1, sticky="ns", pady=6)

    return container, divider


def register_divider_handlers(container: Any, divider: Any, hand_frame: Any, app: Any,
                              initial_left_ratio: float = 0.52):
    """Attach drag handlers and container resize behavior.

    The left (hand) column gets an explicit width; the right (stats) column
    takes the rest but never less than its minimum. The split is kept as a
    ratio in `app._left_ratio` so it survives window resizes.
    """
    app._divider_drag = {'dragging': False, 'start_x': 0, 'start_left': 0}
    app._left_ratio = float(initial_left_ratio)

    min_left = int(MIN_LEFT_WIDTH * _scaling(app))
    min_right = _min_right_width(app)
    container.grid_columnconfigure(0, weight=0)
    container.grid_columnconfigure(2, weight=1, minsize=min_right)

    def _total_width() -> int:
        return container.winfo_width() or app.winfo_width() or 1200

    def _clamp(left: float, total: int) -> int:
        max_left = total - min_right - divider.winfo_width()
        # If the window is too narrow for both minimums, the hand panel wins
        return int(max(min_left, min(left, max_left)))

    def _set_left(left: int) -> None:
        container.grid_columnconfigure(0, minsize=left)

    def _on_divider_press(event):
        app._divider_drag['dragging'] = True
        app._divider_drag['start_x'] = event.x_root
        try:
            app._divider_drag['start_left'] = container.grid_bbox(0, 0)[2]
        except Exception:
            app._divider_drag['start_left'] = hand_frame.winfo_width()

    def _on_divider_motion(event):
        if not app._divider_drag['dragging']:
            return
        total = _total_width()
        dx = event.x_root - app._divider_drag['start_x']
        new_left = _clamp(app._divider_drag['start_left'] + dx, total)
        _set_left(new_left)
        app._left_ratio = new_left / total

    def _on_divider_release(event):
        app._divider_drag['dragging'] = False
        divider.configure(bg=DIVIDER_COLOR)

    def _on_container_configure(event):
        total = _total_width()
        _set_left(_clamp(total * app._left_ratio, total))

    divider.bind("<ButtonPress-1>", _on_divider_press)
    divider.bind("<B1-Motion>", _on_divider_motion)
    divider.bind("<ButtonRelease-1>", _on_divider_release)
    divider.bind("<Enter>", lambda e: divider.configure(bg=DIVIDER_HOVER_COLOR))
    divider.bind("<Leave>", lambda e: None if app._divider_drag['dragging']
                 else divider.configure(bg=DIVIDER_COLOR))
    container.bind('<Configure>', _on_container_configure)

    try:
        app.update_idletasks()
        _on_container_configure(None)
    except Exception:
        pass
