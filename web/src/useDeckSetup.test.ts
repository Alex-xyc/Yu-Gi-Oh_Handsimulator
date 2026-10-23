import { describe, expect, it } from "vitest";
import type { DeckCard } from "./api";
import { type Decks, swapCards } from "./useDeckSetup";

const card = (name: string, copies: number): DeckCard => ({ name, id: name.length.toString(), copies });

// Main: Ash x2 (engine), Maxx "C" x1 (brick); side: Nibiru x2
const decks: Decks = {
  cards: [card("Ash", 2), card("Maxx", 1)],
  tags: ["engine", "engine", "brick"],
  custom: ["", "", "custom-a"],
  sided: [false, false, false],
  side: [card("Nibiru", 2)],
  sideTags: ["", ""],
  sideCustom: ["", ""],
  sideFromMain: [false, false],
};

describe("swapCards", () => {
  it("swaps copies, each taking its label, and marks the ones out of their own deck", () => {
    expect(swapCards(decks, [2], [0])).toEqual({
      cards: [card("Ash", 2), card("Nibiru", 1)],
      tags: ["engine", "engine", ""],
      custom: ["", "", ""],
      sided: [false, false, true],
      side: [card("Nibiru", 1), card("Maxx", 1)],
      sideTags: ["", "brick"],
      sideCustom: ["", "custom-a"],
      sideFromMain: [false, true],
    });
  });

  it("puts a sided-in copy with its other copies, taking their label when it has none", () => {
    const next = swapCards({ ...decks, side: [card("Ash", 1)], sideTags: [""], sideFromMain: [false] }, [], [0]);
    expect(next.cards).toEqual([card("Ash", 3), card("Maxx", 1)]);
    expect(next.tags).toEqual(["engine", "engine", "engine", "brick"]);
    expect(next.sided).toEqual([false, false, true, false]);
    expect(next.side).toEqual([]);
  });

  it("undoes a swap when the copies go back", () => {
    const swapped = swapCards(decks, [2], [0]);
    // Nibiru (deck position 2) out, Maxx (side position 1) back in
    const back = swapCards(swapped, [2], [1]);
    expect(back.cards).toEqual([card("Ash", 2), card("Maxx", 1)]);
    expect(back.tags).toEqual(decks.tags);
    expect(back.custom).toEqual(decks.custom);
    expect(back.sided).toEqual([false, false, false]);
    expect(back.side).toEqual([card("Nibiru", 2)]);
    expect(back.sideFromMain).toEqual([false, false]);
  });

  it("can take more out than it puts in", () => {
    const next = swapCards(decks, [0, 1], []);
    expect(next.cards).toEqual([card("Maxx", 1)]);
    expect(next.side).toEqual([card("Nibiru", 2), card("Ash", 2)]);
    expect(next.sideTags).toEqual(["", "", "engine", "engine"]);
    expect(next.sideFromMain).toEqual([false, false, true, true]);
  });
});
