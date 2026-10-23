// Hypergeometric odds worked out in the browser (the side deck cards, and the opening hand going
// second), the same way the server works out the rest (src/ygo_calc/core/probability.py)

/** n choose k */
export function choose(n: number, k: number) {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let i = 1; i <= k; i++) result = (result * (n - k + i)) / i;
  return result;
}

/** Chance of at least 1, 2, … of `copies` cards in the first `cards` of a `deckSize` deck, up to
 *  `max` (no more than there are copies) */
export function atLeastEach(deckSize: number, copies: number, cards: number, max = cards) {
  return Array.from({ length: Math.min(copies, max) }, (_, i) => atLeast(deckSize, copies, cards, i + 1));
}

/** Chance of at least `wanted` of `copies` cards in the first `cards` of a `deckSize` deck */
export function atLeast(deckSize: number, copies: number, cards: number, wanted: number) {
  let p = 0;
  for (let x = wanted; x <= Math.min(copies, cards); x++) {
    p += (choose(copies, x) * choose(deckSize - copies, cards - x)) / choose(deckSize, cards);
  }
  return p;
}
