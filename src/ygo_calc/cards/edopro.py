"""EDOPro (Project Ignis) card databases: the fallback when YGOPRODeck has no entry."""

import logging
import os
import re
import shutil
import sqlite3
import threading
import time
from typing import Dict, List, Tuple

from . import cache
from .http import fetch_bytes, fetch_json

EDOPRO_CDB_BASE_URL = "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/"
EDOPRO_CDB_FILES = ["cards.cdb", "cards-unofficial.cdb", "prerelease-others.cdb"]
EDOPRO_CDB_LIST_URL = "https://api.github.com/repos/ProjectIgnis/BabelCDB/contents"
EDOPRO_IMAGE_URL = "https://pics.projectignis.org:2096/pics/{card_id}.jpg"
# Database file names from the listing: letters, digits, "-", "_" and "." only, ending in .cdb
SAFE_CDB_NAME = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9_.-]{0,99}\.cdb")
# The largest database we'll download (the real ones are a few to tens of megabytes)
MAX_CDB_BYTES = 200 * 1024 * 1024
EDOPRO_CACHE_MAX_AGE = 7 * 24 * 60 * 60  # Re-download CDBs weekly
EDOPRO_TYPE_TOKEN = 0x4000
EDOPRO_TYPE_MONSTER, EDOPRO_TYPE_SPELL, EDOPRO_TYPE_TRAP = 0x1, 0x2, 0x4
# Spell / trap subtype bits
EDOPRO_SUBTYPES = ((0x10000, "quick_play"), (0x20000, "continuous"), (0x40000, "equip"),
                   (0x80000, "field"), (0x80, "ritual"), (0x100000, "counter"))


def _edopro_info(card_type: int, level: int) -> dict:
    """A card's kind (monster, spell_<subtype>, trap_<subtype>) and level from its EDOPro type bits."""
    if card_type & (EDOPRO_TYPE_SPELL | EDOPRO_TYPE_TRAP):
        base = "spell" if card_type & EDOPRO_TYPE_SPELL else "trap"
        subtype = next((name for bit, name in EDOPRO_SUBTYPES if card_type & bit), "normal")
        return {"kind": f"{base}_{subtype}", "level": 0}
    if card_type & EDOPRO_TYPE_MONSTER:
        # The low byte is the level; the rest holds the pendulum scales
        return {"kind": "monster", "level": level & 0xff}
    return {"kind": "", "level": 0}


def _edopro_cache_dir() -> str:
    """Directory where downloaded EDOPro card databases are kept."""
    base = os.environ.get('LOCALAPPDATA') or os.path.join(os.path.expanduser('~'), '.cache')
    path = os.path.join(base, 'YGO-Calc', 'edopro')
    os.makedirs(path, exist_ok=True)
    return path


# The database listing is asked for at most this often (GitHub allows 60 unauthenticated API
# requests an hour), and a database that failed to download isn't tried again for RETRY_SECONDS
LIST_MAX_AGE = 6 * 60 * 60
RETRY_SECONDS = 10 * 60

# (when the listing should be asked for again, the database names)
_names_cache: Tuple[float, List[str]] = (0.0, [])
_download_lock = threading.Lock()
_failed_at: Dict[str, float] = {}


def _edopro_cdb_names() -> List[str]:
    """List the BabelCDB databases to search (main card pool plus pre-releases)."""
    global _names_cache
    expires, cached = _names_cache
    if cached and time.monotonic() < expires:
        return list(cached)
    names = list(EDOPRO_CDB_FILES)
    max_age = LIST_MAX_AGE
    try:
        for entry in fetch_json(EDOPRO_CDB_LIST_URL, timeout=10, accept_json=False):
            name = entry.get('name', '') if isinstance(entry, dict) else ''
            # The name becomes a file name here and part of a URL: plain names only
            if (SAFE_CDB_NAME.fullmatch(name) and name not in names
                    and 'rush' not in name and 'skills' not in name):
                names.append(name)
    except Exception:
        logging.exception("Failed to list EDOPro card databases; using defaults")
        # The defaults for now; ask again sooner
        max_age = RETRY_SECONDS
    _names_cache = (time.monotonic() + max_age, names)
    return list(names)


def _edopro_store_dir() -> str:
    """Where downloaded databases are also kept so they outlive the server: $YGO_CACHE_DIR/edopro
    (on Cloud Run the Cloud Storage bucket, while the databases are used from the container's own
    /tmp, as SQLite needs file locking the bucket mount doesn't have). "" when there's no such
    folder, or it's the folder the databases are used from anyway."""
    base = os.environ.get('YGO_CACHE_DIR')
    if not base:
        return ''
    path = os.path.join(base, 'edopro')
    if os.path.normcase(os.path.abspath(path)) == os.path.normcase(os.path.abspath(_edopro_cache_dir())):
        return ''
    os.makedirs(path, exist_ok=True)
    return path


def _is_fresh(path: str) -> bool:
    return os.path.exists(path) and time.time() - os.path.getmtime(path) < EDOPRO_CACHE_MAX_AGE


