// The whole deck in the order the test hand shuffled it, 10 cards per row: the opening five,
// then the 6th card and every draw after it. Each card shows its place in the deck; the opening
// hand and the 6th card are framed like in the test hand.

import Button from "@mui/material/Button";
import { useId } from "react";
import { CATEGORY_LABELS, DrawnCard } from "../api";
import { CardImage } from "./common";

const SIXTH_FRAME = "shadow-[0_0_0_2px_var(--color-sixth)]";
const HAND_FRAME = "shadow-[0_0_0_2px_var(--color-faint)]";

export function ShuffledDeckView({ deck, idByName, tagged, onClose }: {
  deck: DrawnCard[]; idByName: Record<string, string>; tagged: boolean; onClose: () => void;
}) {
  const id = useId();
  return (
    <div className="flex flex-col gap-3.5">
      <div className="overlay-header pinned">
        <div>
          <h2 id={`${id}-title`}>Shuffled deck</h2>
          <p className="m-0 text-muted">
            Top to bottom, as drawn: cards 1–5 are the opening hand, card 6 is the draw going second.
          </p>
        </div>
        <Button color="inherit" onClick={onClose}>Close</Button>
      </div>
      <ol className="m-0 grid list-none grid-cols-5 gap-2 p-0 sm:grid-cols-10">
        {deck.map((card, i) => (
          <li key={i} className="flex min-w-0 flex-col gap-1">
            <div className={`relative rounded-[7px] ${i === 5 ? SIXTH_FRAME : i < 5 ? HAND_FRAME : ""}`}>
              <CardImage id={idByName[card.name]} name={card.name} />
              {tagged && card.category && (
                <span className={`card-badge tile-badge tone-${card.category}`}>{CATEGORY_LABELS[card.category]}</span>
              )}
            </div>
            <span className="truncate text-center text-[11px] text-muted" title={card.name}>
              <b className={i === 5 ? "text-sixth" : "text-text"}>{i + 1}.</b> {card.name}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}
