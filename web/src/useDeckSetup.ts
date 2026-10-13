// One deck and the label (engine / non-engine / brick) of each card copy, set in the decklist view.

import { useCallback, useEffect, useMemo, useState } from "react";
import { api, Category, DeckCard, DeckSetupBody } from "./api";
import { SavedDeck } from "./storage";

export interface DeckSetup {
  cards: DeckCard[] | null;
  /** The deck's name (the .ydk file name), or null when loaded from a ydke:// code */
  name: string | null;
  /** One card name per copy, in deck order */
  deckList: string[];
  idByName: Record<string, string>;
  size: number;
  loading: boolean;
  /** One label per copy, in deck order ("" = unlabelled) */
  tags: Category[];
  /** Whether any card is labelled */
  labelled: boolean;
  load: (code: string, name?: string) => Promise<void>;
  applyTags: (tags: Category[]) => void;
  /** Back to no deck (when its tab is closed) */
  reset: () => void;
  body: (name: string) => DeckSetupBody | null;
}

const unlabelled = (cards: DeckCard[]) =>
  Array<Category>(cards.reduce((total, card) => total + card.copies, 0)).fill("");

/** `initial`: a deck saved before the page was refreshed */
export function useDeckSetup(initial?: SavedDeck): DeckSetup {
  const [cards, setCards] = useState<DeckCard[] | null>(initial?.cards ?? null);
  const [name, setName] = useState<string | null>(initial?.name ?? null);
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<Category[]>(initial?.tags ?? []);

  const deckList = useMemo(
    () => (cards ?? []).flatMap((card) => Array<string>(card.copies).fill(card.name)),
    [cards],
  );
  const idByName = useMemo(
    () => Object.fromEntries((cards ?? []).map((card) => [card.name, card.id])),
    [cards],
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

  const load = useCallback(async (code: string, deckName?: string) => {
    setLoading(true);
    try {
      const deck = await api.loadDeck(code);
      setCards(deck.cards);
      setName(deckName?.trim() || null);
      setTags(unlabelled(deck.cards));
    } finally {
      setLoading(false);
    }
  }, []);

  const reset = useCallback(() => {
    setCards(null);
    setName(null);
    setTags([]);
  }, []);

  const body = useCallback(
    (name: string): DeckSetupBody | null => {
      if (!cards) return null;
      return { name, cards: cards.map(({ name, copies }) => ({ name, copies })), tags, counts: null };
    },
    [cards, tags],
  );

  // The same object until the deck changes, so memoised views don't re-render needlessly
  return useMemo(() => ({
    cards, name, deckList, idByName, size: deckList.length, loading, tags,
    labelled: tags.some(Boolean),
    load, applyTags: setTags, reset, body,
  }), [cards, name, deckList, idByName, loading, tags, load, reset, body]);
}
