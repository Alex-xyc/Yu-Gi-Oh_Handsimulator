// Siding: the main deck above the side deck, 10 cards per row (5 when that makes them bigger, on a phone). Click main deck cards to side them
// out and side deck cards to side them in; Swap trades them once as many go in as come out, so the
// main deck keeps its size. The cards are sized so both decks always fit the window, without
// scrolling (as the shuffled deck).

import Button from "@mui/material/Button";
import { useId, useLayoutEffect, useMemo, useRef, useState } from "react";
import { type Category, CATEGORY_LABELS } from "../api";
import { type DeckSetup, MAX_COPIES } from "../useDeckSetup";
import { CardImage, SideIcon } from "./common";

// Cards per row: whichever gives the bigger cards
const COLUMN_CHOICES = [10, 5];
const GAP = 8; // between cards, both ways (gap-2)
const HEADING = 28; // a deck's title line (h-7)
const SECTION_GAP = 14; // between the two decks (gap-3.5)
const OUTLINE = 6; // a picked card's outline, so the top and bottom rows' isn't cut off
const CARD_RATIO = 59 / 86; // width / height, as .card-image

type Pick = "out" | "in";

const toggled = (set: Set<number>, index: number) => {
  const next = new Set(set);
  if (!next.delete(index)) next.add(index);
  return next;
};

