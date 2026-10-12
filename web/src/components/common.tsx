// Small building blocks shared across the app

import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import { AnimatePresence, motion, Variants } from "framer-motion";
import { ReactNode, useEffect, useLayoutEffect, useRef, useState } from "react";
import { cardImageUrl } from "../api";

/** A card picture, or its name on a plain tile when there's no image. */
export function CardImage({ id, name, size = "small", className = "" }: {
  id?: string; name: string; size?: "small" | "full"; className?: string;
}) {
  const url = cardImageUrl(id, size);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => { setFailed(false); setLoaded(false); }, [url]);

  return (
    <div className={`card-image ${className}`}>
      {url && !failed ? (
        <img src={url} alt={name} draggable={false} loading="lazy"
             className={loaded ? "loaded" : ""}
             onLoad={() => setLoaded(true)} onError={() => setFailed(true)} />
      ) : null}
      {(!url || failed || !loaded) && <span className="card-image-name">{name}</span>}
    </div>
  );
}

// The overlay opens in steps, so the two screens are never seen on top of each other. Opening:
// the backdrop dims the page, the panel's empty box fades in over it, then its contents. Closing:
// the reverse. (The panel and contents follow the backdrop's "open" / "closed" state.)
const BACKDROP: Variants = {
  open: { opacity: 1, transition: { duration: 0.16, ease: "easeOut" } },
  closed: { opacity: 0, transition: { delay: 0.2, duration: 0.16, ease: "easeIn" } },
};
const PANEL: Variants = {
  open: { opacity: 1, y: 0, scale: 1, transition: { delay: 0.1, duration: 0.18, ease: [0.2, 0.7, 0.2, 1] } },
  closed: { opacity: 0, y: 8, scale: 0.99, transition: { delay: 0.08, duration: 0.14, ease: "easeIn" } },
};
const CONTENT: Variants = {
  open: { opacity: 1, transition: { delay: 0.24, duration: 0.18, ease: "easeOut" } },
  closed: { opacity: 0, transition: { duration: 0.1, ease: "easeIn" } },
};

/** Full-window overlay panel that fades and slides in, like the desktop app's overlays.
 *  With `keepMounted` its contents are built once and kept (hidden) while closed, so opening and
 *  closing only run the animation; building a large view at that moment stalls the fade.
 *  With `asWindow` it's a smaller centred window over the dimmed page instead, closed by clicking
 *  outside it. Focus moves into it while open; the page behind should be made inert meanwhile. */
