// One deck and the label (engine / non-engine / brick) of each card copy, set in the decklist view.

import { useCallback, useMemo, useState } from "react";
import { api, Category, DeckCard, DeckSetupBody } from "./api";

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
  copyFrom: (other: DeckSetup) => void;
  body: (name: string) => DeckSetupBody | null;
}

const unlabelled = (cards: DeckCard[]) =>
  Array<Category>(cards.reduce((total, card) => total + card.copies, 0)).fill("");

export function useDeckSetup(): DeckSetup {
  const [cards, setCards] = useState<DeckCard[] | null>(null);
  const [name, setName] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tags, setTags] = useState<Category[]>([]);

  const deckList = useMemo(
    () => (cards ?? []).flatMap((card) => Array<string>(card.copies).fill(card.name)),
    [cards],
  );
  const idByName = useMemo(
    () => Object.fromEntries((cards ?? []).map((card) => [card.name, card.id])),
    [cards],
  );

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

  const copyFrom = useCallback((other: DeckSetup) => {
    setCards(other.cards);
    setName(other.name);
    setTags(other.tags);
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
    load, applyTags: setTags, copyFrom, body,
  }), [cards, name, deckList, idByName, loading, tags, load, copyFrom, body]);
}
