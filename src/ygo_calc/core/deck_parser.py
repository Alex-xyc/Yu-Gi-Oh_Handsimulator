"""Reading card IDs out of deck codes: ydke:// URLs and .ydk file text."""

import base64
import struct
from typing import List, Tuple


class DeckParseError(ValueError):
    """The deck code contains no main deck cards."""


def parse_ydke_url(ydke_url: str) -> Tuple[List[str], List[str], List[str]]:
    """Parse ydke:// URL into card ID lists."""
    if not ydke_url.startswith("ydke://"):
        raise ValueError("Invalid ydke:// format")

    data = ydke_url[7:]
    parts = data.split("!")

    def decode_section(b64_data: str) -> List[str]:
        if not b64_data:
            return []
        try:
            decoded = base64.b64decode(b64_data)
            card_ids = []
            for i in range(0, len(decoded), 4):
                if i + 4 <= len(decoded):
                    card_id = struct.unpack('<I', decoded[i:i+4])[0]
                    card_ids.append(str(card_id))
            return card_ids
        except Exception:
            return []

    main_ids = decode_section(parts[0]) if len(parts) >= 1 else []
    extra_ids = decode_section(parts[1]) if len(parts) >= 2 else []
    side_ids = decode_section(parts[2]) if len(parts) >= 3 else []

    return main_ids, extra_ids, side_ids


def parse_ydk_section_ids(ydk_text: str, section: str) -> List[str]:
    """Card IDs in one section ("main", "extra" or "side") of .ydk file text."""
    headers = {"#main": "main", "#extra": "extra", "!side": "side", "#side": "side"}
    card_ids = []
    current = None
    for line in ydk_text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line in headers:
            current = headers[line]
            continue
        if line.startswith("#") or line.startswith("!"):
            continue
        if current == section and line.isascii() and line.isdigit() and len(line) <= 10:
            card_ids.append(line)
    return card_ids


def parse_ydk_main_ids(ydk_text: str) -> List[str]:
    """Card IDs in the #main section of .ydk file text."""
    return parse_ydk_section_ids(ydk_text, "main")


def extract_main_deck_ids(deck_code: str) -> List[str]:
    """Main deck card IDs from a ydke:// URL or .ydk file text.

    Raises DeckParseError if the code has no main deck cards.
    """
    deck_code = deck_code.strip()
    if deck_code.startswith("ydke://"):
        main_ids, _, _ = parse_ydke_url(deck_code)
        if not main_ids:
            raise DeckParseError("No main deck cards found in ydke code.")
        return main_ids

    card_ids = parse_ydk_main_ids(deck_code)
    if not card_ids:
        raise DeckParseError("No main deck cards found.")
    return card_ids


def extract_side_deck_ids(deck_code: str) -> List[str]:
    """Side deck card IDs from a ydke:// URL or .ydk file text (empty if it has none)."""
    deck_code = deck_code.strip()
    if deck_code.startswith("ydke://"):
        return parse_ydke_url(deck_code)[2]
    return parse_ydk_section_ids(deck_code, "side")