function DeckGrid({ title, list, tags, moved, movedLabel, picked, pick, idByName, columns, cardWidth, onToggle }: {
  title: string;
  list: string[];
  /** Each copy's label, shown on it */
  tags: Category[];
  /** Per copy: whether it's out of the deck it started in (marked with a dot) */
  moved: boolean[];
  /** What a dot means here, e.g. "sided in" */
  movedLabel: string;
  picked: Set<number>;
  pick: Pick;
  idByName: Record<string, string>;
  columns: number;
  cardWidth: number | null;
  onToggle: (index: number) => void;
}) {
  const verb = pick === "out" ? "side out" : "side in";
  return (
    <section className="flex min-h-0 flex-col" aria-label={title}>
      <h3 className="m-0 flex h-7 items-center gap-2">
        {title} <span className="font-normal text-muted">· {list.length} cards</span>
        {picked.size > 0 && <span className={`side-count ${pick}`}>{picked.size} {pick}</span>}
      </h3>
      <ul className="m-0 grid list-none justify-center gap-2" style={{ padding: `${OUTLINE}px 0`,
          gridTemplateColumns: `repeat(${columns}, ${cardWidth === null ? "minmax(0, 1fr)" : `${cardWidth}px`})` }}>
        {list.map((name, i) => {
          const isPicked = picked.has(i);
          const tag = tags[i];
          const isMoved = moved[i] ?? false;
          return (
            <li key={i} className="min-w-0">
              <button type="button" className={`side-tile ${isPicked ? pick : ""}`}
                      title={isMoved ? `${name} (${movedLabel})` : name} aria-pressed={isPicked}
                      aria-label={`${name}${tag ? `, ${CATEGORY_LABELS[tag]}` : ""}${isMoved ? `, ${movedLabel}` : ""}: ${verb}`}
                      onClick={() => onToggle(i)}>
                <CardImage id={idByName[name]} name={name} />
                {tag && <span className={`card-badge tile-badge tone-${tag}`}>{CATEGORY_LABELS[tag]}</span>}
                {isMoved && <SideIcon />}
                {isPicked && <span className="side-mark" aria-hidden="true">{pick === "out" ? "OUT" : "IN"}</span>}
              </button>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function SideDeckView({ setup, onClose }: { setup: DeckSetup; onClose: () => void }) {
  const id = useId();
  const { deckList, sideList, tags, idByName } = setup;
  const [out, setOut] = useState<Set<number>>(new Set());
  const [into, setInto] = useState<Set<number>>(new Set());
  const [swapped, setSwapped] = useState(0);

  // A card would have too many copies in the main deck after the swap
  const overLimit = useMemo(() => {
    const counts = new Map<string, number>();
    deckList.forEach((name, i) => { if (!out.has(i)) counts.set(name, (counts.get(name) ?? 0) + 1); });
    for (const i of into) counts.set(sideList[i], (counts.get(sideList[i]) ?? 0) + 1);
    return [...counts].find(([, copies]) => copies > MAX_COPIES)?.[0] ?? null;
  }, [deckList, sideList, out, into]);

  const canSwap = out.size > 0 && out.size === into.size && !overLimit;
  const status = overLimit ? `Too many copies of ${overLimit} (at most ${MAX_COPIES}).`
    : out.size > into.size ? `Pick ${out.size - into.size} more from the side deck to swap.`
    : into.size > out.size ? `Pick ${into.size - out.size} more from the main deck to swap.`
    : out.size ? `Ready to swap ${out.size} card${out.size > 1 ? "s" : ""}.`
    : swapped ? `Swapped ${swapped} card${swapped > 1 ? "s" : ""}.`
    : "Pick cards to side out of the main deck and as many to side in.";

  const swap = () => {
    if (!canSwap) return;
    setup.swapSide([...out], [...into]);
    setSwapped(out.size);
    setOut(new Set());
    setInto(new Set());
  };
  const clear = () => { setOut(new Set()); setInto(new Set()); };

  // The widest card that lets both decks' rows fit the width and the height of the space left
  const area = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(COLUMN_CHOICES[0]);
  const [cardWidth, setCardWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    const widthFor = (cols: number) => {
      const mainRows = Math.max(1, Math.ceil(deckList.length / cols));
      const sideRows = Math.max(1, Math.ceil(sideList.length / cols));
      const rows = mainRows + sideRows;
      const byWidth = (el.clientWidth - (cols - 1) * GAP) / cols;
      const height = el.clientHeight - 2 * HEADING - SECTION_GAP - 4 * OUTLINE - (rows - 2) * GAP;
      const byHeight = (height / rows) * CARD_RATIO;
      return Math.max(0, Math.floor(Math.min(byWidth, byHeight)));
    };
    const fitCards = () => {
      const best = COLUMN_CHOICES.reduce((a, b) => (widthFor(b) > widthFor(a) ? b : a));
      setColumns(best);
      setCardWidth(widthFor(best));
    };
    fitCards();
    const observer = new ResizeObserver(fitCards);
    observer.observe(el);
    return () => observer.disconnect();
  }, [deckList.length, sideList.length]);

  return (
    <div className="flex h-full flex-col gap-3.5">
      <div className="overlay-header pinned flex-wrap">
        <div className="min-w-0">
          <h2 id={`${id}-title`}>Side deck</h2>
          <p className="m-0 text-muted" aria-live="polite">
            <span className={overLimit ? "error" : canSwap ? "ok" : ""}>{status}</span>
            {(setup.sidedIn > 0 || setup.sideFromMain.some(Boolean)) && (
              <span className="ml-3 inline-flex items-center gap-1.5 text-xs">
                <SideIcon inline />Swapped from the other deck
              </span>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button color="inherit" onClick={clear} disabled={!out.size && !into.size}>Clear</Button>
          <Button variant="contained" onClick={swap} disabled={!canSwap} className="min-w-[120px]">
            Swap {out.size} ⇄ {into.size}
          </Button>
          <Button color="inherit" onClick={onClose}>Close</Button>
        </div>
      </div>
      <div ref={area} className="flex min-h-0 flex-1 flex-col gap-3.5 overflow-hidden">
        <DeckGrid title="Main deck" list={deckList} tags={tags} moved={setup.sided} movedLabel="sided in" picked={out} pick="out" idByName={idByName}
                  columns={columns} cardWidth={cardWidth} onToggle={(i) => setOut(toggled(out, i))} />
        <DeckGrid title="Side deck" list={sideList} tags={setup.sideTags} moved={setup.sideFromMain} movedLabel="sided out"
                  picked={into} pick="in" idByName={idByName}
                  columns={columns} cardWidth={cardWidth} onToggle={(i) => setInto(toggled(into, i))} />
      </div>
    </div>
  );
}
