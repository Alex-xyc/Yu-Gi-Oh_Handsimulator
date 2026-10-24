// One deck tab: loading, labelling, a test hand and the probabilities. Every open tab stays
// mounted (hidden when not selected), so switching tabs keeps its hand, undo history and input.

import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import { useCallback, useEffect, useId, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { api, type DrawResult, prefetchCardImages, type Stats } from "../api";
import { countLabels, type CustomLabelCount, type CustomLabelOf, useLabelSettings } from "../customLabels";
import { exportStats } from "../export";
import type { DeckSetup } from "../useDeckSetup";
import { Overlay, SectionHeader, Spinner } from "./common";
import { DeckLoader } from "./DeckPanel";
import { ExportButton } from "./ExportButton";
import { SortControls, TagControls, TagGrid, TagHistoryButtons, useDeckOrder, useTagEditor } from "./DecklistView";
import { HandView } from "./HandView";
import { ShuffledDeckView } from "./ShuffledDeckView";
import { SideDeckView } from "./SideDeckView";
import { type SidedCard, StatsView } from "./StatsView";

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
  const { t } = useTranslation();
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
  // biome-ignore lint/correctness/useExhaustiveDependencies: cleared when another deck is loaded
  useEffect(() => { setDraw(null); }, [setup.cards]);

  // The test hand shows full-size images and the decklist small ones: once the decklist's have had
  // a head start, load the main deck's full-size images in the background, so a drawn hand shows at once
  useEffect(() => {
    if (!active || !setup.cards) return;
    const ids = setup.cards.map((card) => card.id);
    const timer = setTimeout(() => prefetchCardImages(ids, "full"), 1500);
    return () => clearTimeout(timer);
  }, [active, setup.cards]);

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
    if (!body) return onError(t("workspace.loadFirst"));
    setDrawing(true);
    try {
      const result = await api.draw(body);
      setDraw(result);
      setStats(result.stats);
      setDrawId((n) => n + 1);
    } catch (e) {
      onError(e instanceof Error ? e.message : t("workspace.drawFailed"));
    } finally {
      setDrawing(false);
    }
  };


  // Labelling on the page: the controls and the cards are in different panels
  const { labels, advanced } = useLabelSettings();
  const editor = useTagEditor({
    deckList: setup.deckList, tags: setup.tags, custom: setup.custom, labels, advanced, onChange: setup.applyTags,
    shortcuts: active && shortcuts && !showingDeck && !siding,
  });
  // Each custom label's copies in the deck, for its odds (advanced mode only)
  const customCounts = useMemo((): CustomLabelCount[] => countLabels(advanced ? labels : [], setup.deckList, editor.custom),
    [advanced, labels, setup.deckList, editor.custom]);
  // A drawn card's custom label: the one its copy has now (advanced mode only)
  const customOf = useMemo((): CustomLabelOf | undefined => {
    if (!advanced) return undefined;
    const byId = new Map(labels.map((label) => [label.id, label]));
    return (card) => (card.copy === undefined ? undefined : byId.get(editor.custom[card.copy]));
  }, [advanced, labels, editor.custom]);
  const customInHand = useMemo(() => {
    if (!draw || !customOf) return null;
    const counts: Record<string, number> = {};
    for (const card of draw.hand) {
      const label = customOf(card);
      if (label) counts[label.id] = (counts[label.id] ?? 0) + 1;
    }
    return counts;
  }, [draw, customOf]);

  /** Everything the panel shows, going first and going second, plus the test hand */
  const exportAll = async () => {
    if (!stats || !body) return;
    const second = await api.stats(body, undefined, 6);
    await exportStats({
      name, first: stats, second, draw, labelled: setup.labelled, sidedCards,
      customLabels: customCounts, customOf, customInHand,
    });
  };

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
        <h2 id={`${id}-load`} className="sr-only">{t("workspace.loadDeck")}</h2>
        <DeckLoader setup={setup} onError={onError} />
      </section>

      {/* Left: labelling controls above the test hand. Right: only the decklist, which fills
          the left column's height (h-0 + min-h-full) and scrolls inside it. The decklist gets
          two thirds of the width so its 10-card rows stay a readable size.
          Narrower, it's one column: the left panel splits into two panels (max-lg:contents),
          the test hand first, then the labelling, then the decklist. */}
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
        <section className="card-panel flex min-w-0 flex-col gap-5 max-lg:contents" aria-labelledby={`${id}-label`}>
          <div className="workspace-part min-w-0">
            <SectionHeader as="h2" id={`${id}-label`} title={t("workspace.labelDecklist")} action={<TagHistoryButtons editor={editor} />} />
            <TagControls editor={editor} />
          </div>
          <div className="workspace-part flex min-w-0 flex-col max-lg:-order-1 lg:border-t lg:border-line lg:pt-4">
            <SectionHeader as="h2" title={t("workspace.testHand")} action={
              <div className="flex flex-wrap justify-end gap-2 max-sm:grid max-sm:w-full max-sm:grid-cols-2">
                <Button variant="outlined" onClick={() => setShowingDeck(true)} disabled={!draw}>
                  <span className="max-sm:hidden">{t("workspace.showShuffledDeck")}</span><span className="sm:hidden">{t("workspace.shuffledDeck")}</span>
                </Button>
                <Button variant="contained" className="min-w-[130px]" onClick={drawHand} disabled={!setup.cards || drawing}>
                  {drawing ? <Spinner /> : draw ? t("workspace.drawAgain") : t("workspace.drawHand")}
                </Button>
              </div>
            } />
            <HandView result={draw} drawId={drawId} idByName={setup.idByName} tagged={setup.labelled} customOf={customOf} />
          </div>
        </section>

        <section className="card-panel flex min-w-0 flex-col max-lg:max-h-[560px] lg:h-0 lg:min-h-full"
                 aria-labelledby={`${id}-list`}>
          <SectionHeader as="h2" id={`${id}-list`} title={t("workspace.decklist")}
                         hint={setup.cards ? t("common.deckSize", { count: setup.size }) : undefined}
                         action={setup.cards ? (
                           <div className="flex flex-wrap items-center gap-3">
                             <SortControls deckOrder={deckOrder} />
                             <Tooltip title={!setup.side ? t("workspace.sideDeckUnknown")
                                             : setup.side.length ? t("workspace.sideDeckSwap", { count: setup.sideList.length })
                                             : t("workspace.sideDeckNone")}>
                               <span>
                                 <Button variant="outlined" size="small" onClick={openSide} disabled={!setup.side?.length}>
                                   {t("workspace.sideDeck")}
                                 </Button>
                               </span>
                             </Tooltip>
                           </div>
                         ) : undefined} />
          {setup.cards ? (
            <TagGrid editor={editor} idByName={setup.idByName} sided={setup.sided} order={deckOrder.order} onMove={deckOrder.move} scroll />
          ) : (
            <p className="m-0 grid flex-1 place-items-center p-6 text-center text-muted">
              {t("workspace.emptyDecklist")}
            </p>
          )}
        </section>
      </div>

      <Overlay open={showingDeck && draw !== null} onClose={closeDeck} label={t("shuffled.title")} asWindow fit>
        {draw && <ShuffledDeckView deck={draw.deck} idByName={setup.idByName} tagged={setup.labelled} customOf={customOf} onClose={closeDeck} />}
      </Overlay>

      <Overlay open={siding && setup.cards !== null} onClose={closeSide} label={t("side.title")} asWindow fit>
        {setup.cards && <SideDeckView key={sideOpenings} setup={setup} onClose={closeSide} />}
      </Overlay>

      <section className="card-panel stats-panel min-h-[320px]" aria-labelledby={`${id}-stats`}>
        <SectionHeader as="h2" id={`${id}-stats`} title={t("workspace.probabilities")}
                       action={<ExportButton disabled={!stats} onError={onError} onExport={exportAll} />} />
        <StatsView stats={stats} tagged={setup.labelled} hasHand={draw !== null} sidedCards={sidedCards}
                   customLabels={customCounts} customInHand={customInHand}
                   sidedInHand={draw ? draw.hand.filter((card) => card.sided).length : null} />
      </section>
    </main>
  );
}
