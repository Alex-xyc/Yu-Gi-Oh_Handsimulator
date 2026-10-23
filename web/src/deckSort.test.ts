import { describe, expect, it } from "vitest";
import type { Category, DeckCard } from "./api";
import { sortedOrder } from "./deckSort";

const card = (name: string, kind?: string): DeckCard => ({ name, id: "1", copies: 1, kind });
const cards = [card("Trap Hole", "trap_normal"), card("Zeta", "monster"), card("Alpha", "monster"),
               card("Called by the Grave", "spell_quick_play"), card("Mystery")];
const deckList = cards.map((c) => c.name);
const tags: Category[] = ["brick", "engine", "", "engine", "non_engine"];

describe("sortedOrder", () => {
  it("sorts by name within each card type, unknown cards last", () => {
    expect(sortedOrder("name", false, cards, deckList, tags)).toEqual([2, 1, 3, 0, 4]);
  });

  it("flips the names but not the types when descending", () => {
    expect(sortedOrder("name", true, cards, deckList, tags)).toEqual([1, 2, 3, 0, 4]);
  });

  it("sorts by label, then type, with unlabelled cards last", () => {
    expect(sortedOrder("label", false, cards, deckList, tags)).toEqual([1, 3, 4, 0, 2]);
  });

  it("flips the labels, keeping unlabelled cards last, when descending", () => {
    expect(sortedOrder("label", true, cards, deckList, tags)).toEqual([0, 4, 1, 3, 2]);
  });

  it("keeps copies of a card in deck order", () => {
    const copies = ["Ash", "Ash", "Ash"];
    expect(sortedOrder("name", false, [card("Ash", "monster")], copies, ["", "", ""])).toEqual([0, 1, 2]);
  });

  it("works before the card types are known", () => {
    expect(sortedOrder("name", false, null, ["B", "A"], ["", ""])).toEqual([1, 0]);
  });
});
