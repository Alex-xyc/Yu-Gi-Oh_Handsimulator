// Types and calls for the Python API (src/ygo_calc/web/server.py)

export type Category = "brick" | "non_engine" | "engine" | "";
export const CATEGORIES = ["engine", "non_engine", "brick"] as const;
export type TagKey = (typeof CATEGORIES)[number];

export const CATEGORY_LABELS: Record<TagKey, string> = {
  engine: "Engine",
  non_engine: "Non-Engine",
  brick: "Brick",
};

export interface DeckCard {
  name: string;
  id: string;
  copies: number;
  /** "monster", "spell_<subtype>" or "trap_<subtype>" ("" or missing if unknown, e.g. saved
   *  before it was sent); for sorting the decklist */
  kind?: string;
  /** A monster's level */
  level?: number;
}

export interface Counts {
  brick: number;
  non_engine: number;
  engine: number;
}

export interface DeckSetupBody {
  name: string;
  cards: { name: string; copies: number }[];
  tags: Category[] | null;
  counts: Counts | null;
}

export interface CardOdds {
  name: string;
  copies: number;
  group: TagKey | "mixed" | "untagged";
  first: number;
  second: number;
}

export interface Stats {
  deck_size: number;
  hand_size: number;
  /** Opening-hand combinations, e.g. "1+ engine & no bricks" */
  combinations: { label: string; probability: number }[];
  /** Average number of each label in the opening hand */
  averages: Record<TagKey, number>;
  counts: Record<TagKey | "untagged", number>;
  matrix: (number | null)[][];
  /** Chance of at least 1, 2, … hand_size cards of each category */
  at_least: Record<TagKey, number[]>;
  bricks: { open: number; draw_sixth: number; by_turn_one: number };
  sixth_card:
    | (Record<TagKey, { remaining: number; probability: number }> & { deck_remaining: number })
    | null;
  cards: CardOdds[];
}

export interface DrawnCard {
  name: string;
  category: Category;
}

export interface DrawResult {
  hand: DrawnCard[];
  sixth: DrawnCard | null;
  /** The next cards after the 6th, for extra draws */
  draws: DrawnCard[];
  /** The whole deck in shuffled order (the hand first) */
  deck: DrawnCard[];
  stats: Stats;
}

/** One probability for both decks; better is the deck with the better value, if either */
export interface OddsPair {
  label: string;
  a: number;
  b: number;
  better: 1 | 2 | null;
}

export interface Comparison {
  hand_size: number;
  names: [string, string];
  composition: { label: string; a: number; b: number }[];
  /** Combinations (e.g. 1+ engine & no bricks); also a few of the at_least rows */
  odds: OddsPair[];
  /** Chance of at least 1..hand_size of each category, as on the main page */
  at_least: { key: TagKey; label: string; rows: OddsPair[] }[];
  /** Open with a brick, draw one as the next card, see one by then */
  bricks: OddsPair[];
  averages: { label: string; a: number; b: number }[];
  cards: { name: string; a_copies: number; b_copies: number; changed: boolean; a: number; b: number }[];
}

/** The opening-hand combinations not already in the "X or more" breakdown */
export function combinationOdds(result: Comparison): OddsPair[] {
  const inBreakdown = new Set(result.at_least.flatMap((group) => group.rows.map((row) => row.label)));
  return result.odds.filter((row) => !inBreakdown.has(row.label));
}

export class ApiError extends Error {}

async function post<T>(path: string, body: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
  });
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const data = await response.json();
      if (typeof data.detail === "string") message = data.detail;
    } catch {
      // Not JSON: keep the generic message
    }
    throw new ApiError(message);
  }
  return response.json() as Promise<T>;
}

export const api = {
  loadDeck: (code: string) => post<{ cards: DeckCard[]; size: number }>("/api/decks", { code }),
  /** Each card's kind and level by ID, for decks saved before the card list had them */
  cardInfo: (ids: string[]) => post<Record<string, { kind: string; level: number }>>("/api/decks/info", { ids }),
  /** handSize 6 gives the odds going second */
  stats: (deck: DeckSetupBody, signal?: AbortSignal, handSize = 5) =>
    post<Stats>(`/api/stats?hand_size=${handSize}`, deck, signal),
  draw: (deck: DeckSetupBody) => post<DrawResult>("/api/draw", { deck }),
  compare: (decks: [DeckSetupBody, DeckSetupBody], handSize: number) =>
    post<Comparison>("/api/compare", { decks, hand_size: handSize }),
};

export function cardImageUrl(id: string | undefined, size: "small" | "full" = "small"): string | null {
  return id && /^\d+$/.test(id) ? `/api/cards/${id}/image?size=${size}` : null;
}

/** Decimals to show value with: digits, or more for a small non-zero value so it doesn't round to 0
 * (two significant figures, e.g. 0.022) */
export function decimalsFor(value: number, digits = 1): number {
  const size = Math.abs(value);
  if (size <= 1e-10 || size >= 0.5 * 10 ** -digits) return digits;
  // Round to two significant figures first, so 0.00999 gives 0.010 and not 0.0100
  return Math.min(1 - Math.floor(Math.log10(Number(size.toPrecision(2)))), 12);
}

/** Decimals for a 0..1 chance shown as a percentage */
export const percentDigits = (p: number, digits = 1) => decimalsFor(p * 100, digits);

export function percent(p: number, digits = 1, decimals = percentDigits(p, digits)): string {
  return `${(p * 100).toFixed(decimals)}%`;
}

/** The most characters any of these chances takes as a percentage (to size their column) */
export const percentWidth = (values: number[]) => Math.max(0, ...values.map((p) => percent(p).length));
