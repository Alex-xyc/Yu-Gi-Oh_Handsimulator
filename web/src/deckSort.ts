// The decklist's sort orders (the Name and Label buttons above the cards)

import type { Category, DeckCard } from "./api";

export type SortMode = "name" | "label";

/** Monsters, then spells, then traps, each by subtype; unknown cards last */
const KIND_ORDER = [
  "monster",
  "spell_normal", "spell_quick_play", "spell_continuous", "spell_field", "spell_equip", "spell_ritual",
  "trap_normal", "trap_continuous", "trap_counter",
];
const LABEL_ORDER: Record<Category, number> = { engine: 0, non_engine: 1, brick: 2, "": 3 };

/** Deck positions sorted by name within each card type (the arrow flips the names, not the
 *  types), or by label (the arrow flips the labels; unlabelled cards stay last), then type, then name */
export function sortedOrder(mode: SortMode, descending: boolean, cards: DeckCard[] | null, deckList: string[], tags: Category[]) {
  const kinds = new Map((cards ?? []).map((card) => [card.name, card.kind ?? ""]));
  const kindRank = (i: number) => {
    const rank = KIND_ORDER.indexOf(kinds.get(deckList[i]) ?? "");
    return rank < 0 ? KIND_ORDER.length : rank;
  };
  const byName = (a: number, b: number) => deckList[a].localeCompare(deckList[b]) || a - b;
  const dir = descending ? -1 : 1;
  const unlabelled = (i: number) => (tags[i] ? 0 : 1);
  const compare = mode === "name"
    ? (a: number, b: number) => kindRank(a) - kindRank(b) || dir * byName(a, b)
    : (a: number, b: number) => unlabelled(a) - unlabelled(b) || dir * (LABEL_ORDER[tags[a]] - LABEL_ORDER[tags[b]])
      || kindRank(a) - kindRank(b) || byName(a, b);
  return deckList.map((_, i) => i).sort(compare);
}
