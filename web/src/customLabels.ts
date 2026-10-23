// Labels the user makes up (e.g. "Starter", "Hand trap"), for the advanced labelling mode. A card
// copy can have one of them on top of its engine / non-engine / brick label. The labels and
// whether advanced mode is on are shared by every deck tab and kept in the browser (localStorage),
// so a page refresh brings them back; which cards have them is kept with each deck.

import { useSyncExternalStore } from "react";
import { CATEGORY_LABELS, type DrawnCard, type OddsPair } from "./api";
import { atLeastEach } from "./odds";

const KEY = "ygo-hand-simulator:labels:v1";

export interface CustomLabel {
  /** "custom-…", so it never clashes with engine / non_engine / brick */
  id: string;
  name: string;
  color: string;
}

export interface LabelSettings {
  advanced: boolean;
  labels: CustomLabel[];
}

/** The longest name a label can have */
export const MAX_LABEL_NAME = 24;

/** Colours for new labels, apart from the engine / non-engine / brick and side deck colours; dark
 *  text reads on all of them */
const COLORS = ["#a78bfa", "#fb923c", "#f472b6", "#2dd4bf", "#a3e635", "#818cf8", "#fda4af", "#fcd34d"];

export const isCustom = (tool: string) => tool.startsWith("custom-");

const validLabel = (label: unknown): label is CustomLabel => {
  const { id, name, color } = (label ?? {}) as Record<string, unknown>;
  return typeof id === "string" && isCustom(id) && typeof name === "string" && name.trim() !== ""
    && typeof color === "string" && /^#[0-9a-f]{6}$/i.test(color);
};

function load(): LabelSettings {
  try {
    const data = JSON.parse(localStorage.getItem(KEY) ?? "null");
    const labels = Array.isArray(data?.labels) ? (data.labels as unknown[]).filter(validLabel) : [];
    return { advanced: data?.advanced === true, labels };
  } catch {
    return { advanced: false, labels: [] };
  }
}

let settings: LabelSettings = load();
const listeners = new Set<() => void>();

function update(next: LabelSettings) {
  settings = next;
  try {
    localStorage.setItem(KEY, JSON.stringify(next));
  } catch {
    // Storage full or blocked (private window): the labels just aren't kept
  }
  for (const listener of listeners) listener();
}

const subscribe = (listener: () => void) => {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
};

/** Why `name` can't be a label's name (blank, too long, taken), or null when it can */
export function nameProblem(name: string, except?: string): string | null {
  const trimmed = name.trim();
  if (!trimmed) return "Give the label a name";
  if (trimmed.length > MAX_LABEL_NAME) return `At most ${MAX_LABEL_NAME} characters`;
  const taken = [...Object.values(CATEGORY_LABELS), ...settings.labels.filter((l) => l.id !== except).map((l) => l.name)];
  if (taken.some((other) => other.toLowerCase() === trimmed.toLowerCase())) return "There's already a label with that name";
  return null;
}

export const labelSettings = {
  setAdvanced: (advanced: boolean) => update({ ...settings, advanced }),
  /** The new label, or null when the name can't be used */
  add: (name: string): CustomLabel | null => {
    if (nameProblem(name)) return null;
    const used = new Set(settings.labels.map((l) => l.color));
    const color = COLORS.find((c) => !used.has(c)) ?? COLORS[settings.labels.length % COLORS.length];
    const label = { id: `custom-${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`, name: name.trim(), color };
    update({ ...settings, labels: [...settings.labels, label] });
    return label;
  },
  rename: (id: string, name: string) => {
    if (nameProblem(name, id)) return;
    update({ ...settings, labels: settings.labels.map((l) => (l.id === id ? { ...l, name: name.trim() } : l)) });
  },
  /** Cards with it lose it (their copies of its id are ignored from then on) */
  remove: (id: string) => update({ ...settings, labels: settings.labels.filter((l) => l.id !== id) }),
};

/** A custom label and how many copies in the deck have it */
export interface CustomLabelCount extends CustomLabel {
  count: number;
  /** How many copies of each card (by name) have it */
  cards?: Record<string, number>;
}

/** Each custom label with how many copies have it (`custom`: one id per copy of `deckList`) */
export function countLabels(labels: CustomLabel[], deckList: string[], custom: string[]): CustomLabelCount[] {
  return labels.map((label) => {
    const cards: Record<string, number> = {};
    deckList.forEach((name, i) => { if (custom[i] === label.id) cards[name] = (cards[name] ?? 0) + 1; });
    return { ...label, count: Object.values(cards).reduce((total, n) => total + n, 0), cards };
  });
}

/** A drawn card's custom label (looked up by which copy it is), if any */
export type CustomLabelOf = (card: DrawnCard) => CustomLabel | undefined;

/** The custom labels in two compared decks: how many copies each deck has, and the decks' sizes */
export interface CustomComparison {
  sizes: [number, number];
  labels: (CustomLabel & { a: number; b: number })[];
}

/** For each custom label in either deck: the chance of at least 1, 2, … of it in each deck (up to
 *  the most either has, no more than the hand), and its average per hand. Neither deck counts as
 *  better: whether more of a label is good depends on the label. */
export function compareLabels({ sizes, labels }: CustomComparison, handSize: number) {
  return labels.map((label) => {
    const a = atLeastEach(sizes[0], label.a, handSize);
    const b = atLeastEach(sizes[1], label.b, handSize);
    const rows: OddsPair[] = Array.from({ length: Math.max(a.length, b.length) }, (_, i) => ({
      label: `At least ${i + 1} ${label.name}`, a: a[i] ?? 0, b: b[i] ?? 0, better: null,
    }));
    const average = { label: label.name, a: (label.a * handSize) / sizes[0], b: (label.b * handSize) / sizes[1] };
    return { label, rows, average };
  });
}

/** The custom labels and advanced mode, the same in every tab */
export function useLabelSettings(): LabelSettings {
  return useSyncExternalStore(subscribe, () => settings);
}
