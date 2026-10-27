// Each card's TCG banlist status and Genesys points, looked up once per page load (not kept with
// saved decks, so a new banlist or points list shows up without loading the deck again). Cards ask
// for theirs as they're shown; the requests are gathered into one call.
//
// Also which of the two the cards show: the TCG banlist, or Genesys points (the Genesys format has
// no banlist: each card costs points, and a deck may spend at most GENESYS_CAP). The choice is the
// same in every tab and kept in the browser (localStorage).

import { useEffect, useSyncExternalStore } from "react";
import { api, type BanStatus, type DeckCard } from "./api";

const statuses = new Map<string, BanStatus>();
const points = new Map<string, number>();
const listeners = new Set<() => void>();
/** IDs waiting for the next lookup, and the ones being (or already) looked up */
const pending = new Set<string>();
const requested = new Set<string>();
/** The most IDs one lookup takes (the server's limit, the largest deck) */
const PER_REQUEST = 60;

/** The most Genesys points a deck may spend */
export const GENESYS_CAP = 100;

const FORMAT_KEY = "ygo-hand-simulator:format:v1";

function loadGenesys(): boolean {
  try {
    return localStorage.getItem(FORMAT_KEY) === "genesys";
  } catch {
    return false;
  }
}

let genesys = loadGenesys();

function notify() {
  for (const listener of listeners) listener();
}

/** Show Genesys points on the cards (and the deck's total) instead of the TCG banlist */
export function setGenesys(on: boolean) {
  genesys = on;
  try {
    localStorage.setItem(FORMAT_KEY, on ? "genesys" : "tcg");
  } catch {
    // Storage full or blocked (private window): the choice just isn't kept
  }
  notify();
}

/** Statuses and points that came with a card list (a deck just loaded), so they aren't looked up again */
export function rememberStatuses(cards: DeckCard[]) {
  let changed = false;
  for (const card of cards) {
    // A card list from before points were sent has them looked up with the status
    if (card.id && card.status !== undefined && card.points !== undefined) {
      requested.add(card.id);
      if (statuses.get(card.id) !== card.status || points.get(card.id) !== card.points) {
        statuses.set(card.id, card.status);
        points.set(card.id, card.points);
        changed = true;
      }
    }
  }
  if (changed) notify();
}

function lookUp() {
  const ids = [...pending];
  pending.clear();
  for (let start = 0; start < ids.length; start += PER_REQUEST) {
    const batch = ids.slice(start, start + PER_REQUEST);
    api.cardInfo(batch)
      .then((infos) => {
        for (const id of batch) {
          statuses.set(id, infos[id]?.status ?? "");
          points.set(id, infos[id]?.points ?? 0);
        }
        notify();
      })
      // Shown without a status or points; asked for again next time the page loads
      .catch(() => {});
  }
}

const isCardId = (id: string | undefined): id is string => !!id && /^\d+$/.test(id);

function request(id: string) {
  if (requested.has(id)) return;
  requested.add(id);
  if (!pending.size) setTimeout(lookUp, 0);
  pending.add(id);
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

/** A card's status ("" while unknown or not on the banlist) */
export function useBanStatus(id: string | undefined): BanStatus {
  const valid = isCardId(id);
  useEffect(() => { if (valid) request(id); }, [id, valid]);
  return useSyncExternalStore(subscribe, () => (valid ? statuses.get(id) ?? "" : ""));
}

/** A card's Genesys points (0 while unknown, and for most cards) */
export function useGenesysPoints(id: string | undefined): number {
  const valid = isCardId(id);
  useEffect(() => { if (valid) request(id); }, [id, valid]);
  return useSyncExternalStore(subscribe, () => (valid ? points.get(id) ?? 0 : 0));
}

/** The Genesys points of every copy of these cards, or null while some are still being looked up
 *  (cards without an ID count as 0) */
export function genesysTotal(cards: DeckCard[]): number | null {
  let total = 0;
  for (const card of cards) {
    if (!isCardId(card.id)) continue;
    const cost = points.get(card.id);
    if (cost === undefined) return null;
    total += cost * card.copies;
  }
  return total;
}

/** genesysTotal, kept up to date as the cards' points come in */
export function useGenesysTotal(cards: DeckCard[]): number | null {
  useEffect(() => { for (const card of cards) if (isCardId(card.id)) request(card.id); }, [cards]);
  return useSyncExternalStore(subscribe, () => genesysTotal(cards));
}

/** Whether the cards show Genesys points instead of the TCG banlist */
export function useGenesys(): boolean {
  return useSyncExternalStore(subscribe, () => genesys);
}
