"""The web app's HTTP API (FastAPI), plus the built front end from web/dist.

The server keeps no per-user state: the browser holds the deck and its tags or
counts and sends them with each request.

    POST /api/decks                  deck code -> card list
    POST /api/stats                  deck setup -> opening-hand odds
    POST /api/draw                   deck setup -> random hand + odds for it
    POST /api/compare                two deck setups -> side-by-side odds
    GET  /api/cards/{id}/image       card image (cached on disk)

Copyright (c) 2026 Alex-xyc
"""

import os
from typing import List, Literal, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ..core.categories import CardPool, pool_from_counts, pool_from_tags
from ..core.comparison import DeckSummary, compare_decks
from ..core.deck import YuGiOhDeck
from ..core.deck_builder import TooManyCopiesError
from ..core.deck_parser import DeckParseError
from ..core.simulation import draw_from_pool
from ..core.stats import opening_stats
from ..deck_loading import load_main_deck
from ..paths import SRC_DIR
from .images import SIZES, card_image_path

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

    def build(self) -> YuGiOhDeck:
        deck = YuGiOhDeck()
        for card in self.cards:
            try:
                deck.add_card(card.name, deck.cards.get(card.name, 0) + card.copies)
            except ValueError as e:
                raise HTTPException(400, str(e).removeprefix("Error: "))
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

app = FastAPI(title="Yu-Gi-Oh! Hand Simulator", docs_url="/api/docs", openapi_url="/api/openapi.json")


@app.post("/api/decks")
def load_deck(body: DeckCode):
    """Look up a ydke:// code or .ydk file text; returns the main deck in deck order."""
    deck = YuGiOhDeck()
    try:
        card_ids = load_main_deck(deck, body.code)
    except (DeckParseError, TooManyCopiesError) as e:
        raise HTTPException(400, str(e))
    cards = [{"name": name, "id": card_ids.get(name, ""), "copies": copies}
             for name, copies in deck.cards.items()]
    return {"cards": cards, "size": deck.get_deck_size()}


@app.post("/api/stats")
def stats(body: DeckSetup):
    return opening_stats(body.pool(), grouped=body.tagged)


@app.post("/api/draw")
def draw(body: DrawRequest):
    """Shuffle and draw 5 cards plus the 6th (the next card); odds include the 6th-card odds
    for this hand when the deck is tagged by card."""
    setup = body.deck
    pool = setup.pool()
    hand, categories, sixth = draw_from_pool(pool)
    sixth_category = None
    if sixth is not None:
        # The 6th card is the first remaining copy of that name after the hand
        remaining = list(pool)
        for name, category in zip(hand, categories):
            remaining.remove((name, category))
        sixth_category = next(c for n, c in remaining if n == sixth)
    return {
        "hand": [{"name": n, "category": c} for n, c in zip(hand, categories)],
        "sixth": {"name": sixth, "category": sixth_category} if sixth else None,
        "stats": opening_stats(pool, categories if setup.tagged else None, grouped=setup.tagged),
    }


@app.post("/api/compare")
def compare(body: CompareRequest):
    summaries = [DeckSummary(setup.name, setup.pool()) for setup in body.decks]
    return compare_decks(*summaries, hand_size=body.hand_size)


@app.get("/api/cards/{card_id}/image")
def card_image(card_id: str, size: Literal["small", "full"] = "small"):
    if not card_id.isdigit() or len(card_id) > 12 or size not in SIZES:
        raise HTTPException(404)
    path = card_image_path(card_id, size)
    if path is None:
        raise HTTPException(404)
    # Card art never changes for an ID, so browsers may keep it for a long time
    return FileResponse(path, media_type="image/jpeg",
                        headers={"Cache-Control": "public, max-age=2592000, immutable"})


if os.path.isdir(WEB_DIST):
    app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")

