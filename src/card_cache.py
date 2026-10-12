"""Local on-disk cache for card data and card images.

The full YGOPRODeck card database is downloaded once (one request) and
stored as a compact id -> {name, image} index. Card images are saved to
disk the first time they are needed, so each image is only ever fetched
from the API once.

Some passcodes used by deck files are not in YGOPRODeck (alternate-art ids
it doesn't list, tokens, very new cards). For those, EDOPro's card database
(ProjectIgnis/BabelCDB) is downloaded on demand and used as a fallback.

Cache location: %LOCALAPPDATA%/YGO-Hand-Simulator (Windows) or
~/.cache/ygo-hand-simulator, overridable with the YGO_CACHE_DIR env var.
"""
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.request
import html
import re
from io import BytesIO
from typing import Dict, Iterable, Optional
from urllib.parse import urlparse

API_ALL_CARDS = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
API_DB_VERSION = "https://db.ygoprodeck.com/api/v7/checkDBVer.php"
USER_AGENT = 'Mozilla/5.0 YGO-Calculator/1.0'

# Re-check the remote database version at most this often
DB_CHECK_INTERVAL = 24 * 60 * 60
# YGOPRODeck allows 20 requests/second; stay well below it
MIN_REQUEST_GAP = 0.1
# Only ever contact YGOPRODeck, over HTTPS
ALLOWED_HOSTS = {'db.ygoprodeck.com', 'images.ygoprodeck.com',
                 'raw.githubusercontent.com', 'pics.projectignis.org'}
# Response size caps (full card list is ~21 MB, a small card image ~25 KB)
MAX_DB_BYTES = 100 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_CDB_BYTES = 50 * 1024 * 1024

# EDOPro fallback for passcodes YGOPRODeck doesn't know
EDOPRO_CDB_URL = "https://raw.githubusercontent.com/ProjectIgnis/BabelCDB/master/cards.cdb"
EDOPRO_IMAGE_URL = "https://pics.projectignis.org:2096/pics/{id}.jpg"
EDOPRO_REFRESH_INTERVAL = 7 * 24 * 60 * 60
# Bump when the layout of edopro.json changes so old caches are rebuilt
EDOPRO_INDEX_FORMAT = 2
TYPE_TOKEN = 0x4000
_SAFE_FILENAME = re.compile(r'^[A-Za-z0-9_-]{1,64}\.(jpg|jpeg|png|webp)$')

_db: Optional[Dict[str, Dict[str, str]]] = None
_db_lock = threading.Lock()
_request_lock = threading.Lock()
_edopro: Optional[Dict[str, Dict]] = None
_edopro_lock = threading.Lock()
_last_request = 0.0


def cache_dir() -> str:
    """Return (and create) the directory used for cached data."""
    base = os.environ.get('YGO_CACHE_DIR')
    if not base:
        if os.name == 'nt':
            root = os.environ.get('LOCALAPPDATA') or os.path.expanduser('~')
            base = os.path.join(root, 'YGO-Hand-Simulator')
        else:
            base = os.path.join(os.path.expanduser('~'), '.cache', 'ygo-hand-simulator')
    os.makedirs(base, exist_ok=True)
    return base


def normalize_id(card_id: str) -> str:
    """Strip leading zeros so '05318639' and '5318639' match."""
    try:
        return str(int(card_id))
    except (TypeError, ValueError):
        return str(card_id)


def _check_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in ALLOWED_HOSTS:
        raise ValueError(f"Refusing to download from untrusted URL: {url}")


def _get(url: str, timeout: int = 30, max_bytes: int = MAX_IMAGE_BYTES) -> bytes:
    """Rate-limited, size-capped HTTPS GET restricted to YGOPRODeck hosts."""
    global _last_request
    _check_url(url)
    with _request_lock:
        wait = MIN_REQUEST_GAP - (time.monotonic() - _last_request)
        if wait > 0:
            time.sleep(wait)
        _last_request = time.monotonic()
    req = urllib.request.Request(url)
    req.add_header('User-Agent', USER_AGENT)
    with urllib.request.urlopen(req, timeout=timeout) as response:
        _check_url(response.geturl())  # also covers redirects
        data = response.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ValueError(f"Response from {url} exceeds {max_bytes} bytes")
    return data


def _db_path() -> str:
    return os.path.join(cache_dir(), 'cards.json')


def _write_json_atomic(path: str, data) -> None:
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f)
    os.replace(tmp, path)


def _remote_db_version() -> Optional[str]:
    try:
        data = json.loads(_get(API_DB_VERSION, timeout=10).decode())
        return str(data[0]['database_version'])
    except Exception:
        logging.warning("Could not check card database version")
        return None


