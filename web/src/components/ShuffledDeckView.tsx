// The whole deck in the order the test hand shuffled it, 10 cards per row (5 when that makes them
// bigger): the opening five,
// then the 6th card and every draw after it. Each card shows its place in the deck; the opening
// hand and the 6th card are framed like in the test hand. The cards are sized so the whole deck
// fits the window without scrolling, except on phones: there it's always 5 per row, as wide as
// the screen, and the deck scrolls.

import Button from "@mui/material/Button";
import { useId, useLayoutEffect, useRef, useState } from "react";
import { CATEGORY_LABELS, DrawnCard } from "../api";
import { CardImage } from "./common";

const SIXTH_FRAME = "shadow-[0_0_0_2px_var(--color-sixth)]";
const HAND_FRAME = "shadow-[0_0_0_2px_var(--color-faint)]";

// Cards per row: whichever gives the bigger cards
const COLUMN_CHOICES = [10, 5];
const GAP = 8; // between cards, both ways (gap-2)
const LABEL = 20; // the name line under a card (leading-4) plus its gap (gap-1)
const CARD_RATIO = 59 / 86; // width / height, as .card-image
// Phones (below Tailwind's sm breakpoint)
const PHONE = "(max-width: 639px)";

export function ShuffledDeckView({ deck, idByName, tagged, onClose }: {
  deck: DrawnCard[]; idByName: Record<string, string>; tagged: boolean; onClose: () => void;
}) {
  const id = useId();

  // The widest card that lets every row fit both the width and the height of the space left
  const area = useRef<HTMLDivElement>(null);
  const [columns, setColumns] = useState(COLUMN_CHOICES[0]);
  const [cardWidth, setCardWidth] = useState<number | null>(null);
  useLayoutEffect(() => {
    const el = area.current;
    if (!el) return;
    const widthFor = (cols: number) => {
      const rows = Math.max(1, Math.ceil(deck.length / cols));
      const byWidth = (el.clientWidth - (cols - 1) * GAP) / cols;
      const byHeight = ((el.clientHeight - (rows - 1) * GAP) / rows - LABEL) * CARD_RATIO;
      return Math.max(0, Math.floor(Math.min(byWidth, byHeight)));
    };
    const phone = window.matchMedia(PHONE);
    const fit = () => {
      if (phone.matches) {
        setColumns(5);
        setCardWidth(Math.max(0, Math.floor((el.clientWidth - 4 * GAP) / 5)));
        return;
      }
      const best = COLUMN_CHOICES.reduce((a, b) => (widthFor(b) > widthFor(a) ? b : a));
      setColumns(best);
      setCardWidth(widthFor(best));
    };
    fit();
    const observer = new ResizeObserver(fit);
    observer.observe(el);
    phone.addEventListener("change", fit);
    return () => {
      observer.disconnect();
      phone.removeEventListener("change", fit);
    };
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
      <div ref={area} className="min-h-0 flex-1 max-sm:overflow-y-auto max-sm:overscroll-contain">
        <ol className="m-0 grid list-none justify-center gap-2 p-0"
            style={{ gridTemplateColumns: `repeat(${columns}, ${cardWidth === null ? "minmax(0, 1fr)" : `${cardWidth}px`})` }}>
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
