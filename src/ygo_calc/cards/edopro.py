"""EDOPro (Project Ignis) card databases: the fallback when YGOPRODeck has no entry."""

import logging
import os
import re
import sqlite3
import time
from typing import Dict, List

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


def _edopro_cdb_names() -> List[str]:
    """List the BabelCDB databases to search (main card pool plus pre-releases)."""
    names = list(EDOPRO_CDB_FILES)
    try:
        for entry in fetch_json(EDOPRO_CDB_LIST_URL, timeout=10, accept_json=False):
            name = entry.get('name', '') if isinstance(entry, dict) else ''
            # The name becomes a file name here and part of a URL: plain names only
            if (SAFE_CDB_NAME.fullmatch(name) and name not in names
                    and 'rush' not in name and 'skills' not in name):
                names.append(name)
    except Exception:
        logging.exception("Failed to list EDOPro card databases; using defaults")
    return names


def _edopro_cdb_path(name: str) -> str:
    """Return a local path to an EDOPro CDB, downloading it if missing or stale."""
    path = os.path.join(_edopro_cache_dir(), name)
    if os.path.exists(path) and time.time() - os.path.getmtime(path) < EDOPRO_CACHE_MAX_AGE:
        return path
    try:
        if not SAFE_CDB_NAME.fullmatch(name):
            raise ValueError(f"Unexpected database name {name!r}")
        data = fetch_bytes(EDOPRO_CDB_BASE_URL + name, timeout=60, max_bytes=MAX_CDB_BYTES)
        if not data.startswith(b'SQLite format 3\x00'):
            raise ValueError(f"{name} is not a SQLite database")
        with open(path, 'wb') as f:
            f.write(data)
    except Exception:
        logging.exception("Failed to download EDOPro database %s", name)
    return path if os.path.exists(path) else ''


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
