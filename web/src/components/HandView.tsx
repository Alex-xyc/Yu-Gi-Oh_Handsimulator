// The drawn hand in a 5×2 grid, dealt face down and flipped over: the opening five on top, then the
// 6th card (going second) and the next four (extra draws). The 6th card is marked with a sky-blue
// frame and a "6th card" label (colour-blind safe: it is told apart by the label and frame, and the
// blue is distinct from the red/yellow/green tags); the extra draws are dimmed, numbered and stay
// face down until clicked (clicking again turns them back over).

import { motion } from "framer-motion";
import { memo, useState } from "react";
import { CATEGORY_LABELS, type DrawnCard, type DrawResult } from "../api";
import type { CustomLabel, CustomLabelOf } from "../customLabels";
import { CardBack } from "./CardBack";
import { CardImage, toneColor } from "./common";

// Cards scale with the panel, up to about 105px wide
const GRID = "mx-auto grid w-full max-w-[560px] grid-cols-5 gap-x-2 gap-y-4 pt-2.5 perspective-[1200px]";
/** The opening hand plus the 6th card and four extra draws */
const SLOTS = 10;
const FACE = "absolute inset-0 overflow-hidden rounded-lg backface-hidden shadow-[0_10px_26px_rgba(0,0,0,0.5)]";
const SIXTH_FRAME = "shadow-[0_0_0_3px_var(--color-sixth),0_0_20px_color-mix(in_srgb,var(--color-sixth)_45%,transparent)]";

function SixthLabel() {
  return (
    <span className="absolute -top-2.5 left-1/2 z-[2] -translate-x-1/2 whitespace-nowrap rounded-full bg-sixth px-2
                     py-px text-[10px] font-extrabold tracking-wider text-ink uppercase shadow-md">
      6th card
    </span>
  );
}

/** "7th", "8th", … on an extra draw */
function DrawLabel({ index }: { index: number }) {
  return (
    <span className="absolute -top-2.5 left-1/2 z-[2] -translate-x-1/2 whitespace-nowrap rounded-full border border-line
                     bg-surface-2 px-2 py-px text-[10px] font-bold tracking-wider text-muted uppercase shadow-md">
      {index + 1}th
    </span>
  );
}

function HandCard({ card, id, index, showCategory, custom }: {
  card: DrawnCard; id?: string; index: number; showCategory: boolean;
  /** Its custom label (advanced mode) */
  custom?: CustomLabel;
}) {
  const category = showCategory && card.category;
  const sixth = index === 5;
  const extra = index > 5;
  // The extra draws stay face down until clicked, and a second click hides them again (a new draw
  // remounts the grid, hiding them all)
  const [revealed, setRevealed] = useState(!extra);
  const [hovered, setHovered] = useState(false);
  return (
    <motion.div className="relative flex min-w-0 flex-col gap-1.5"
                initial={{ opacity: 0, y: -40, rotate: -6 }}
                animate={{ opacity: 1, y: 0, rotate: 0 }}
                transition={{
                  default: { delay: index * 0.07, type: "spring", stiffness: 260, damping: 24 },
                  // A slower, even fade (a spring would make it near-instant)
                  opacity: { delay: index * 0.07, duration: 0.7, ease: "easeOut" },
                }}>
      <div className="relative">
        <motion.div className={`relative aspect-[59/86] rounded-lg transform-3d ${sixth ? SIXTH_FRAME : ""}`}
                    initial={{ rotateY: 180 }} animate={{ rotateY: revealed ? 0 : 180, y: hovered ? -4 : 0 }}
                    transition={{ delay: extra ? 0 : 0.25 + index * 0.07, duration: 0.55, ease: [0.2, 0.7, 0.2, 1] }}>
          <div className={`${FACE} ${extra ? "opacity-75" : ""}`}>
            <CardImage id={id} name={card.name} size="full" className="h-full" />
            {category && (
              <span className={`card-badge hand-badge tone-${category}`}>{CATEGORY_LABELS[category]}</span>
            )}
            {custom && (
              <span className={`card-badge hand-badge custom-badge ${category ? "stacked" : ""}`} style={toneColor(custom.color)}>
                {custom.name}
              </span>
            )}
          </div>
          <div className={`${FACE} rotate-y-180`}><CardBack /></div>
        </motion.div>
        {/* Over the card but outside its 3D flip: inside it, the turned-over face could take the
            click instead, so a revealed card couldn't be hidden again */}
        {extra && (
          <button type="button" className="reveal-card absolute inset-0 z-[1] cursor-pointer rounded-lg"
                  aria-label={`${revealed ? "Hide" : "Reveal"} the ${index + 1}th card`} aria-pressed={revealed}
                  title={revealed ? `${card.name} (click to hide)` : undefined}
                  onMouseEnter={() => setHovered(true)} onMouseLeave={() => setHovered(false)}
                  onClick={() => setRevealed((r) => !r)} />
        )}
      </div>
      {/* Outside the flip, so it never shows mirrored */}
      {sixth && <SixthLabel />}
      {extra && <DrawLabel index={index} />}
      {revealed ? (
        <span className="truncate text-center text-[11px] text-muted" title={card.name}>{card.name}</span>
      ) : (
        <span className="truncate text-center text-[11px] text-faint">Click to reveal</span>
      )}
    </motion.div>
  );
}

export const HandView = memo(function HandView({ result, drawId, idByName, tagged, customOf }: {
  result: DrawResult | null; drawId: number; idByName: Record<string, string>; tagged: boolean;
  /** A card's custom label (advanced mode only) */
  customOf?: CustomLabelOf;
}) {
  if (!result) {
    return (
      <div className={GRID}>
        {Array.from({ length: SLOTS }, (_, i) => (
          // Fade in one after another, then float gently
          <motion.div key={i} className="relative flex min-w-0 flex-col gap-1.5"
                      initial={{ opacity: 0, y: 14, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      transition={{
                        default: { delay: 0.1 + i * 0.12, duration: 0.6, ease: [0.2, 0.7, 0.2, 1] },
                        opacity: { delay: 0.1 + i * 0.12, duration: 1.1, ease: "easeInOut" },
                      }}>
            {/* No 6th-card marker until a hand is drawn */}
            <motion.div className="relative aspect-[59/86] rounded-lg"
                        animate={{ y: [0, -4, 0] }}
                        transition={{ duration: 2.4, repeat: Infinity, delay: 0.7 + i * 0.15, ease: "easeInOut" }}>
              <div className={`${FACE} opacity-55`}><CardBack /></div>
            </motion.div>
            <span className="text-[11px]">&nbsp;</span>
          </motion.div>
        ))}
      </div>
    );
  }

  return (
    <div className={GRID} key={drawId}>
      {result.hand.map((card, i) => (
        <HandCard key={i} card={card} id={idByName[card.name]} index={i} showCategory={tagged} custom={customOf?.(card)} />
      ))}
      {result.sixth && (
        <HandCard card={result.sixth} id={idByName[result.sixth.name]} index={5} showCategory={tagged} custom={customOf?.(result.sixth)} />
      )}
      {result.draws.map((card, i) => (
        <HandCard key={6 + i} card={card} id={idByName[card.name]} index={6 + i} showCategory={tagged} custom={customOf?.(card)} />
      ))}
    </div>
  );
});
