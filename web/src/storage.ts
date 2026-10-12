// The open deck tabs, kept in the browser (localStorage) so a page refresh brings them back

import { Category, DeckCard } from "./api";

const KEY = "ygo-hand-simulator:decks:v1";

export interface SavedDeck {
  cards: DeckCard[] | null;
  name: string | null;
  tags: Category[];
}

export interface SavedTabs {
  /** The open tabs' slots, in tab order */
  open: number[];
  active: number;
  /** Each open slot's deck */
  decks: Record<number, SavedDeck>;
}

const TAGS = new Set<string>(["", "engine", "non_engine", "brick"]);

/** A saved deck as stored, or null when it isn't one (old format, edited by hand, …) */
function validDeck(value: unknown): SavedDeck | null {
  if (!value || typeof value !== "object") return null;
  const { cards, name, tags } = value as Record<string, unknown>;
  if (cards === null) return { cards: null, name: null, tags: [] };
  if (!Array.isArray(cards) || !cards.every((c) =>
    c && typeof c.name === "string" && typeof c.id === "string" && Number.isInteger(c.copies) && c.copies > 0)) return null;
  const size = cards.reduce((total: number, card: DeckCard) => total + card.copies, 0);
  // Labels that don't fit the deck are dropped rather than the whole deck
  const fits = Array.isArray(tags) && tags.length === size && tags.every((t) => TAGS.has(t));
  return {
    cards,
    name: typeof name === "string" ? name : null,
    tags: fits ? (tags as Category[]) : Array<Category>(size).fill(""),
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