def _download_db(version: Optional[str]) -> Dict[str, Dict[str, str]]:
    """Download every card and build a compact id -> {name, image} index.

    Alternate artworks get their own entries so decks using alt-art
    passcodes resolve to the right name and picture.
    """
    data = json.loads(_get(API_ALL_CARDS, timeout=120, max_bytes=MAX_DB_BYTES).decode())
    cards: Dict[str, Dict[str, str]] = {}
    for card in data.get('data', []):
        name = html.unescape(card['name'])
        images = card.get('card_images') or []
        main_image = images[0].get('image_url_small', '') if images else ''
        cards[str(card['id'])] = {'name': name, 'image': main_image}
        for art in images:
            art_id = str(art.get('id', ''))
            if art_id and art_id not in cards:
                cards[art_id] = {'name': name, 'image': art.get('image_url_small', '')}
    _write_json_atomic(_db_path(), {'version': version, 'checked': time.time(), 'cards': cards})
    logging.info("Downloaded card database: %d entries", len(cards))
    return cards


def load_card_db(allow_download: bool = True) -> Optional[Dict[str, Dict[str, str]]]:
    """Load the card index from disk, downloading/refreshing it if needed.

    Safe to call from a background thread. Returns None if no database
    is available (e.g. first run while offline).
    """
    global _db
    with _db_lock:
        if _db is not None:
            return _db

        stored = None
        try:
            with open(_db_path(), encoding='utf-8') as f:
                stored = json.load(f)
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("Card database cache is corrupt; re-downloading")

        if stored and not allow_download:
            _db = stored['cards']
            return _db

        if stored and time.time() - stored.get('checked', 0) < DB_CHECK_INTERVAL:
            _db = stored['cards']
            return _db

        if not allow_download:
            return None

        remote_version = _remote_db_version()
        if stored and (remote_version is None or remote_version == stored.get('version')):
            # Up to date (or can't tell): keep using it, check again later
            stored['checked'] = time.time()
            try:
                _write_json_atomic(_db_path(), stored)
            except Exception:
                pass
            _db = stored['cards']
            return _db

        try:
            _db = _download_db(remote_version)
        except Exception:
            logging.exception("Failed to download card database")
            _db = stored['cards'] if stored else None
        return _db


def get_db() -> Optional[Dict[str, Dict[str, str]]]:
    """Return the card index if it is already loaded (never blocks on network)."""
    return _db


def get_db_nowait() -> Optional[Dict[str, Dict[str, str]]]:
    """Return the card index, loading it from disk if possible.

    Never touches the network and never waits on a download that is
    already running in the background.
    """
    global _db
    if _db is not None or not _db_lock.acquire(blocking=False):  # pylint: disable=consider-using-with
        return _db
    try:
        if _db is None:
            with open(_db_path(), encoding='utf-8') as f:
                _db = json.load(f)['cards']
    except Exception:
        pass
    finally:
        _db_lock.release()
    return _db


def lookup(card_id: str) -> Optional[Dict[str, str]]:
    """Return {'name', 'image'} for a card id from the loaded index, if present."""
    if _db is None:
        return None
    return _db.get(normalize_id(card_id))


def _token_creators(rows) -> Dict[str, str]:
    """Map each token id to the card that creates it.

    Tokens can never be in a deck, so a token id in a deck file is an export
    mistake (e.g. "Primal Being Token" 27204312 instead of Nibiru 27204311).
    The creator is the card whose text names the token; when several do,
    prefer the one whose passcode is the token's minus one (Konami's usual
    numbering), otherwise leave the token unresolved.
    """
    tokens = {str(cid): name for cid, name, _alias, ctype, _desc in rows if (ctype or 0) & TYPE_TOKEN}
    wanted = {f'"{name}"': [] for name in tokens.values()}
    for cid, _name, _alias, ctype, desc in rows:
        if (ctype or 0) & TYPE_TOKEN or not desc:
            continue
        for quoted, creators in wanted.items():
            if quoted in desc:
                creators.append(str(cid))
    result = {}
    for token_id, name in tokens.items():
        creators = wanted[f'"{name}"']
        guess = str(int(token_id) - 1)
        if guess in creators:
            result[token_id] = guess
        elif len(creators) == 1:
            result[token_id] = creators[0]
    return result


def _download_edopro_index() -> Dict[str, Dict]:
    """Download EDOPro's cards.cdb (SQLite) and keep only id -> {name, alias, creator}."""
    data = _get(EDOPRO_CDB_URL, timeout=120, max_bytes=MAX_CDB_BYTES)
    if not data.startswith(b'SQLite format 3\x00'):
        raise ValueError("EDOPro card database is not a SQLite file")
    tmp = os.path.join(cache_dir(), f'edopro.{threading.get_ident()}.cdb.tmp')
    try:
        with open(tmp, 'wb') as f:
            f.write(data)
        con = sqlite3.connect(f'file:{tmp}?mode=ro', uri=True)
        try:
            rows = con.execute(
                'SELECT texts.id, texts.name, datas.alias, datas.type, texts.desc '
                'FROM texts JOIN datas ON datas.id = texts.id'
            ).fetchall()
        finally:
            con.close()
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    cards = {str(cid): {'name': str(name), 'alias': str(alias or 0)} for cid, name, alias, _t, _d in rows}
    for token_id, creator_id in _token_creators(rows).items():
        cards[token_id]['creator'] = creator_id
    _write_json_atomic(os.path.join(cache_dir(), 'edopro.json'),
                       {'format': EDOPRO_INDEX_FORMAT, 'checked': time.time(), 'cards': cards})
    logging.info("Downloaded EDOPro card index: %d entries", len(cards))
    return cards


