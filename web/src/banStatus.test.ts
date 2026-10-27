import { describe, expect, it } from "vitest";
import type { DeckCard } from "./api";
import { genesysTotal, rememberStatuses } from "./banStatus";

const card = (id: string, copies: number, points?: number): DeckCard =>
  ({ name: `Card ${id}`, id, copies, status: "", ...(points === undefined ? {} : { points }) });

describe("Genesys points", () => {
  it("adds up every copy's points", () => {
    rememberStatuses([card("101", 3, 18), card("102", 1, 50), card("103", 2, 0)]);
    expect(genesysTotal([card("101", 3), card("102", 1), card("103", 2)])).toBe(104);
  });

  it("is unknown while a card's points are being looked up", () => {
    // Sent without points (a deck saved before they were): looked up rather than taken as 0
    rememberStatuses([card("201", 1)]);
    expect(genesysTotal([card("101", 1), card("201", 1)])).toBeNull();
  });

  it("counts cards without an ID as 0", () => {
    expect(genesysTotal([card("101", 1), card("", 2)])).toBe(18);
  });
});
