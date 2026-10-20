// Each card's TCG banlist status, looked up once per page load (not kept with saved decks, so a new
// banlist shows up without loading the deck again). Cards ask for theirs as they're shown; the
// requests are gathered into one call.

import { useEffect, useSyncExternalStore } from "react";
import { api, BanStatus, DeckCard } from "./api";

const statuses = new Map<string, BanStatus>();
const listeners = new Set<() => void>();
/** IDs waiting for the next lookup, and the ones being (or already) looked up */
const pending = new Set<string>();
const requested = new Set<string>();
/** The most IDs one lookup takes (the server's limit, the largest deck) */
const PER_REQUEST = 60;

function notify() {
  for (const listener of listeners) listener();
}

/** Statuses that came with a card list (a deck just loaded), so they aren't looked up again */
export function rememberStatuses(cards: DeckCard[]) {
  let changed = false;
  for (const card of cards) {
    if (card.id && card.status !== undefined) {
      requested.add(card.id);
      if (statuses.get(card.id) !== card.status) {
        statuses.set(card.id, card.status);
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
        for (const id of batch) statuses.set(id, infos[id]?.status ?? "");
        notify();
      })
      // Shown without a status; asked for again next time the page loads
      .catch(() => {});
  }
}

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
  const valid = !!id && /^\d+$/.test(id);
  useEffect(() => { if (valid) request(id); }, [id, valid]);
  return useSyncExternalStore(subscribe, () => (valid ? statuses.get(id) ?? "" : ""));
}
