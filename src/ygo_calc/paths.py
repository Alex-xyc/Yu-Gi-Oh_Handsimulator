"""File-system locations, for both a source checkout and the PyInstaller .exe."""

import os
import shutil
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
    """Decklists folder the GUI browses: Documents/YGO-Calc/decklists when frozen, src/decklists otherwise.

    The frozen app may be installed somewhere read-only (e.g. Program Files), so its
    decklists live in the user's Documents folder instead of next to the .exe.
    """
    if not is_frozen():
        return os.path.join(SRC_DIR, "decklists")
    return os.path.join(documents_dir(), "YGO-Calc", "decklists")


def documents_dir() -> str:
    """The user's Documents folder, following Windows redirection (e.g. to OneDrive)."""
    if sys.platform == "win32":
        import ctypes
        buffer = ctypes.create_unicode_buffer(260)
        # CSIDL_PERSONAL (5) is the Documents folder
        if ctypes.windll.shell32.SHGetFolderPathW(None, 5, None, 0, buffer) == 0 and buffer.value:
            return buffer.value
    return os.path.join(os.path.expanduser("~"), "Documents")


def ensure_user_decklists_dir() -> str:
    """Create the user decklists folder if needed, seeding it with the bundled example decks.

    Returns the folder, or the user's home folder if it can't be created.
    """
    path = user_decklists_dir()
    if os.path.isdir(path):
        return path
    try:
        os.makedirs(path)
    except OSError:
        return os.path.expanduser("~")
    bundled = bundled_resource("decklists")
    if is_frozen() and os.path.isdir(bundled):
        for name in os.listdir(bundled):
            if name.lower().endswith(".ydk"):
                try:
                    shutil.copy2(os.path.join(bundled, name), path)
                except OSError:
                    pass
    return path


def source_decklists_dir() -> str:
    """The src/decklists folder (used by the console simulator)."""
    return os.path.join(SRC_DIR, "decklists")
