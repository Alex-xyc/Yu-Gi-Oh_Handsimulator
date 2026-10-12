import Button from "@mui/material/Button";
import { motion } from "framer-motion";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, Category, DrawResult, Stats } from "./api";
import { Overlay, Spinner, Toast, Toasts } from "./components/common";
import { CompareView } from "./components/CompareView";
import { DeckLoader } from "./components/DeckPanel";
import { DecklistView, TagControls, TagGrid, useTagEditor } from "./components/DecklistView";
import { HandView } from "./components/HandView";
import { StatsView } from "./components/StatsView";
import { DeckSetup, useDeckSetup } from "./useDeckSetup";

/** Which compare deck is being labelled in the overlay */
type TagTarget = 0 | 1;

export default function App() {
  const main = useDeckSetup();
  const compareA = useDeckSetup();
  const compareB = useDeckSetup();
  const setupFor = (target: TagTarget): DeckSetup => (target === 0 ? compareA : compareB);

  const [stats, setStats] = useState<Stats | null>(null);
  const [draw, setDraw] = useState<DrawResult | null>(null);
  const [drawId, setDrawId] = useState(0);
  const [drawing, setDrawing] = useState(false);

  const [tagging, setTagging] = useState<TagTarget | null>(null);
  const [comparing, setComparing] = useState(false);
  const compareStarted = useRef(false);
  const [toasts, setToasts] = useState<Toast[]>([]);

  const showError = useCallback((message: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, message }]);
    setTimeout(() => setToasts((t) => t.filter((toast) => toast.id !== id)), 4500);
  }, []);

  // A new deck clears the old hand
  useEffect(() => { setDraw(null); }, [main.cards]);

  // Keep the statistics in step with the labels (debounced while clicking through cards)
  const mainBody = main.body("Deck");
  const bodyKey = mainBody ? JSON.stringify(mainBody) : null;
  useEffect(() => {
    if (!bodyKey) {
      if (!main.cards) setStats(null);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.stats(JSON.parse(bodyKey), controller.signal)
        .then(setStats)
        .catch((e) => { if (e.name !== "AbortError") showError(e.message); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [bodyKey, main.cards, showError]);

  const drawHand = async () => {
    if (!mainBody) return showError("Load a deck first.");
    setDrawing(true);
    try {
      const result = await api.draw(mainBody);
      setDraw(result);
      setStats(result.stats);
      setDrawId((n) => n + 1);
    } catch (e) {
      showError(e instanceof Error ? e.message : "Draw failed.");
    } finally {
      setDrawing(false);
    }
  };

  const compareSetups = useMemo((): [DeckSetup, DeckSetup] => [compareA, compareB], [compareA, compareB]);
  const closeCompare = useCallback(() => setComparing(false), []);

  // Until the comparison is first opened, Deck 1 follows the deck loaded here. It's copied in
  // the background, not on opening, so opening the comparison is only the animation.
  useEffect(() => {
    if (!compareStarted.current && main.cards) compareA.copyFrom(main);
  }, [main, compareA]);

  const openCompare = () => {
    compareStarted.current = true;
    setComparing(true);
  };

  const finishTagging = (tags: Category[]) => {
    if (tagging !== null) setupFor(tagging).applyTags(tags);
    setTagging(null);
  };

  // Labelling on the page: the controls and the cards are in different panels
  const editor = useTagEditor({
    deckList: main.deckList, tags: main.tags, onChange: main.applyTags,
    shortcuts: !comparing && tagging === null,
  });
  const taggingSetup = tagging !== null ? setupFor(tagging) : null;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <img className="logo" src="/icon-192.png" alt="" />
          <div>
            <h1>Hand Simulator</h1>
            <span className="muted small">Yu-Gi-Oh! opening-hand odds · by Xin Yuan</span>
          </div>
        </div>
        <Button variant="outlined" color="primary" onClick={openCompare}>Compare decks</Button>
      </header>

      <main className="layout">
        <motion.section className="card-panel setup" layout>
          <DeckLoader setup={main} onError={showError} />
        </motion.section>

        {/* Left: labelling controls above the test hand. Right: only the decklist, which fills
            the left column's height (h-0 + min-h-full) and scrolls inside it. */}
        <div className="grid gap-4 lg:grid-cols-2">
          <section className="card-panel flex flex-col gap-5">
            <div>
              <h2 className="mb-3">Label your decklist</h2>
              <TagControls editor={editor} />
            </div>
            <div className="flex flex-col border-t border-line pt-4">
              <div className="mb-2 flex items-center justify-between gap-3">
                <h2 className="mb-0">Test hand</h2>
                <Button variant="contained" className="min-w-[130px]" onClick={drawHand} disabled={!main.cards || drawing}>
                  {drawing ? <Spinner /> : draw ? "Draw again" : "Draw hand"}
                </Button>
              </div>
              <HandView result={draw} drawId={drawId} idByName={main.idByName} tagged={main.labelled} />
            </div>
          </section>

          <section className="card-panel flex flex-col max-lg:max-h-[560px] lg:h-0 lg:min-h-full">
            <h2 className="mb-2">
              Decklist{main.cards && <span className="text-xs font-normal text-muted"> · {main.size} cards</span>}
            </h2>
            {main.cards ? (
              <TagGrid editor={editor} idByName={main.idByName} scroll />
            ) : (
              <p className="m-0 grid flex-1 place-items-center p-6 text-center text-muted">
                Load a deck, then click its cards to label them as engine, non-engine or brick.
              </p>
            )}
          </section>
        </div>

        <section className="card-panel stats-panel min-h-[320px]">
          <h2>Probabilities</h2>
          <StatsView stats={stats} tagged={main.labelled} hasHand={draw !== null} />
        </section>
      </main>

      {/* Escape closes only the top overlay: tagging can be open on top of the comparison */}
      {/* Built once at start-up and kept, so opening and closing it is only the animation */}
      <Overlay open={comparing} onClose={() => tagging === null && setComparing(false)} label="Compare decks" keepMounted>
        <CompareView setups={compareSetups} onClose={closeCompare} onTag={setTagging} onError={showError} />
      </Overlay>

      <Overlay open={taggingSetup !== null} onClose={() => setTagging(null)} label="Label your decklist">
        {taggingSetup && (
          <DecklistView deckList={taggingSetup.deckList} idByName={taggingSetup.idByName}
                        initialTags={taggingSetup.tags} onDone={finishTagging} />
        )}
      </Overlay>

      <Toasts toasts={toasts} onDismiss={(id) => setToasts((t) => t.filter((toast) => toast.id !== id))} />
    </div>
  );
}
