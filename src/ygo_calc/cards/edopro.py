"""EDOPro (Project Ignis) card databases: the fallback when YGOPRODeck has no entry."""

import logging
import os
import sqlite3
import time
from typing import Dict, List

from . import cache
from .http import fetch_bytes, fetch_json

EDOPRO_CDB_BASE_URL = "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/"
EDOPRO_CDB_FILES = ["cards.cdb", "cards-unofficial.cdb", "prerelease-others.cdb"]
EDOPRO_CDB_LIST_URL = "https://api.github.com/repos/ProjectIgnis/BabelCDB/contents"
EDOPRO_IMAGE_URL = "https://pics.projectignis.org:2096/pics/{card_id}.jpg"
EDOPRO_CACHE_MAX_AGE = 7 * 24 * 60 * 60  # Re-download CDBs weekly
EDOPRO_TYPE_TOKEN = 0x4000


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
            if (name.endswith('.cdb') and name not in names
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
        data = fetch_bytes(EDOPRO_CDB_BASE_URL + name, timeout=60)
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
                    "SELECT t.id, t.name, d.type FROM texts t JOIN datas d ON d.id = t.id "
                    f"WHERE t.id IN ({placeholders})",
                    [int(cid) for cid in missing]
                ).fetchall()
                rows = [(cid, cname, _edopro_token_creator(conn, cid, cname) if ctype & EDOPRO_TYPE_TOKEN else None)
                        for cid, cname, ctype in rows]
            finally:
                conn.close()
        except Exception:
            logging.exception("Failed to read EDOPro database %s", name)
            continue
        for card_id, card_name, creator in rows:
            card_id = str(card_id)
            if creator:
                # Tokens can't be in a deck, so a token ID means the card that makes it
                creator_id, card_name = creator
                cache.aliases[card_id] = creator_id
            result[card_id] = card_name
            cache.names[card_id] = card_name
            cache.image_urls.setdefault(
                card_id, EDOPRO_IMAGE_URL.format(card_id=cache.aliases.get(card_id, card_id)))
        missing = [cid for cid in missing if cid not in result]

    return result
