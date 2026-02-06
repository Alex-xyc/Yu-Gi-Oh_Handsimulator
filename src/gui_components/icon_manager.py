import os
import sys
import logging
import tkinter as tk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


def set_app_icon(app):
    """Set application icon (tries .ico and falls back to .png)."""
    try:
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            base_path = sys._MEIPASS
        else:
            base_path = os.path.dirname(__file__)

        # icons/ is located one directory up from this components package
        icon_path = os.path.join(os.path.dirname(base_path), "icons", "ghattic.ico")
        if not os.path.exists(icon_path):
            alt_path = os.path.join(os.path.dirname(base_path), "icons", "ghattic.ic")
            if os.path.exists(alt_path):
                icon_path = alt_path

        if os.path.exists(icon_path):
            try:
                app.iconbitmap(icon_path)
            except Exception as e:
                logging.debug("iconbitmap failed: %s", e)

            try:
                if PIL_AVAILABLE:
                    img = Image.open(icon_path).convert("RGBA")
                    img = img.resize((64, 64), Image.LANCZOS)
                    tk_img = ImageTk.PhotoImage(img)
                    app.iconphoto(True, tk_img)
                    app._icon_img = tk_img
                else:
                    png_path = os.path.splitext(icon_path)[0] + ".png"
                    if os.path.exists(png_path):
                        png_img = tk.PhotoImage(file=png_path)
                        app.iconphoto(True, png_img)
                        app._icon_img = png_img
            except Exception:
                logging.exception("Failed to load icon image")
    except Exception:
        logging.exception("Unexpected error while setting application icon")
