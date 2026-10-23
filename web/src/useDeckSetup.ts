// One deck and the label (engine / non-engine / brick) of each card copy, set in the decklist view,
// plus its side deck, whose cards can be swapped with the main deck's. Every copy keeps its label
// and which deck it started in as it moves between the two.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type Category, type DeckCard, type DeckSetupBody } from "./api";
import { rememberStatuses } from "./banStatus";
import type { SavedDeck } from "./storage";

/** The most copies of a card a deck can have */
export const MAX_COPIES = 3;

export interface DeckSetup {
  cards: DeckCard[] | null;
  /** The side deck (empty when the deck has none); null when not known, for a deck saved before
   *  side decks were kept (loading it again gets it) */
  side: DeckCard[] | null;
  /** The deck's name (the .ydk file name), or null when loaded from a ydke:// code */
  name: string | null;
  /** One card name per copy, in deck order */
  deckList: string[];
  /** One card name per side deck copy, in order */
  sideList: string[];
  /** Main and side deck cards */
  idByName: Record<string, string>;
  size: number;
  loading: boolean;
  /** One label per copy, in deck order ("" = unlabelled) */
  tags: Category[];
  /** Per copy, in deck order: whether it was sided in (started in the side deck) */
  sided: boolean[];
  /** How many copies in the deck were sided in */
  sidedIn: number;
  /** One remembered label per side deck copy, in order */
  sideTags: Category[];
  /** Per side deck copy: whether it was sided out (started in the main deck) */
  sideFromMain: boolean[];
  /** Whether any card is labelled */
  labelled: boolean;
  load: (code: string, name?: string) => Promise<void>;
  applyTags: (tags: Category[]) => void;
  /** Swap main deck copies (deck positions) for as many side deck copies (side positions) */
  swapSide: (out: number[], into: number[]) => void;
  /** Back to no deck (when its tab is closed) */
  reset: () => void;
  body: (name: string) => DeckSetupBody | null;
}

/** Both decks, one entry per copy in the per-copy lists */
export interface Decks {
  cards: DeckCard[];
  tags: Category[];
  sided: boolean[];
  side: DeckCard[];
  sideTags: Category[];
  sideFromMain: boolean[];
}

const sizeOf = (cards: DeckCard[]) => cards.reduce((total, card) => total + card.copies, 0);
const unlabelled = (cards: DeckCard[]) => Array<Category>(sizeOf(cards)).fill("");
const unmoved = (cards: DeckCard[]) => Array<boolean>(sizeOf(cards)).fill(false);

const copiesOf = (cards: DeckCard[]) => cards.flatMap((card) => Array<string>(card.copies).fill(card.name));

interface Copy { name: string; tag: Category; moved: boolean }

/** Copies back into cards, each card where its first copy is, and the copies in that order (each
 *  card's copies together) */
function grouped(copies: Copy[], info: Map<string, DeckCard>): { cards: DeckCard[]; copies: Copy[] } {
  const byName = new Map<string, Copy[]>();
  for (const copy of copies) byName.set(copy.name, [...byName.get(copy.name) ?? [], copy]);
  return {
    cards: [...byName].map(([name, list]) => ({ ...info.get(name)!, copies: list.length })),
    copies: [...byName.values()].flat(),
  };
}

/** Both decks after swapping main deck copies `out` (deck positions) for side deck copies `into`
 *  (side positions). Each copy takes its label along; one sided in without a label takes the label
 *  of its copies already in the deck. A copy is marked as moved while it's out of the deck it
 *  started in. Cards sided in go with their other copies (or after the rest of the deck); cards
 *  sided out go to the end of the side deck. */
export function swapCards(decks: Decks, out: number[], into: number[]): Decks {
  const info = new Map([...decks.side, ...decks.cards].map((card) => [card.name, card]));
  const leaving = new Set(out);
  const coming = new Set(into);
  const main: Copy[] = copiesOf(decks.cards).map((name, i) => ({ name, tag: decks.tags[i] ?? "", moved: decks.sided[i] ?? false }));
  const side: Copy[] = copiesOf(decks.side).map((name, i) => ({ name, tag: decks.sideTags[i] ?? "", moved: decks.sideFromMain[i] ?? false }));

  const kept = main.filter((_, i) => !leaving.has(i));
  for (const copy of side.filter((_, i) => coming.has(i))) {
    // Back in the deck it started in, or now away from it
    kept.push({ name: copy.name, moved: !copy.moved,
                tag: copy.tag || (kept.find((other) => other.name === copy.name)?.tag ?? "") });
  }
  const nextSide = [
    ...side.filter((_, i) => !coming.has(i)),
    ...main.filter((_, i) => leaving.has(i)).map((copy) => ({ ...copy, moved: !copy.moved })),
  ];

  const nextMain = grouped(kept, info);
  const nextSideDeck = grouped(nextSide, info);
  return {
    cards: nextMain.cards,
    tags: nextMain.copies.map((copy) => copy.tag),
    sided: nextMain.copies.map((copy) => copy.moved),
    side: nextSideDeck.cards,
    sideTags: nextSideDeck.copies.map((copy) => copy.tag),
    sideFromMain: nextSideDeck.copies.map((copy) => copy.moved),
  };
}

