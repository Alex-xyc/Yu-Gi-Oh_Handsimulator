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
  stats: Stats;
}

export interface Comparison {
  hand_size: number;
  names: [string, string];
  composition: { label: string; a: number; b: number }[];
  odds: { label: string; a: number; b: number; better: 1 | 2 | null }[];
  averages: { label: string; a: number; b: number }[];
  cards: { name: string; a_copies: number; b_copies: number; changed: boolean; a: number; b: number }[];
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
  stats: (deck: DeckSetupBody, signal?: AbortSignal) => post<Stats>("/api/stats", deck, signal),
  draw: (deck: DeckSetupBody) => post<DrawResult>("/api/draw", { deck }),
  compare: (decks: [DeckSetupBody, DeckSetupBody], handSize: number) =>
    post<Comparison>("/api/compare", { decks, hand_size: handSize }),
};

export function cardImageUrl(id: string | undefined, size: "small" | "full" = "small"): string | null {
  return id && /^\d+$/.test(id) ? `/api/cards/${id}/image?size=${size}` : null;
}

export function percent(p: number, digits = 1): string {
  return `${(p * 100).toFixed(digits)}%`;
}
