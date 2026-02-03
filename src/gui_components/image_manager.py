"""Image loading and thumbnail management for the hand simulator.

Provides `load_and_display_image(app, ...)` and `resize_thumbnails(app, ...)`
which operate on the `app` instance (the main `YuGiOhHandSimulator`).

This keeps image-related code out of the main `gui.py` file.
"""

import urllib.request
from io import BytesIO
import logging

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

import customtkinter as ctk


def load_and_display_image(app, url: str, parent_frame, card_name: str, is_sixth: bool = False, target_size: tuple = None):
    """Load image from URL and attach it to `parent_frame`.

    `app` is the main GUI instance and must expose `image_cache`, `orig_images`,
    and `card_image_labels` attributes (as in the original `gui.py`).
    """
    try:
        # Determine target size
        if target_size and isinstance(target_size, tuple) and len(target_size) == 2:
            tw, th = target_size
        else:
            tw, th = (140, 205)

        cache_key = f"{url}|{tw}x{th}"

        if cache_key in app.image_cache:
            img_tk = app.image_cache[cache_key]
        else:
            # Download image
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
            with urllib.request.urlopen(req, timeout=10) as response:
                image_data = response.read()

            if not PIL_AVAILABLE:
                raise RuntimeError("Pillow not available")

            orig = Image.open(BytesIO(image_data)).convert("RGBA")
            app.orig_images[url] = orig

            img = orig.resize((tw, th), Image.Resampling.LANCZOS)
            img_tk = ImageTk.PhotoImage(img)
            app.image_cache[cache_key] = img_tk

        # Create label with image
        label = ctk.CTkLabel(parent_frame, image=img_tk, text="")
        label.image = img_tk
        try:
            label._image_url = url
        except Exception:
            pass
        label.grid(row=0, column=0)
        try:
            label.configure(border_width=1, border_color="#3a3a3a", corner_radius=6)
        except Exception:
            pass
        app.card_image_labels.append(label)

    except Exception as e:
        logging.debug("Image load failed for %s: %s", url, e)
        try:
            tw, th = (tw, th)
        except Exception:
            tw, th = (140, 205)
        label = ctk.CTkLabel(parent_frame, text=card_name[:12], width=tw, height=th,
                             fg_color="gray30", corner_radius=5)
        label.grid(row=0, column=0)


def resize_thumbnails(app, canvas_height: int):
    """Resize all displayed thumbnails to fit the given canvas height.

    Re-uses originals in `app.orig_images` and keeps a size-aware `app.image_cache`.
    """
    try:
        thumb_h = max(100, min(205, canvas_height - 30))
        thumb_w = int(thumb_h * (140 / 205))
    except Exception:
        thumb_w, thumb_h = 140, 205

    for lbl in list(getattr(app, 'card_image_labels', [])):
        url = getattr(lbl, '_image_url', None)
        if not url:
            continue
        cache_key = f"{url}|{thumb_w}x{thumb_h}"
        try:
            if cache_key in app.image_cache:
                img_tk = app.image_cache[cache_key]
            else:
                orig = app.orig_images.get(url)
                if orig is None:
                    continue
                img = orig.resize((thumb_w, thumb_h), Image.Resampling.LANCZOS)
                img_tk = ImageTk.PhotoImage(img)
                app.image_cache[cache_key] = img_tk

            lbl.configure(image=img_tk)
            lbl.image = img_tk
        except Exception:
            continue
