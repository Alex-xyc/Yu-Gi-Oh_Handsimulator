"""File-system locations, for both a source checkout and the PyInstaller .exe."""

import os
import sys

PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
# The src/ folder: holds icons/ and decklists/ when running from source
SRC_DIR = os.path.dirname(PACKAGE_DIR)


def is_frozen() -> bool:
    """True when running as a PyInstaller-built executable."""
    return bool(getattr(sys, 'frozen', False))


def bundled_resource(*parts: str) -> str:
    """Path to a file shipped with the app (e.g. icons), inside the .exe bundle if frozen."""
    base = getattr(sys, '_MEIPASS', SRC_DIR) if is_frozen() else SRC_DIR
    return os.path.join(base, *parts)


def user_decklists_dir() -> str:
    """Decklists folder the GUI browses: next to the .exe when frozen, src/decklists otherwise."""
    base = os.path.dirname(sys.executable) if is_frozen() else SRC_DIR
    return os.path.join(base, "decklists")


def source_decklists_dir() -> str:
    """The src/decklists folder (used by the console simulator)."""
    return os.path.join(SRC_DIR, "decklists")
