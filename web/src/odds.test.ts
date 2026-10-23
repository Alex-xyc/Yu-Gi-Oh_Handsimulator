import { describe, expect, it } from "vitest";
import { atLeast, choose } from "./odds";

describe("choose", () => {
  it("counts combinations", () => {
    expect(choose(5, 0)).toBe(1);
    expect(choose(5, 2)).toBe(10);
    expect(choose(40, 5)).toBe(658008);
    expect(choose(37, 5)).toBe(435897);
  });

  it("is 0 outside 0..n", () => {
    expect(choose(5, -1)).toBe(0);
    expect(choose(5, 6)).toBe(0);
  });
});

describe("atLeast", () => {
  it("matches 1 - C(n - k, h) / C(n, h) for at least one", () => {
    // 3 copies in 40, going first and second (as tests/test_core_modules.py)
    expect(atLeast(40, 3, 5, 1)).toBeCloseTo(1 - choose(37, 5) / choose(40, 5), 12);
    expect(atLeast(40, 3, 6, 1)).toBeCloseTo(1 - choose(37, 6) / choose(40, 6), 12);
  });

  it("is certain for at least none, and impossible beyond the copies or the cards drawn", () => {
    expect(atLeast(40, 12, 5, 0)).toBeCloseTo(1, 12);
    expect(atLeast(40, 2, 5, 3)).toBe(0);
    expect(atLeast(40, 12, 5, 6)).toBe(0);
    expect(atLeast(40, 0, 5, 1)).toBe(0);
  });

  it("is certain when every card is one of them", () => {
    expect(atLeast(40, 40, 5, 5)).toBeCloseTo(1, 12);
    expect(atLeast(40, 40, 6, 6)).toBeCloseTo(1, 12);
  });

  it("goes down as more are wanted, and up going second", () => {
    for (let wanted = 1; wanted <= 5; wanted++) {
      expect(atLeast(40, 12, 5, wanted + 1)).toBeLessThan(atLeast(40, 12, 5, wanted));
      expect(atLeast(40, 12, 6, wanted)).toBeGreaterThan(atLeast(40, 12, 5, wanted));
    }
  });

  it("adds up the exact chances", () => {
    // P(at least 2) = P(at least 1) - P(exactly 1)
    const exactlyOne = (choose(12, 1) * choose(28, 4)) / choose(40, 5);
    expect(atLeast(40, 12, 5, 2)).toBeCloseTo(atLeast(40, 12, 5, 1) - exactlyOne, 12);
  });
});
