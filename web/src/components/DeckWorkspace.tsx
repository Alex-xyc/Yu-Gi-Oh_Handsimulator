// One deck tab: loading, labelling, a test hand and the probabilities. Every open tab stays
// mounted (hidden when not selected), so switching tabs keeps its hand, undo history and input.

import Button from "@mui/material/Button";
import { useEffect, useId, useState } from "react";
import { api, DrawResult, Stats } from "../api";
import { exportStats } from "../export";
import { DeckSetup } from "../useDeckSetup";
import { SectionHeader, Spinner } from "./common";
import { DeckLoader } from "./DeckPanel";
import { ExportButton } from "./ExportButton";
import { TagControls, TagGrid, useTagEditor } from "./DecklistView";
import { HandView } from "./HandView";
import { StatsView } from "./StatsView";

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
    shortcuts: active && shortcuts,
  });

  return (
    <main className="layout" hidden={!active} aria-label={name}>
      <section className="card-panel" aria-labelledby={`${id}-load`}>
        <h2 id={`${id}-load`} className="sr-only">Load a deck</h2>
        <DeckLoader setup={setup} onError={onError} />
      </section>

      {/* Left: labelling controls above the test hand. Right: only the decklist, which fills
          the left column's height (h-0 + min-h-full) and scrolls inside it. */}
      <div className="grid gap-4 lg:grid-cols-2">
        <section className="card-panel flex min-w-0 flex-col gap-5" aria-labelledby={`${id}-label`}>
          <div>
            <SectionHeader as="h2" id={`${id}-label`} title="Label your decklist" />
            <TagControls editor={editor} />
          </div>
          <div className="flex flex-col border-t border-line pt-4">
            <SectionHeader as="h2" title="Test hand" action={
              <Button variant="contained" className="min-w-[130px]" onClick={drawHand} disabled={!setup.cards || drawing}>
                {drawing ? <Spinner /> : draw ? "Draw again" : "Draw hand"}
              </Button>
            } />
            <HandView result={draw} drawId={drawId} idByName={setup.idByName} tagged={setup.labelled} />
          </div>
        </section>

        <section className="card-panel flex min-w-0 flex-col max-lg:max-h-[560px] lg:h-0 lg:min-h-full"
                 aria-labelledby={`${id}-list`}>
          <SectionHeader as="h2" id={`${id}-list`} title="Decklist"
                         hint={setup.cards ? `· ${setup.size} cards` : undefined} />
          {setup.cards ? (
            <TagGrid editor={editor} idByName={setup.idByName} scroll />
          ) : (
            <p className="m-0 grid flex-1 place-items-center p-6 text-center text-muted">
              Load a deck, then click its cards to label them as engine, non-engine or brick.
            </p>
          )}
        </section>
      </div>

      <section className="card-panel stats-panel min-h-[320px]" aria-labelledby={`${id}-stats`}>
        <SectionHeader as="h2" id={`${id}-stats`} title="Probabilities"
                       action={<ExportButton disabled={!stats} onError={onError} onExport={exportAll} />} />
        <StatsView stats={stats} tagged={setup.labelled} hasHand={draw !== null} />
      </section>
    </main>
  );
}
