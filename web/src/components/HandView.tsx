// The drawn hand in a 3×2 grid: five cards plus the 6th card, dealt face down and flipped over.
// The 6th card is marked with a sky-blue frame and a "6th card" label (colour-blind safe: it is told
// apart by the label and frame, and the blue is distinct from the red/yellow/green tags).

import { motion } from "framer-motion";
import { memo } from "react";
import { CATEGORY_LABELS, DrawnCard, DrawResult } from "../api";
import { CardBack } from "./CardBack";
import { CardImage } from "./common";

// Cards scale with the panel, up to about 115px wide
const GRID = "mx-auto grid w-full max-w-[380px] grid-cols-3 gap-x-3 gap-y-4 pt-2.5 perspective-[1200px]";
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

function HandCard({ card, id, index, showCategory }: {
  card: DrawnCard; id?: string; index: number; showCategory: boolean;
}) {
  const sixth = index === 5;
  return (
    <motion.div className="relative flex min-w-0 flex-col gap-1.5"
                initial={{ opacity: 0, y: -40, rotate: -6 }}
                animate={{ opacity: 1, y: 0, rotate: 0 }}
                transition={{
                  default: { delay: index * 0.07, type: "spring", stiffness: 260, damping: 24 },
                  // A slower, even fade (a spring would make it near-instant)
                  opacity: { delay: index * 0.07, duration: 0.7, ease: "easeOut" },
                }}>
      <motion.div className={`relative aspect-[59/86] rounded-lg transform-3d ${sixth ? SIXTH_FRAME : ""}`}
                  initial={{ rotateY: 180 }} animate={{ rotateY: 0 }}
                  transition={{ delay: 0.25 + index * 0.07, duration: 0.55, ease: [0.2, 0.7, 0.2, 1] }}>
        <div className={FACE}>
          <CardImage id={id} name={card.name} size="full" className="h-full" />
          {showCategory && card.category && (
            <span className={`card-badge hand-badge tone-${card.category}`}>{CATEGORY_LABELS[card.category]}</span>
          )}
        </div>
        <div className={`${FACE} rotate-y-180`}><CardBack /></div>
      </motion.div>
      {/* Outside the flip, so it never shows mirrored */}
      {sixth && <SixthLabel />}
      <span className="truncate text-center text-[11px] text-muted" title={card.name}>{card.name}</span>
    </motion.div>
  );
}

export const HandView = memo(function HandView({ result, drawId, idByName, tagged }: {
  result: DrawResult | null; drawId: number; idByName: Record<string, string>; tagged: boolean;
}) {
  if (!result) {
    return (
      <div className={GRID}>
        {Array.from({ length: 6 }, (_, i) => (
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
        <HandCard key={i} card={card} id={idByName[card.name]} index={i} showCategory={tagged} />
      ))}
      {result.sixth && (
        <HandCard card={result.sixth} id={idByName[result.sixth.name]} index={5} showCategory={tagged} />
      )}
    </div>
  );
});