def _copy_into_place(source: str, target: str):
    """Copy a file (keeping its modified time, which says how old the database is) beside the
    target and then swap it in, so nobody reads a half-written database."""
    temp = f"{target}.{threading.get_ident()}.part"
    try:
        shutil.copy2(source, temp)
        os.replace(temp, target)
    except BaseException:
        try:
            os.remove(temp)
        except OSError:
            pass
        raise


def _edopro_cdb_path(name: str) -> str:
    """Return a local path to an EDOPro CDB: the local copy, else the stored one (see
    _edopro_store_dir), else downloaded (and stored). A stale copy is used if a new one
    can't be had."""
    # The name becomes part of file paths and a URL: plain names only
    if not SAFE_CDB_NAME.fullmatch(name):
        logging.error("Unexpected EDOPro database name %r", name)
        return ''
    path = os.path.join(_edopro_cache_dir(), name)
    if _is_fresh(path):
        return path
    # One at a time (the databases are large), and no download while a recent one failed
    with _download_lock:
        if _is_fresh(path):
            return path
        store = _edopro_store_dir()
        stored = os.path.join(store, name) if store else ''
        if stored and _is_fresh(stored):
            try:
                _copy_into_place(stored, path)
                return path
            except OSError:
                logging.exception("Failed to copy stored EDOPro database %s; downloading it", name)
        if time.monotonic() - _failed_at.get(name, -RETRY_SECONDS) >= RETRY_SECONDS:
            _download_cdb(name, path, stored)
        if not os.path.exists(path) and stored and os.path.exists(stored):
            # Couldn't get a fresh one: an old one beats none
            try:
                _copy_into_place(stored, path)
            except OSError:
                logging.exception("Failed to copy stored EDOPro database %s", name)
    return path if os.path.exists(path) else ''


def _download_cdb(name: str, path: str, stored: str):
    """Download a database to path, and keep a copy at stored (if given)."""
    temp = f"{path}.{threading.get_ident()}.part"
    try:
        data = fetch_bytes(EDOPRO_CDB_BASE_URL + name, timeout=60, max_bytes=MAX_CDB_BYTES)
        if not data.startswith(b'SQLite format 3\x00'):
            raise ValueError(f"{name} is not a SQLite database")
        # Written beside it and then swapped in, so nobody reads a half-written database
        with open(temp, 'wb') as f:
            f.write(data)
        os.replace(temp, path)
        _failed_at.pop(name, None)
    except Exception:
        logging.exception("Failed to download EDOPro database %s", name)
        _failed_at[name] = time.monotonic()
        try:
            os.remove(temp)
        except OSError:
            pass
        return
    if stored:
        # Not in the background: on Cloud Run a request's CPU is cut back once it has been
        # answered, which could leave the copy half done
        try:
            _copy_into_place(path, stored)
        except OSError:
            logging.exception("Failed to store EDOPro database %s", name)


def _edopro_token_creator(conn: sqlite3.Connection, token_id: int, token_name: str):
    """Find the card that creates a token: by convention its ID is the token's ID - 1.

    Returns (creator_id, creator_name), or None if the neighbouring card doesn't
    mention the token in its text.
    """
    row = conn.execute("SELECT id, name, desc FROM texts WHERE id = ?", (token_id - 1,)).fetchone()
    if row and token_name.lower() in (row[2] or '').lower():
        return str(row[0]), row[1]
    return None


def fetch_edopro_card_names(card_ids: List[str]) -> Dict[str, str]:
    """Look up card names in EDOPro's databases (fallback for YGOPRODeck misses).

    Found cards also get an EDOPro image URL cached for them.
    """
    result: Dict[str, str] = {}
    missing = [cid for cid in card_ids if cid.isdigit()]
    if not missing:
        return result

    for name in _edopro_cdb_names():
        if not missing:
            break
        path = _edopro_cdb_path(name)
        if not path:
            continue
        try:
            conn = sqlite3.connect(path)
            try:
                placeholders = ",".join("?" * len(missing))
                rows = conn.execute(
                    "SELECT t.id, t.name, d.type, d.level FROM texts t JOIN datas d ON d.id = t.id "
                    f"WHERE t.id IN ({placeholders})",
                    [int(cid) for cid in missing]
                ).fetchall()
                rows = [(cid, cname, _edopro_token_creator(conn, cid, cname) if ctype & EDOPRO_TYPE_TOKEN else None,
                         _edopro_info(ctype, clevel))
                        for cid, cname, ctype, clevel in rows]
            finally:
                conn.close()
        except Exception:
            logging.exception("Failed to read EDOPro database %s", name)
            continue
        for card_id, card_name, creator, info in rows:
            card_id = str(card_id)
            if creator:
                # Tokens can't be in a deck, so a token ID means the card that makes it
                creator_id, card_name = creator
                cache.aliases[card_id] = creator_id
            else:
                cache.info.setdefault(card_id, info)
            result[card_id] = card_name
            cache.names[card_id] = card_name
            cache.image_urls.setdefault(
                card_id, EDOPRO_IMAGE_URL.format(card_id=cache.aliases.get(card_id, card_id)))
        missing = [cid for cid in missing if cid not in result]

    return result