export function Overlay({ open, onClose, children, label, keepMounted = false, asWindow = false }: {
  open: boolean; onClose: () => void; children: ReactNode; label: string; keepMounted?: boolean; asWindow?: boolean;
}) {
  // Rendered from the first open (or from the start with keepMounted) and then kept
  const [mounted, setMounted] = useState(open || keepMounted);
  // Hidden (not just transparent) once the closing animation has finished
  const [hidden, setHidden] = useState(!open);
  useLayoutEffect(() => {
    if (open) { setMounted(true); setHidden(false); }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Keyboard focus moves into the panel on opening, and back to where it was on closing (only
  // on closing, so an effect that runs twice, as in React's development mode, doesn't undo it)
  const panel = useRef<HTMLDivElement>(null);
  const restoreTo = useRef<HTMLElement | null>(null);
  const opened = open && !hidden;
  useEffect(() => {
    if (opened) {
      const focused = document.activeElement as HTMLElement | null;
      if (!restoreTo.current && focused !== document.body && !panel.current?.contains(focused)) restoreTo.current = focused;
      // A frame later: until the browser has restyled it, the panel still counts as hidden
      const frame = requestAnimationFrame(() => panel.current?.focus({ preventScroll: true }));
      return () => cancelAnimationFrame(frame);
    } else if (restoreTo.current) {
      const target = restoreTo.current;
      restoreTo.current = null;
      // A frame later, once the page behind is no longer inert
      requestAnimationFrame(() => target.focus({ preventScroll: true }));
    }
  }, [opened]);

  if (!mounted) return null;
  return (
    // Hidden with a class, not motion's style: motion applies style a frame later, and the panel
    // must be visible at once to take focus
    <motion.div className={`overlay-backdrop ${asWindow ? "window" : ""} ${hidden ? "invisible" : ""}`}
                role="dialog" aria-modal="true" aria-label={label}
                onMouseDown={asWindow ? (e) => { if (e.target === e.currentTarget) onClose(); } : undefined}
                variants={BACKDROP} initial="closed" animate={open ? "open" : "closed"}
                onAnimationComplete={(state) => { if (state === "closed") setHidden(true); }}>
      <motion.div className="overlay-panel" variants={PANEL} ref={panel} tabIndex={-1}>
        <motion.div variants={CONTENT}>{children}</motion.div>
      </motion.div>
    </motion.div>
  );
}

export interface Toast {
  id: number;
  message: string;
}

export function Toasts({ toasts, onDismiss }: { toasts: Toast[]; onDismiss: (id: number) => void }) {
  return (
    <div className="toasts" aria-live="polite">
      <AnimatePresence>
        {toasts.map((toast) => (
          <motion.div key={toast.id} layout
                      initial={{ opacity: 0, y: 16, scale: 0.96 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, x: 40 }}>
            <Alert severity="error" variant="filled" onClose={() => onDismiss(toast.id)}>{toast.message}</Alert>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}

export interface SegmentOption<T> {
  value: T;
  label: ReactNode;
  /** Colours the pill: a tag (engine, non_engine, brick); the accent otherwise */
  tone?: string;
}

/** Pick one of a few options (MUI toggle buttons), with a pill that slides to the selected one. */
export function Segmented<T extends string | number>({ value, options, onChange, pillId, label }: {
  value: T;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  /** Unique per control, so the pill slides within it */
  pillId: string;
  label: string;
}) {
  return (
    <ToggleButtonGroup exclusive value={value} aria-label={label}
                       onChange={(_, next: T | null) => next !== null && onChange(next)}>
      {options.map((option) => (
        <ToggleButton key={option.value} value={option.value}
                      className={option.tone ? `tone-${option.tone}` : ""}>
          {value === option.value && (
            <motion.span layoutId={pillId} className="segment-pill"
                         transition={{ type: "spring", stiffness: 500, damping: 38 }} />
          )}
          <span className="segment-label">{option.label}</span>
        </ToggleButton>
      ))}
    </ToggleButtonGroup>
  );
}

/** A small spinner for busy buttons */
export function Spinner() {
  return <CircularProgress size={16} color="inherit" thickness={5} />;
}

/** A number that eases to its new value whenever it changes. */
export function AnimatedPercent({ value, digits = 1 }: { value: number; digits?: number }) {
  const [shown, setShown] = useState(value);
  useEffect(() => {
    const start = performance.now();
    const from = shown;
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 450);
      const eased = 1 - Math.pow(1 - t, 3);
      setShown(from + (value - from) * eased);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  return <>{(shown * 100).toFixed(digits)}%</>;
}

/** A horizontal bar whose width animates to the value (0..1). */
export function Bar({ value, tone }: { value: number; tone: string }) {
  return (
    <div className="bar">
      <motion.div className={`bar-fill tone-${tone}`} initial={false}
                  animate={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
                  transition={{ type: "spring", stiffness: 140, damping: 22 }} />
    </div>
  );
}

/** A colour of a label or deck, as used by the tone-* classes */
export type Tone = "engine" | "non_engine" | "brick" | "deck-a" | "deck-b" | "mixed" | "untagged";

/** The tone of a deck in the comparison: side 0 is deck A (blue), side 1 deck B (pink) */
export const deckTone = (side: number): Tone => (side ? "deck-b" : "deck-a");

/** A small coloured dot in front of a label (decorative: the label says what it is) */
export function Dot({ tone }: { tone?: Tone }) {
  return <i className={`dot ${tone ? `tone-${tone}` : ""}`} aria-hidden="true" />;
}

/** A name that shortens with an ellipsis when it doesn't fit; hovering shows it in full */
export function TruncatedName({ children }: { children: string }) {
  return <Tooltip title={children}><span className="truncate-name">{children}</span></Tooltip>;
}

/** A panel (h2) or section (h3) title, an optional muted hint after it, and an optional action
 *  (e.g. an Export button) on the right */
export function SectionHeader({ as: Heading = "h3", title, hint, action, id }: {
  as?: "h2" | "h3";
  title: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  /** For aria-labelledby on the section */
  id?: string;
}) {
  const heading = <Heading id={id}>{title}{hint && <span className="muted small font-normal"> {hint}</span>}</Heading>;
  if (!action) return heading;
  return <div className="section-header">{heading}{action}</div>;
}

/** A number with a caption under it, e.g. "40 cards"; tone adds a coloured edge */
export function StatTile({ value, label, tone, wide = false }: { value: ReactNode; label: string; tone?: Tone; wide?: boolean }) {
  return (
    <div className={`stat-tile ${tone ? `tone-${tone}` : ""} ${wide ? "wide" : ""}`}>
      <span className="stat-value">{value}</span>
      <span className="muted">{label}</span>
    </div>
  );
}
