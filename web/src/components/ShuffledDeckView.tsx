// The whole deck in the order the test hand shuffled it, 10 cards per row: the opening five,
// then the 6th card and every draw after it. Each card shows its place in the deck; the opening
// hand and the 6th card are framed like in the test hand. The cards are sized so the whole deck
// always fits the window, without scrolling.

import Button from "@mui/material/Button";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { CATEGORY_LABELS, DrawnCard } from "../api";
import { CardImage } from "./common";

const SIXTH_FRAME = "shadow-[0_0_0_2px_var(--color-sixth)]";
const HAND_FRAME = "shadow-[0_0_0_2px_var(--color-faint)]";

const COLUMNS = 10;
const GAP = 8; // between cards, both ways (gap-2)
const LABEL = 20; // the name line under a card (leading-4) plus its gap (gap-1)
const CARD_RATIO = 59 / 86; // width / height, as .card-image

export function ShuffledDeckView({ deck, idByName, tagged, onClose }: {
  deck: DrawnCard[]; idByName: Record<string, string>; tagged: boolean; onClose: () => void;
}) {
  const id = useId();

  // The widest card that lets every row fit both the width and the height of the space left
  const area = useRef<HTMLDivElement>(null);
  const [cardWidth, setCardWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    const rows = Math.max(1, Math.ceil(deck.length / COLUMNS));
    const fit = () => {
      const byWidth = (el.clientWidth - (COLUMNS - 1) * GAP) / COLUMNS;
      const byHeight = ((el.clientHeight - (rows - 1) * GAP) / rows - LABEL) * CARD_RATIO;
      setCardWidth(Math.max(0, Math.floor(Math.min(byWidth, byHeight))));
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    return () => observer.disconnect();
  }, [deck.length]);

  return (
    <div className="flex h-full flex-col gap-3.5">
      <div className="overlay-header pinned">
        <div>
          <h2 id={`${id}-title`}>Shuffled deck</h2>
          <p className="m-0 text-muted">
            Top to bottom, as drawn: cards 1–5 are the opening hand, card 6 is the draw going second.
          </p>
        </div>
        <Button color="inherit" onClick={onClose}>Close</Button>
      </div>
      <div ref={area} className="min-h-0 flex-1">
        <ol className="m-0 grid list-none justify-center gap-2 p-0"
            style={{ gridTemplateColumns: `repeat(${COLUMNS}, ${cardWidth === null ? "minmax(0, 1fr)" : `${cardWidth}px`})` }}>
          {deck.map((card, i) => (
            <li key={i} className="flex min-w-0 flex-col gap-1">
              <div className={`relative rounded-[7px] ${i === 5 ? SIXTH_FRAME : i < 5 ? HAND_FRAME : ""}`}>
                <CardImage id={idByName[card.name]} name={card.name} />
                {tagged && card.category && (
                  <span className={`card-badge tile-badge tone-${card.category}`}>{CATEGORY_LABELS[card.category]}</span>
                )}
              </div>
              <span className="truncate text-center text-[11px] leading-4 text-muted" title={card.name}>
                <b className={i === 5 ? "text-sixth" : "text-text"}>{i + 1}.</b> {card.name}
              </span>
            </li>
          ))}
        </ol>
      </div>
    </div>
  );
}
