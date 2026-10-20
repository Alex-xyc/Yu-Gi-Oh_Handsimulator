// The open deck tabs, kept in the browser (localStorage) so a page refresh brings them back

import { Category, DeckCard } from "./api";

const KEY = "ygo-hand-simulator:decks:v1";

export interface SavedDeck {
  cards: DeckCard[] | null;
  /** The side deck (missing or null in decks saved before it was kept) */
  side?: DeckCard[] | null;
  name: string | null;
  tags: Category[];
  /** Per copy: whether it was sided in (missing in decks saved before it was kept) */
  sided?: boolean[];
  /** Per side deck copy: its remembered label, and whether it was sided out */
  sideTags?: Category[];
  sideFromMain?: boolean[];
}

export interface SavedTabs {
  /** The open tabs' slots, in tab order */
  open: number[];
  active: number;
  /** Each open slot's deck */
  decks: Record<number, SavedDeck>;
}

const TAGS = new Set<string>(["", "engine", "requirement", "non_engine", "brick"]);

const validCards = (cards: unknown): cards is DeckCard[] => Array.isArray(cards) && cards.every((c) =>
  c && typeof c.name === "string" && typeof c.id === "string" && Number.isInteger(c.copies) && c.copies > 0);

/** `list` if it's one valid entry per copy, else `fallback` of that length */
function perCopy<T>(list: unknown, size: number, valid: (item: unknown) => boolean, fallback: T): T[] {
  return Array.isArray(list) && list.length === size && list.every(valid) ? list as T[] : Array<T>(size).fill(fallback);
}
const isTag = (t: unknown) => TAGS.has(t as string);
const isFlag = (f: unknown) => typeof f === "boolean";

/** A saved deck as stored, or null when it isn't one (old format, edited by hand, …) */
function validDeck(value: unknown): SavedDeck | null {
  if (!value || typeof value !== "object") return null;
  const { cards, side, name, tags, sided, sideTags, sideFromMain } = value as Record<string, unknown>;
  if (cards === null) return { cards: null, side: [], name: null, tags: [] };
  if (!validCards(cards)) return null;
  const sizeOf = (list: DeckCard[]) => list.reduce((total, card) => total + card.copies, 0);
  const size = sizeOf(cards);
  // A side deck that isn't one is dropped rather than the whole deck (and counts as not known)
  const sideDeck = validCards(side) ? side : null;
  const sideSize = sizeOf(sideDeck ?? []);
  // Labels and marks that don't fit the deck are dropped rather than the whole deck
  return {
    cards,
    side: sideDeck,
    name: typeof name === "string" ? name : null,
    tags: perCopy<Category>(tags, size, isTag, ""),
    sided: perCopy(sided, size, isFlag, false),
    sideTags: perCopy<Category>(sideTags, sideSize, isTag, ""),
    sideFromMain: perCopy(sideFromMain, sideSize, isFlag, false),
  };
}

/** The saved tabs, or null when there are none (or storage is unavailable) */
export function loadTabs(maxDecks: number): SavedTabs | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    const open = Array.isArray(data?.open)
      ? [...new Set<number>(data.open)].filter((slot) => Number.isInteger(slot) && slot >= 0 && slot < maxDecks)
      : [];
    if (!open.length) return null;
    const decks: Record<number, SavedDeck> = {};
    for (const slot of open) {
      const deck = validDeck(data.decks?.[slot]);
      if (deck) decks[slot] = deck;
    }
    return { open, active: open.includes(data.active) ? data.active : open[0], decks };
  } catch {
    return null;
  }
}

export function saveTabs(tabs: SavedTabs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(tabs));
  } catch {
    // Storage full or blocked (private window): the tabs just aren't kept
  }
}
