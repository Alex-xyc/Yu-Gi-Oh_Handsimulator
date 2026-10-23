import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { DeckCard } from "./api";
import { loadTabs, type SavedTabs, saveTabs } from "./storage";

const KEY = "ygo-hand-simulator:decks:v1";

/** A localStorage stand-in (the tests run without a browser) */
function memoryStorage() {
  const items = new Map<string, string>();
  return {
    getItem: (key: string) => items.get(key) ?? null,
    setItem: (key: string, value: string) => { items.set(key, value); },
    removeItem: (key: string) => { items.delete(key); },
    clear: () => items.clear(),
  };
}

const cards: DeckCard[] = [
  { name: "Ash Blossom & Joyous Spring", id: "14558127", copies: 3 },
  { name: "Pot of Prosperity", id: "84211599", copies: 1 },
];
const side: DeckCard[] = [{ name: "Nibiru, the Primal Being", id: "27204311", copies: 2 }];

const store = (data: unknown) => localStorage.setItem(KEY, JSON.stringify(data));

describe("storage", () => {
  beforeEach(() => {
    vi.stubGlobal("localStorage", memoryStorage());
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("brings back what was saved", () => {
    const tabs: SavedTabs = {
      open: [0, 2],
      active: 2,
      decks: {
        0: {
          cards, side, name: "Snake-Eye", tags: ["engine", "engine", "engine", "non_engine"],
          custom: ["custom-starter", "custom-starter", "custom-starter", ""],
          sided: [false, false, false, true], sideTags: ["", "brick"], sideCustom: ["", ""], sideFromMain: [false, true],
        },
        2: { cards: null, side: [], name: null, tags: [] },
      },
    };
    saveTabs(tabs);
    expect(loadTabs(6)).toEqual(tabs);
  });

  it("is null with nothing saved, or something that isn't JSON", () => {
    expect(loadTabs(6)).toBeNull();
    localStorage.setItem(KEY, "{not json");
    expect(loadTabs(6)).toBeNull();
    store({ open: [], active: 0, decks: {} });
    expect(loadTabs(6)).toBeNull();
  });

  it("keeps only valid, distinct open slots, and an active one among them", () => {
    store({ open: [1, 1, -1, 7, 2.5, "3", 4], active: 5, decks: {} });
    expect(loadTabs(6)).toEqual({ open: [1, 4], active: 1, decks: {} });
  });

  it("drops a deck whose cards aren't valid", () => {
    store({ open: [0, 1], active: 0, decks: {
      0: { cards: [{ name: "Ash", id: "14558127", copies: 0 }], name: "Bad", tags: [] },
      1: { cards: [{ name: "Ash", copies: 1 }], name: "No ID", tags: [] },
    } });
    expect(loadTabs(6)?.decks).toEqual({});
  });

  it("replaces per-copy lists that don't fit the deck instead of dropping it", () => {
    store({ open: [0], active: 0, decks: {
      0: { cards, side: "not a side deck", name: 42, tags: ["engine"], sided: [1, 2, 3, 4] },
    } });
    expect(loadTabs(6)?.decks[0]).toEqual({
      cards, side: null, name: null,
      tags: ["", "", "", ""],
      custom: ["", "", "", ""],
      sided: [false, false, false, false],
      sideTags: [], sideCustom: [], sideFromMain: [],
    });
  });

  it("drops unknown labels", () => {
    store({ open: [0], active: 0, decks: { 0: { cards, name: null, tags: ["engine", "engine", "engine", "boss"] } } });
    expect(loadTabs(6)?.decks[0].tags).toEqual(["", "", "", ""]);
  });

  it("does without storage when it's blocked or full", () => {
    vi.stubGlobal("localStorage", {
      getItem: () => { throw new Error("SecurityError"); },
      setItem: () => { throw new Error("QuotaExceededError"); },
    });
    expect(loadTabs(6)).toBeNull();
    expect(() => saveTabs({ open: [0], active: 0, decks: {} })).not.toThrow();
  });
});
