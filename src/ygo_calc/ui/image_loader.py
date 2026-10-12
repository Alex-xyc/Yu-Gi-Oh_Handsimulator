"""Downloading card images and keeping resized copies for display."""

from io import BytesIO
from typing import Dict

from ..cards.http import fetch_bytes

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


class ImageLoader:
    """Downloads each image once and serves resized PhotoImages of it."""

    def __init__(self):
        self._originals: Dict[str, 'Image.Image'] = {}  # Original PIL images by URL
        self._photos: Dict[str, 'ImageTk.PhotoImage'] = {}  # Resized images (keyed by url|WxH)

    def download(self, url: str) -> 'Image.Image':
        """Download an image (or reuse a cached one) as a PIL image. Safe to call off the Tk thread."""
        orig = self._originals.get(url)
        if orig is None:
            image_data = fetch_bytes(url, timeout=10)
            # Open original PIL image and store it for future resizes
            orig = Image.open(BytesIO(image_data)).convert("RGBA")
            self._originals[url] = orig
        return orig

    def photo(self, url: str, width: int, height: int) -> 'ImageTk.PhotoImage':
        """Download (or reuse) an image and return it resized as a PhotoImage."""
        # Use cache key that includes size to avoid mismatched thumbnail sizes
        cache_key = f"{url}|{width}x{height}"
        if cache_key in self._photos:
            return self._photos[cache_key]

        orig = self.download(url)
        img_tk = ImageTk.PhotoImage(orig.resize((width, height), Image.Resampling.LANCZOS))
        # Drop other sizes of this image so resizing the window doesn't grow the cache
        prefix = f"{url}|"
        for key in [k for k in self._photos if k.startswith(prefix)]:
            del self._photos[key]
        self._photos[cache_key] = img_tk
        return img_tk
