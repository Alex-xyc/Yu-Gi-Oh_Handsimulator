import Button from "@mui/material/Button";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Overlay, type Toast, Toasts } from "./components/common";
import { CompareView } from "./components/CompareView";
import { type DeckTab, DeckTabs, MAX_DECKS } from "./components/DeckTabs";
import { DeckWorkspace } from "./components/DeckWorkspace";
import { loadTabs, saveTabs, type SavedTabs } from "./storage";
import { type DeckSetup, useDeckSetup } from "./useDeckSetup";

/** One deck per possible tab: a fixed number of hooks, so a tab only picks a free slot */
function useDeckSlots(saved: SavedTabs | null): DeckSetup[] {
  const d = saved?.decks ?? {};
  const slots = [useDeckSetup(d[0]), useDeckSetup(d[1]), useDeckSetup(d[2]), useDeckSetup(d[3]), useDeckSetup(d[4]), useDeckSetup(d[5])];
  // biome-ignore lint/correctness/useExhaustiveDependencies: the same array while every slot is the same
  return useMemo(() => slots, slots);
}

/** Each tab's name: its .ydk file's name, else `untitled` ("New deck"); repeats get " (1)", " (2)",
 *  … in tab order */
function tabNames(setups: DeckSetup[], untitled: string): string[] {
  const seen = new Map<string, number>();
  return setups.map((setup) => {
    const name = (setup.cards && setup.name) || untitled;
    const repeats = seen.get(name) ?? 0;
    seen.set(name, repeats + 1);
    return repeats ? `${name} (${repeats})` : name;
  });
}

export default function App() {
  const { t } = useTranslation();
  // The tabs open before the page was refreshed, read once
  const [saved] = useState(() => loadTabs(MAX_DECKS));
  const slots = useDeckSlots(saved);
  /** The open tabs' slots, in tab order */
  const [open, setOpen] = useState<number[]>(saved?.open ?? [0]);
  const [active, setActive] = useState(saved?.active ?? 0);

  // Keep the open tabs and their decks and labels, so a refresh brings them back
  useEffect(() => {
    const decks = Object.fromEntries(open.map((slot) => {
      const { cards, side, name, tags, custom, sided, sideTags, sideCustom, sideFromMain } = slots[slot];
      return [slot, { cards, side, name, tags, custom, sided, sideTags, sideCustom, sideFromMain }];
    }));
    saveTabs({ open, active, decks });
  }, [open, active, slots]);

  const [comparing, setComparing] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showError = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message }]);
    setTimeout(() => setToasts((t) => t.filter((toast) => toast.id !== id)), 4500);
  }, []);

  const tabs = useMemo((): DeckTab[] => {
    const names = tabNames(open.map((slot) => slots[slot]), t("app.newDeck"));
    return open.map((slot, i) => ({ slot, name: names[i], size: slots[slot].cards ? slots[slot].size : null }));
  }, [open, slots, t]);

  const addTab = () => {
    const slot = Array.from({ length: MAX_DECKS }, (_, i) => i).find((i) => !open.includes(i));
    if (slot === undefined) return showError(t("app.tooManyDecks", { count: MAX_DECKS }));
    setOpen([...open, slot]);
    setActive(slot);
  };

  const closeTab = (slot: number) => {
    if (open.length <= 1) return;
    const index = open.indexOf(slot);
    const rest = open.filter((s) => s !== slot);
    setOpen(rest);
    if (active === slot) setActive(rest[Math.min(index, rest.length - 1)]);
    slots[slot].reset();
  };

  const compareDecks = useMemo(
    () => tabs.map((tab) => ({ ...tab, setup: slots[tab.slot] })),
    [tabs, slots],
  );
  const closeCompare = useCallback(() => setComparing(false), []);

  // While the comparison is open, the page behind it can't be focused or read out
  const page = useRef<HTMLDivElement>(null);
  useEffect(() => { if (page.current) page.current.inert = comparing; }, [comparing]);

  return (
    <div className="app">
      <div ref={page}>
        <DeckTabs tabs={tabs} active={active} onSelect={setActive} onClose={closeTab} onAdd={addTab} />

        <header className="topbar">
          <div className="brand">
            <img className="logo" src="/icon-192.png" alt="" />
            <div>
              <h1>{t("app.name")}</h1>
              <span className="muted small">{t("app.tagline")}</span>
            </div>
          </div>
          <Button variant="outlined" color="primary" onClick={() => setComparing(true)}>
            <span className="max-sm:hidden">{t("app.compareLong")}</span><span className="sm:hidden">{t("app.compareShort")}</span>
          </Button>
        </header>

        {/* Keyed by slot: closing a tab unmounts it, so a reopened slot starts fresh */}
        {tabs.map(({ slot, name }) => (
          <DeckWorkspace key={slot} setup={slots[slot]} name={name} active={slot === active}
                         shortcuts={!comparing} onError={showError} />
        ))}
      </div>

      {/* Built once at start-up and kept, so opening and closing it is only the animation */}
      <Overlay open={comparing} onClose={closeCompare} label={t("compare.title")} keepMounted asWindow>
        <CompareView decks={compareDecks} onClose={closeCompare} onError={showError} />
      </Overlay>

      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((toast) => toast.id !== id))} />
    </div>
  );
}
