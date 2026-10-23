"""The web app's HTTP API (FastAPI), plus the built front end from web/dist.

The server keeps no per-user state: the browser holds the deck and its tags or
counts and sends them with each request.

    POST /api/decks                  deck code -> main and side deck card lists
    POST /api/decks/info             card IDs -> each card's kind, level and banlist status (for
                                     decks saved before the card list had them, and a fresh status)
    POST /api/stats                  deck setup -> opening-hand odds
    POST /api/draw                   deck setup -> random hand, next draws, shuffled deck + odds for it
    POST /api/compare                two deck setups -> side-by-side odds
    GET  /api/cards/{id}/image       card image (cached in memory and on disk)

Security headers, request size limits and rate limits are in security.py. The interactive
API docs (/api/docs) are only served when YGO_API_DOCS=1.

Copyright (c) 2026 Alex-xyc
"""

import os
import random
import re
from typing import List, Literal, Optional, Tuple

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..cards import fetch_card_infos
from ..core.categories import CardPool, pool_from_counts, pool_from_tags
from ..core.comparison import DeckSummary, compare_decks
from ..core.deck import YuGiOhDeck
from ..core.deck_builder import TooManyCopiesError
from ..core.deck_parser import DeckParseError
from ..core.stats import opening_stats
from ..deck_loading import load_main_deck, load_side_deck
from ..paths import SRC_DIR
from .images import SIZES, ImageUnavailable, get_card_image
from .security import SecurityMiddleware

# web/dist next to src/, unless YGO_WEB_DIST points elsewhere
WEB_DIST = os.environ.get("YGO_WEB_DIST",
                          os.path.join(os.path.dirname(SRC_DIR), "web", "dist"))
MAX_CODE_LENGTH = 20_000


# Request bodies

class DeckCode(BaseModel):
    code: str = Field(max_length=MAX_CODE_LENGTH)


class Card(BaseModel):
    name: str = Field(max_length=200)
    copies: int = Field(ge=1, le=YuGiOhDeck.MAX_COPIES)


class Counts(BaseModel):
    brick: int = Field(0, ge=0)
    non_engine: int = Field(0, ge=0)
    engine: int = Field(0, ge=0)


class DeckSetup(BaseModel):
    """A deck plus its categories: per-copy tags (from the decklist view) or typed counts."""
    name: str = Field("Deck", max_length=40)
    cards: List[Card] = Field(min_length=1, max_length=YuGiOhDeck.MAX_DECK_SIZE)
    tags: Optional[List[Literal["brick", "non_engine", "engine", ""]]] = None
    counts: Optional[Counts] = None
    # Per copy, in deck order: whether it was swapped in from the side deck (the draw marks those cards)
    sided: Optional[List[bool]] = Field(None, max_length=YuGiOhDeck.MAX_DECK_SIZE)

    def build(self) -> YuGiOhDeck:
        deck = YuGiOhDeck()
        for card in self.cards:
            try:
                deck.add_card(card.name, deck.cards.get(card.name, 0) + card.copies)
            except ValueError as e:
                raise HTTPException(400, str(e).removeprefix("Error: ")) from e
        if deck.get_deck_size() > YuGiOhDeck.MAX_DECK_SIZE:
            raise HTTPException(400, f"Decks can have at most {YuGiOhDeck.MAX_DECK_SIZE} cards.")
        return deck

    @property
    def tagged(self) -> bool:
        return self.tags is not None and any(self.tags)

    def pool(self) -> CardPool:
        deck = self.build()
        size = deck.get_deck_size()
        if self.tagged:
            if len(self.tags) != size:
                raise HTTPException(400, "Tags don't match the deck.")
            return pool_from_tags(deck, list(self.tags))
        counts = self.counts or Counts()
        total = counts.brick + counts.non_engine + counts.engine
        if total > size:
            raise HTTPException(400, f"{self.name}: total counts ({total}) exceed deck size ({size}).")
        return pool_from_counts(deck, counts.brick, counts.non_engine, counts.engine)


class DrawRequest(BaseModel):
    deck: DeckSetup


class CompareRequest(BaseModel):
    decks: List[DeckSetup] = Field(min_length=2, max_length=2)
    hand_size: int = Field(5, ge=5, le=6)


# The app

# The interactive docs are off on a public server unless asked for
API_DOCS = os.environ.get("YGO_API_DOCS") == "1"
app = FastAPI(title="Yu-Gi-Oh! Hand Simulator", redoc_url=None,
              docs_url="/api/docs" if API_DOCS else None,
              openapi_url="/api/openapi.json" if API_DOCS else None)