def _load_edopro_index() -> Optional[Dict[str, Dict]]:
    """Load the EDOPro fallback index, downloading it the first time it's needed."""
    global _edopro
    with _edopro_lock:
        if _edopro is not None:
            return _edopro
        stored = None
        try:
            with open(os.path.join(cache_dir(), 'edopro.json'), encoding='utf-8') as f:
                stored = json.load(f)
        except FileNotFoundError:
            pass
        except Exception:
            logging.exception("EDOPro index cache is corrupt; re-downloading")
        if stored and stored.get('format') != EDOPRO_INDEX_FORMAT:
            stored = None
        if stored and time.time() - stored.get('checked', 0) < EDOPRO_REFRESH_INTERVAL:
            _edopro = stored['cards']
            return _edopro
        try:
            _edopro = _download_edopro_index()
        except Exception:
            logging.exception("Failed to download EDOPro card database")
            _edopro = stored['cards'] if stored else {}
        return _edopro


def lookup_fallback(card_id: str) -> Optional[Dict[str, str]]:
    """Resolve a passcode YGOPRODeck doesn't list, using EDOPro's database.

    Alternate-art ids are mapped to their base card, and token ids (which a
    deck can't contain) to the card that creates them, using YGOPRODeck's
    name and picture for that card when it has it. Anything else gets its
    EDOPro name and image.
    """
    norm = normalize_id(card_id)
    index = _load_edopro_index() or {}
    entry = index.get(norm)
    if not entry:
        return None
    if entry.get('creator'):
        logging.info("Deck lists token %s (%s); using the card that creates it, %s",
                     norm, entry['name'], entry['creator'])
        norm = entry['creator']
        entry = index.get(norm, entry)
    alias = entry.get('alias', '0')
    for base_id in (alias, norm):
        if base_id != '0':
            base = lookup(base_id)
            if base:
                return base
    return {'name': entry['name'], 'image': EDOPRO_IMAGE_URL.format(id=norm)}


def preload_in_background() -> threading.Thread:
    """Start loading/refreshing the card database without blocking the UI."""
    t = threading.Thread(target=load_card_db, daemon=True)
    t.start()
    return t


def _image_path(url: str) -> str:
    """Map an image URL to a file in the cache, rejecting unsafe file names."""
    name = os.path.basename(urlparse(url).path)
    if not _SAFE_FILENAME.match(name):
        raise ValueError(f"Unexpected image file name in URL: {url}")
    folder = os.path.join(cache_dir(), 'images')
    os.makedirs(folder, exist_ok=True)
    return os.path.join(folder, name)


def _is_valid_image(data: bytes) -> bool:
    """Check the bytes really are an image before caching them."""
    try:
        from PIL import Image  # pylint: disable=import-outside-toplevel
    except ImportError:
        return True
    try:
        with Image.open(BytesIO(data)) as img:
            img.verify()
        return True
    except Exception:
        return False


def get_image_bytes(url: str) -> Optional[bytes]:
    """Return image bytes from disk, downloading and saving them on first use."""
    if not url:
        return None
    try:
        _check_url(url)
        path = _image_path(url)
    except ValueError:
        logging.warning("Skipping image with untrusted URL: %s", url)
        return None
    try:
        with open(path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        pass
    except Exception:
        logging.exception("Failed to read cached image %s", path)

    for attempt in range(3):
        try:
            data = _get(url, timeout=15)
            if not _is_valid_image(data):
                raise ValueError(f"Downloaded data is not a valid image: {url}")
            tmp = f"{path}.{threading.get_ident()}.tmp"
            with open(tmp, 'wb') as f:
                f.write(data)
            os.replace(tmp, path)
            return data
        except Exception:
            if attempt == 2:
                logging.exception("Failed to download image: %s", url)
            else:
                time.sleep(1 + attempt)
    return None


def prefetch_images(urls: Iterable[str]) -> threading.Thread:
    """Download any images not yet on disk, in a background thread."""
    pending = []
    for url in dict.fromkeys(urls):
        try:
            if url and not os.path.exists(_image_path(url)):
                pending.append(url)
        except ValueError:
            logging.warning("Skipping image with untrusted URL: %s", url)

    def _run():
        for url in pending:
            get_image_bytes(url)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
