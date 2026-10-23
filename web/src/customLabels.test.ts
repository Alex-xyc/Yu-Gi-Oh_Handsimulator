import { describe, expect, it } from "vitest";
import { compareLabels, countLabels, type CustomLabel } from "./customLabels";
import { atLeast } from "./odds";

const starter: CustomLabel = { id: "custom-starter", name: "Starter", color: "#a78bfa" };
const trap: CustomLabel = { id: "custom-trap", name: "Hand trap", color: "#fb923c" };

describe("countLabels", () => {
  it("counts each label's copies, overall and per card", () => {
    const deckList = ["Ash", "Ash", "Ash", "Pot"];
    const custom = ["custom-trap", "custom-trap", "", "custom-starter"];
    expect(countLabels([starter, trap], deckList, custom)).toEqual([
      { ...starter, count: 1, cards: { Pot: 1 } },
      { ...trap, count: 2, cards: { Ash: 2 } },
    ]);
  });
});

describe("compareLabels", () => {
  it("gives each deck's odds up to the most either has, and the average per hand", () => {
    const [group] = compareLabels({ sizes: [40, 45], labels: [{ ...starter, a: 2, b: 0 }] }, 5);
    expect(group.rows.map((row) => row.label)).toEqual(["At least 1 Starter", "At least 2 Starter"]);
    expect(group.rows[1].a).toBeCloseTo(atLeast(40, 2, 5, 2));
    expect(group.rows.every((row) => row.b === 0 && row.better === null)).toBe(true);
    expect(group.average).toEqual({ label: "Starter", a: 0.25, b: 0 });
  });
});
