"""Image manager for downloading, caching, and resizing card thumbnails.

Provides functions to load images (size-aware cache), display them in a frame,
and resize existing thumbnails responsively.
"""
from io import BytesIO
from typing import Any, Optional, Tuple
import urllib.request
import logging

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False

import customtkinter as ctk
import tkinter as tk


def _download_image(url: str) -> Optional[Image.Image]:
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 YGO-Calculator/1.0')
        with urllib.request.urlopen(req, timeout=10) as response:
            image_data = response.read()
        img = Image.open(BytesIO(image_data)).convert("RGBA")
        return img
    except Exception:
        logging.exception("Failed to download image: %s", url)
        return None


def load_image_for_size(url: str, target_size: Tuple[int, int], app: Any) -> Optional[ImageTk.PhotoImage]:
    """Return a PhotoImage for the given url and size, using app caches.

    Expects the `app` to have `image_cache` (dict) and `orig_images` (dict).
    """
    if not PIL_AVAILABLE:
        return None

    tw, th = target_size
    cache_key = f"{url}|{tw}x{th}"
    try:
        if cache_key in app.image_cache:
            return app.image_cache[cache_key]

        # Ensure we have the original image
        orig = app.orig_images.get(url)
        if orig is None:
            orig = _download_image(url)
            if orig is None:
                return None
            app.orig_images[url] = orig

        img = orig.resize((tw, th), Image.Resampling.LANCZOS)
        img_tk = ImageTk.PhotoImage(img)
        app.image_cache[cache_key] = img_tk
        return img_tk
    except Exception:
        logging.exception("Error building thumbnail for %s", url)
        return None


def display_image_in_frame(url: str, target_size: Tuple[int, int], parent_frame: Any, card_name: str, app: Any, is_sixth: bool = False):
    """Create and grid a label with the image in parent_frame.

    Falls back to a text placeholder on failure.
    Returns the created label.
    """
    img_tk = load_image_for_size(url, target_size, app)
    tw, th = target_size
    if img_tk:
        try:
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
            return label
        except Exception:
            pass

    # Fallback placeholder
    try:
        label = ctk.CTkLabel(parent_frame, text=card_name[:12], width=tw, height=th,
                             fg_color="gray30", corner_radius=5)
        label.grid(row=0, column=0)
        return label
    except Exception:
        lbl = tk.Label(parent_frame, text=card_name[:12], width=tw, height=th, bg="gray30")
        lbl.grid(row=0, column=0)
        return lbl


def resize_thumbnails_for_canvas_height(canvas_height: int, app: Any):
    """Resize displayed thumbnails based on canvas height (responsive).

    Uses the same clamp logic as the GUI: thumb_h in [100, 205].
    """
    if not PIL_AVAILABLE:
        return

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

            # Update label image
            try:
                lbl.configure(image=img_tk)
                lbl.image = img_tk
            except Exception:
                pass
        except Exception:
            continue