/** `initial`: a deck saved before the page was refreshed */
export function useDeckSetup(initial?: SavedDeck): DeckSetup {
  const [cards, setCards] = useState<DeckCard[] | null>(initial?.cards ?? null);
  const [side, setSide] = useState<DeckCard[] | null>(initial?.cards ? initial.side ?? null : []);
  const [name, setName] = useState<string | null>(initial?.name ?? null);
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<Category[]>(initial?.tags ?? []);
  const [sided, setSided] = useState<boolean[]>(initial?.sided ?? unmoved(initial?.cards ?? []));
  const [sideTags, setSideTags] = useState<Category[]>(initial?.sideTags ?? unlabelled(initial?.side ?? []));
  const [sideFromMain, setSideFromMain] = useState<boolean[]>(initial?.sideFromMain ?? unmoved(initial?.side ?? []));

  const deckList = useMemo(() => copiesOf(cards ?? []), [cards]);
  const sideList = useMemo(() => copiesOf(side ?? []), [side]);
  const idByName = useMemo(
    () => Object.fromEntries([...(side ?? []), ...(cards ?? [])].map((card) => [card.name, card.id])),
    [cards, side],
  );

  // A deck saved before cards had a kind (for sorting) gets them looked up
  useEffect(() => {
    if (!cards?.some((card) => card.kind === undefined)) return;
    api.cardInfo(cards.map((card) => card.id).filter(Boolean))
      .then((infos) => setCards((current) => current !== cards ? current : current.map((card) => ({
        ...card, kind: infos[card.id]?.kind ?? "", level: infos[card.id]?.level ?? 0,
      }))))
      .catch(() => { /* Sorting just puts them last */ });
  }, [cards]);

  const setDecks = useCallback((decks: Decks | null) => {
    setCards(decks?.cards ?? null);
    setTags(decks?.tags ?? []);
    setSided(decks?.sided ?? []);
    setSide(decks?.side ?? []);
    setSideTags(decks?.sideTags ?? []);
    setSideFromMain(decks?.sideFromMain ?? []);
  }, []);

  const load = useCallback(async (code: string, deckName?: string) => {
    setLoading(true);
    try {
      const deck = await api.loadDeck(code);
      const deckSide = deck.side ?? [];
      rememberStatuses([...deck.cards, ...deckSide]);
      setDecks({
        cards: deck.cards, tags: unlabelled(deck.cards), sided: unmoved(deck.cards),
        side: deckSide, sideTags: unlabelled(deckSide), sideFromMain: unmoved(deckSide),
      });
      setName(deckName?.trim() || null);
    } finally {
      setLoading(false);
    }
  }, [setDecks]);

  const swapSide = useCallback((out: number[], into: number[]) => {
    if (!cards || !side || !out.length || out.length !== into.length) return;
    setDecks(swapCards({ cards, tags, sided, side, sideTags, sideFromMain }, out, into));
  }, [cards, tags, sided, side, sideTags, sideFromMain, setDecks]);

  const reset = useCallback(() => {
    setDecks(null);
    setName(null);
  }, [setDecks]);

  const body = useCallback(
    (name: string): DeckSetupBody | null => {
      if (!cards) return null;
      return {
        name, cards: cards.map(({ name, copies }) => ({ name, copies })), tags, counts: null,
        ...(sided.some(Boolean) ? { sided } : {}),
      };
    },
    [cards, tags, sided],
  );

  // The same object until the deck changes, so memoised views don't re-render needlessly
  return useMemo(() => ({
    cards, side, name, deckList, sideList, idByName, size: deckList.length, loading, tags,
    sided, sidedIn: sided.filter(Boolean).length, sideTags, sideFromMain,
    labelled: tags.some(Boolean),
    load, applyTags: setTags, swapSide, reset, body,
  }), [cards, side, name, deckList, sideList, idByName, loading, tags, sided, sideTags, sideFromMain,
       load, swapSide, reset, body]);
}