app.add_middleware(SecurityMiddleware)

# Card IDs are plain numbers (ASCII digits only: str.isdigit also accepts other scripts' digits)
CARD_ID = re.compile(r"[0-9]{1,10}")


@app.post("/api/decks")
def load_deck(body: DeckCode):
    """Look up a ydke:// code or .ydk file text; returns the main and side decks in deck order,
    with each card's kind (monster, spell_<subtype>, trap_<subtype>; "" if unknown) and level for
    sorting, and its TCG status (banned, limited, semi_limited, ocg for not out in the TCG yet, or
    "")."""
    deck = YuGiOhDeck()
    try:
        card_ids = load_main_deck(deck, body.code)
        side_counts, side_ids = load_side_deck(body.code)
    except (DeckParseError, TooManyCopiesError) as e:
        raise HTTPException(400, str(e)) from e
    main = [(name, card_ids.get(name, ""), copies) for name, copies in deck.cards.items()]
    side = [(name, side_ids.get(name, ""), copies) for name, copies in side_counts.items()]
    infos = fetch_card_infos(list(dict.fromkeys(cid for _, cid, _ in main + side)))

    def listed(cards):
        return [{"name": name, "id": cid, "copies": copies, **infos[cid]} for name, cid, copies in cards]

    return {"cards": listed(main), "side": listed(side), "size": deck.get_deck_size()}


class CardIds(BaseModel):
    ids: List[str] = Field(max_length=YuGiOhDeck.MAX_DECK_SIZE)


@app.post("/api/decks/info")
def card_infos(body: CardIds):
    """Each card's kind (monster, spell_<subtype>, trap_<subtype>; "" if unknown), level and TCG
    status (banned, limited, semi_limited, ocg or "")."""
    ids = [cid for cid in dict.fromkeys(body.ids) if CARD_ID.fullmatch(cid)]
    return fetch_card_infos(ids)


@app.post("/api/stats")
def stats(body: DeckSetup, hand_size: int = Query(5, ge=5, le=6)):
    """The main page's odds; hand_size 6 gives them going second (the export uses both)."""
    return opening_stats(body.pool(), hand_size=hand_size, grouped=body.tagged)


def _drawn(cards: List[Tuple[str, str, bool, int]]) -> List[dict]:
    return [{"name": name, "category": category, "sided": sided, "copy": copy}
            for name, category, sided, copy in cards]


@app.post("/api/draw")
def draw(body: DrawRequest):
    """Shuffle and draw 5 cards, the 6th (the next card, going second) and the 4 cards after it
    (extra draws), plus the whole shuffled deck in order; odds include the 6th-card odds for this
    hand when the deck is tagged by card. Each card says whether it was sided in, and which copy
    it is (its position in the deck list), so the page can show its own labels for it."""
    setup = body.deck
    pool = list(setup.pool())
    sided = setup.sided or [False] * len(pool)
    if len(sided) != len(pool):
        raise HTTPException(400, "Sided-in cards don't match the deck.")
    # The pool is in deck order, as are the sided-in flags
    deck = [(*pool[i], sided[i], i) for i in random.sample(range(len(pool)), len(pool))]
    hand, after = deck[:5], deck[5:10]
    categories = [c for _, c, _, _ in hand]
    return {
        "hand": _drawn(hand),
        "sixth": _drawn(after[:1])[0] if after else None,
        "draws": _drawn(after[1:]),
        "deck": _drawn(deck),
        "stats": opening_stats(pool, categories if setup.tagged else None, grouped=setup.tagged),
    }


@app.post("/api/compare")
def compare(body: CompareRequest):
    summaries = [DeckSummary(setup.name, setup.pool()) for setup in body.decks]
    return compare_decks(*summaries, hand_size=body.hand_size)


@app.get("/api/cards/{card_id}/image")
async def card_image(card_id: str, size: Literal["small", "full"] = "small"):
    """Async, so images already in memory are sent without waiting for a worker thread (the
    cache folder and downloads still use threads, inside get_card_image)."""
    if not CARD_ID.fullmatch(card_id) or size not in SIZES:
        raise HTTPException(404)
    try:
        image = await get_card_image(card_id, size)
    except ImageUnavailable as e:
        # Not cached by the browser, so it asks again later
        raise HTTPException(503, "Card images are unavailable just now.",
                            headers={"Retry-After": str(max(1, int(e.retry_after)))}) from e
    if image is None:
        raise HTTPException(404)
    # Card art never changes for an ID, so browsers may keep it for a long time
    return Response(image, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=2592000, immutable"})


if os.path.isdir(WEB_DIST):
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
