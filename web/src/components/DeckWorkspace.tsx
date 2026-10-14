// One deck tab: loading, labelling, a test hand and the probabilities. Every open tab stays
// mounted (hidden when not selected), so switching tabs keeps its hand, undo history and input.

import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { api, DrawResult, Stats } from "../api";
import { exportStats } from "../export";
import { DeckSetup } from "../useDeckSetup";
import { Overlay, SectionHeader, Spinner } from "./common";
import { DeckLoader } from "./DeckPanel";
import { ExportButton } from "./ExportButton";
import { SortControls, TagControls, TagGrid, useDeckOrder, useTagEditor } from "./DecklistView";
import { HandView } from "./HandView";
import { ShuffledDeckView } from "./ShuffledDeckView";
import { SideDeckView } from "./SideDeckView";
import { SidedCard, StatsView } from "./StatsView";

export function DeckWorkspace({ setup, name, active, shortcuts, onError }: {
  setup: DeckSetup;
  /** The tab's name (names the exported file) */
  name: string;
  /** Whether this is the selected tab */
  active: boolean;
  /** Whether keyboard shortcuts are on (off while an overlay is on top) */
  shortcuts: boolean;
  onError: (message: string) => void;
}) {
  const [stats, setStats] = useState<Stats | null>(null);
  const [draw, setDraw] = useState<DrawResult | null>(null);
  const [drawId, setDrawId] = useState(0);
  const [drawing, setDrawing] = useState(false);
  const [showingDeck, setShowingDeck] = useState(false);
  const closeDeck = useCallback(() => setShowingDeck(false), []);
  // Each opening of the side deck window starts with nothing picked
  const [siding, setSiding] = useState(false);
  const [sideOpenings, setSideOpenings] = useState(0);
  const openSide = () => { setSiding(true); setSideOpenings((n) => n + 1); };
  const closeSide = useCallback(() => setSiding(false), []);
  const id = useId();

  // A new deck clears the old hand
  useEffect(() => { setDraw(null); }, [setup.cards]);

  // Keep the statistics in step with the labels (debounced while clicking through cards)
  const body = setup.body("Deck");
  const bodyKey = body ? JSON.stringify(body) : null;
  useEffect(() => {
    if (!bodyKey) {
      if (!setup.cards) setStats(null);
      return;
    }
    const controller = new AbortController();
    const timer = setTimeout(() => {
      api.stats(JSON.parse(bodyKey), controller.signal)
        .then(setStats)
        .catch((e) => { if (e.name !== "AbortError") onError(e.message); });
    }, 180);
    return () => { clearTimeout(timer); controller.abort(); };
  }, [bodyKey, setup.cards, onError]);

  const drawHand = async () => {
    if (!body) return onError("Load a deck first.");
    setDrawing(true);
    try {
      const result = await api.draw(body);
      setDraw(result);
      setStats(result.stats);
      setDrawId((n) => n + 1);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Draw failed.");
    } finally {
      setDrawing(false);
    }
  };

  /** Everything the panel shows, going first and going second, plus the test hand */
  const exportAll = async () => {
    if (!stats || !body) return;
    const second = await api.stats(body, undefined, 6);
    await exportStats({ name, first: stats, second, draw, labelled: setup.labelled });
  };

  // Labelling on the page: the controls and the cards are in different panels
  const editor = useTagEditor({
    deckList: setup.deckList, tags: setup.tags, onChange: setup.applyTags,
    shortcuts: active && shortcuts && !showingDeck && !siding,
  });
  // The cards with copies sided in, in deck order, for their odds
  const sidedCards = useMemo((): SidedCard[] => (setup.cards ?? []).flatMap((card) => {
    const start = setup.deckList.indexOf(card.name);
    const sided = setup.sided.slice(start, start + card.copies).filter(Boolean).length;
    return sided ? [{ name: card.name, copies: card.copies, sided }] : [];
  }), [setup.cards, setup.deckList, setup.sided]);
  const deckOrder = useDeckOrder(setup.cards, setup.deckList, setup.tags);

  return (
    <main className="layout" hidden={!active} aria-label={name}>
      <section className="card-panel" aria-labelledby={`${id}-load`}>
        <h2 id={`${id}-load`} className="sr-only">Load a deck</h2>
        <DeckLoader setup={setup} onError={onError} />
      </section>

      {/* Left: labelling controls above the test hand. Right: only the decklist, which fills
          the left column's height (h-0 + min-h-full) and scrolls inside it. The decklist gets
          two thirds of the width so its 10-card rows stay a readable size. */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <section className="card-panel flex min-w-0 flex-col gap-5" aria-labelledby={`${id}-label`}>
          <div>
            <SectionHeader as="h2" id={`${id}-label`} title="Label your decklist" />
            <TagControls editor={editor} />
          </div>
          <div className="flex flex-col border-t border-line pt-4">
            <SectionHeader as="h2" title="Test hand" action={
              <div className="flex flex-wrap justify-end gap-2">
                <Button variant="outlined" onClick={() => setShowingDeck(true)} disabled={!draw}>
                  Show shuffled deck
                </Button>
                <Button variant="contained" className="min-w-[130px]" onClick={drawHand} disabled={!setup.cards || drawing}>
                  {drawing ? <Spinner /> : draw ? "Draw again" : "Draw hand"}
                </Button>
              </div>
            } />
            <HandView result={draw} drawId={drawId} idByName={setup.idByName} tagged={setup.labelled} />
          </div>
        </section>

        <section className="card-panel flex min-w-0 flex-col max-lg:max-h-[560px] lg:h-0 lg:min-h-full"
                 aria-labelledby={`${id}-list`}>
          <SectionHeader as="h2" id={`${id}-list`} title="Decklist"
                         hint={setup.cards ? `· ${setup.size} cards` : undefined}
                         action={setup.cards ? (
                           <div className="flex flex-wrap items-center gap-3">
                             <SortControls deckOrder={deckOrder} />
                             <Tooltip title={!setup.side ? "This deck was saved before side decks were kept: load it again to get its side deck"
                                             : setup.side.length ? `Swap cards with the side deck (${setup.sideList.length} cards)`
                                             : "This deck has no side deck"}>
                               <span>
                                 <Button variant="outlined" size="small" onClick={openSide} disabled={!setup.side?.length}>
                                   Side deck
                                 </Button>
                               </span>
                             </Tooltip>
                           </div>
                         ) : undefined} />
          {setup.cards ? (
            <TagGrid editor={editor} idByName={setup.idByName} sided={setup.sided} order={deckOrder.order} onMove={deckOrder.move} scroll />
          ) : (
            <p className="m-0 grid flex-1 place-items-center p-6 text-center text-muted">
              Load a deck, then click its cards to label them as engine, non-engine or brick.
            </p>
          )}
        </section>
      </div>

      <Overlay open={showingDeck && draw !== null} onClose={closeDeck} label="Shuffled deck" asWindow fit>
        {draw && <ShuffledDeckView deck={draw.deck} idByName={setup.idByName} tagged={setup.labelled} onClose={closeDeck} />}
      </Overlay>

      <Overlay open={siding && setup.cards !== null} onClose={closeSide} label="Side deck" asWindow fit>
        {setup.cards && <SideDeckView key={sideOpenings} setup={setup} onClose={closeSide} />}
      </Overlay>

      <section className="card-panel stats-panel min-h-[320px]" aria-labelledby={`${id}-stats`}>
        <SectionHeader as="h2" id={`${id}-stats`} title="Probabilities"
                       action={<ExportButton disabled={!stats} onError={onError} onExport={exportAll} />} />
        <StatsView stats={stats} tagged={setup.labelled} hasHand={draw !== null} sidedCards={sidedCards}
                   sidedInHand={draw ? draw.hand.filter((card) => card.sided).length : null} />
      </section>
    </main>
  );
}
