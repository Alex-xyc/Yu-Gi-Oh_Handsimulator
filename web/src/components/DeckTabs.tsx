// Browser-like tabs, one per deck, with a "+" to open a new one (up to MAX_DECKS).
// A navigation list of buttons rather than an ARIA tablist, since each tab has its own close
// button; the open one is marked with aria-current.

import Tooltip from "@mui/material/Tooltip";
import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useRef } from "react";

export const MAX_DECKS = 6;

export interface DeckTab {
  /** Which deck slot the tab shows (stable while the tab is open) */
  slot: number;
  name: string;
  /** Card count, or null when no deck is loaded */
  size: number | null;
}

export function DeckTabs({ tabs, active, onSelect, onClose, onAdd }: {
  tabs: DeckTab[];
  active: number;
  onSelect: (slot: number) => void;
  onClose: (slot: number) => void;
  onAdd: () => void;
}) {
  const full = tabs.length >= MAX_DECKS;
  const closable = tabs.length > 1;
  const nav = useRef<HTMLElement>(null);

  // When the row scrolls sideways (phones), keep the open tab in view. Only the row scrolls, not
  // the page (scrollIntoView would also scroll the page up to the tabs).
  // biome-ignore lint/correctness/useExhaustiveDependencies: run again when another tab opens or the tabs change
  useEffect(() => {
    const row = nav.current;
    const tab = row?.querySelector<HTMLElement>(".deck-tab.active");
    if (!row || !tab) return;
    const left = tab.offsetLeft, right = left + tab.offsetWidth;
    if (left < row.scrollLeft) row.scrollLeft = left;
    else if (right > row.scrollLeft + row.clientWidth) row.scrollLeft = right - row.clientWidth;
  }, [active, tabs.length]);

  return (
    <nav className="deck-tabs" aria-label="Decks" ref={nav}>
      <ul className="deck-tab-list">
        {/* popLayout: a closing tab leaves the row at once (it fades out on top of it), so the
            tabs after it slide left straight away instead of waiting, and sometimes staying put */}
        <AnimatePresence initial={false} mode="popLayout">
          {tabs.map((tab) => {
            const current = tab.slot === active;
            return (
              <motion.li key={tab.slot} layout className={`deck-tab ${current ? "active" : ""}`}
                         initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, scale: 0.95 }}
                         transition={{ duration: 0.16 }}>
                <button type="button" className="deck-tab-select" aria-current={current ? "page" : undefined}
                        title={tab.name} onClick={() => onSelect(tab.slot)}
                        onAuxClick={(e) => { if (e.button === 1 && closable) onClose(tab.slot); }}>
                  <span className="deck-tab-name">{tab.name}</span>
                  {tab.size !== null && (
                    <span className="deck-tab-size">{tab.size}<span className="sr-only"> cards</span></span>
                  )}
                </button>
                {closable && (
                  <button type="button" className="deck-tab-close" aria-label={`Close ${tab.name}`}
                          onClick={() => onClose(tab.slot)}>
                    <span aria-hidden="true">×</span>
                  </button>
                )}
              </motion.li>
            );
          })}
        </AnimatePresence>
      </ul>
      <Tooltip title={full ? `Up to ${MAX_DECKS} decks` : "New deck"}>
        {/* A span, so the tooltip still shows while the button is disabled */}
        <span className="flex-none">
          <button type="button" className="deck-tab-add" onClick={onAdd} disabled={full}
                  aria-label={full ? `New deck (up to ${MAX_DECKS} decks)` : "New deck"}>
            <span aria-hidden="true">+</span>
          </button>
        </span>
      </Tooltip>
    </nav>
  );
}
