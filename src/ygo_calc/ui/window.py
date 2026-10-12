"""Window-level helpers: taskbar identity, icon, default size, and CTk tweaks."""

import ctypes
import logging
import os
import sys
import tkinter as tk
from typing import Callable, Tuple

import customtkinter as ctk

from ..paths import bundled_resource
from . import theme
from .image_loader import PIL_AVAILABLE

if PIL_AVAILABLE:
    from PIL import Image, ImageTk


def window_scaling(widget) -> float:
    """CTk's DPI scaling factor for a window or widget (1.0 if unknown)."""
    try:
        if isinstance(widget, ctk.CTk):
            return ctk.ScalingTracker.get_window_scaling(widget)
        return ctk.ScalingTracker.get_widget_scaling(widget)
    except Exception:
        return 1.0


def set_app_user_model_id() -> None:
    """On Windows, set an explicit AppUserModelID before creating windows so
    the taskbar associates our process with the application icon."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(theme.APP_USER_MODEL_ID)
        except Exception as e:
            logging.debug("Failed to set AppUserModelID: %s", e)


def apply_window_icon(window: tk.Tk) -> None:
    """Load the app icon (prefer .ico on Windows, also set an iconphoto so the
    taskbar uses the same image)."""
    try:
        icon_path = bundled_resource(*theme.ICON_FILE)
        if not os.path.exists(icon_path):
            alt_path = os.path.splitext(icon_path)[0] + ".ic"
            if os.path.exists(alt_path):
                icon_path = alt_path

        if os.path.exists(icon_path):
            # Primary: set iconbitmap (Windows)
            try:
                window.iconbitmap(icon_path)
            except Exception as e:
                logging.debug("iconbitmap failed: %s", e)

            # Secondary: set an iconphoto (some environments/taskbars prefer this)
            try:
                if PIL_AVAILABLE:
                    img = Image.open(icon_path).convert("RGBA")
                    img = img.resize((64, 64), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(img)
                    window.iconphoto(True, tk_img)
                    # keep reference to avoid GC
                    window._icon_img = tk_img
                else:
                    png_path = os.path.splitext(icon_path)[0] + ".png"
                    if os.path.exists(png_path):
                        png_img = tk.PhotoImage(file=png_path)
                        window.iconphoto(True, png_img)
                        window._icon_img = png_img
            except Exception:
                logging.exception("Failed to load icon image")
    except Exception:
        logging.exception("Unexpected error while setting application icon")


def set_default_geometry(window: ctk.CTk, default_size: Tuple[int, int], min_size: Tuple[int, int],
                         maximize: Callable[[], None]) -> None:
    """Open centred at default_size, or maximized if the screen is too small for it."""
    scale = window_scaling(window)
    screen_w = int(window.winfo_screenwidth() / scale)
    screen_h = int(window.winfo_screenheight() / scale)
    # Leave room for the title bar and taskbar
    avail_w, avail_h = screen_w - 40, screen_h - 80
    width, height = default_size

    window.minsize(min(min_size[0], avail_w), min(min_size[1], avail_h))
    if width <= avail_w and height <= avail_h:
        x = (screen_w - width) // 2
        y = max(0, (screen_h - height) // 2 - 20)
        window.geometry(f"{width}x{height}+{x}+{y}")
    else:
        window.geometry(f"{min(width, avail_w)}x{min(height, avail_h)}+20+20")
        # CTk applies its own startup geometry, so maximize once the window is up
        window.after(0, maximize)


def maximize(window: tk.Tk) -> None:
    try:
        window.state("zoomed")  # Windows / macOS
    except tk.TclError:
        try:
            window.attributes("-zoomed", True)  # Linux (X11)
        except tk.TclError:
            pass


def lighten_scrollbar(scrollbar: ctk.CTkScrollbar) -> None:
    """Stop a CTkScrollbar forcing a full layout pass on every scroll update.

    CTkScrollbar._draw() ends with canvas.update_idletasks(), and the attached text box
    calls set() -> _draw() whenever its view changes, so every resize step processed the
    whole window's pending layout synchronously (100-400ms). Tk redraws on idle anyway.
    """
    canvas = getattr(scrollbar, "_canvas", None)
    if canvas is not None:
        canvas.update_idletasks = lambda: None
