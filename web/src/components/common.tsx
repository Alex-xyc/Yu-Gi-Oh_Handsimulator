// Small building blocks shared across the app

import Alert from "@mui/material/Alert";
import CircularProgress from "@mui/material/CircularProgress";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Tooltip from "@mui/material/Tooltip";
import { AnimatePresence, motion, type Variants } from "framer-motion";
import { type ReactNode, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { cardImageUrl, type DeckCard, loadedImages, percent, percentDigits } from "../api";
import { GENESYS_CAP, genesysTotal, useBanStatus, useGenesys, useGenesysPoints, useGenesysTotal } from "../banStatus";

const IMAGE_RETRY_MS = 30_000;

/** A card's top right corner: its TCG banlist icon, or in Genesys mode its points */
function BanMark({ id }: { id?: string }) {
  return useGenesys() ? <PointsMark id={id} /> : <BanlistMark id={id} />;
}

/** A card's Genesys points in the banlist icons' style: a yellow number on black in a red-ringed
 *  pill (a pill, not a circle, so 1 or 2 points don't read as Limited or Semi-Limited). None for
 *  a card worth 0, like an unlimited card's banlist icon. */
function PointsMark({ id }: { id?: string }) {
  const { t } = useTranslation();
  const points = useGenesysPoints(id);
  if (!points) return null;
  const text = String(points);
  // Wide enough for its digits; the CSS sizes it to match (--w)
  const width = 12 + 9 * text.length;
  const label = t("genesys.cardPoints", { count: points });
  return (
    <span className="ban-mark points" style={{ ["--w" as string]: width }} role="img" aria-label={label} title={label}>
      <svg viewBox={`0 0 ${width} 24`} aria-hidden="true">
        <rect x="1.75" y="1.75" width={width - 3.5} height="20.5" rx="10.25" className="ban-face" />
        <text x={width / 2} y="13" className="ban-text" fontSize="14">{text}</text>
      </svg>
    </span>
  );
}

/** The banlist icon: a red ring on black (struck through when forbidden, else a yellow 1 or 2),
 *  or a red-framed "OCG" for a card not out in the TCG yet */
function BanlistMark({ id }: { id?: string }) {
  const { t } = useTranslation();
  const status = useBanStatus(id);
  if (!status) return null;
  const label = t(`banlist.${status}`);
  const digit = { limited: "1", semi_limited: "2" }[status as string];
  return (
    <span className={`ban-mark ${status === "ocg" ? "ocg" : ""}`} role="img" aria-label={label} title={label}>
      {status === "ocg" ? (
        <svg viewBox="0 0 44 24" aria-hidden="true">
          <rect x="1.75" y="1.75" width="40.5" height="20.5" rx="4" className="ban-face" />
          <text x="22" y="13" className="ban-text" fontSize="13.5">{t("banlist.ocgMark")}</text>
        </svg>
      ) : (
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="10.1" className="ban-face" />
          {digit ? (
            <text x="12" y="13" className="ban-text" fontSize="15">{digit}</text>
          ) : (
            <line x1="5.4" y1="5.4" x2="18.6" y2="18.6" className="ban-slash" />
          )}
        </svg>
      )}
    </span>
  );
}

/** The deck's Genesys points (main and side deck: Genesys counts both) out of the cap, red when
 *  over it; hovering shows the split. Shown in Genesys mode only. */
export function GenesysTotal({ cards, side }: { cards: DeckCard[]; side: DeckCard[] | null }) {
  const { t } = useTranslation();
  const all = useMemo(() => [...cards, ...(side ?? [])], [cards, side]);
  const total = useGenesysTotal(all);
  if (!useGenesys()) return null;
  const over = total !== null && total > GENESYS_CAP;
  const title = total === null ? t("genesys.totalLoading")
    : t("genesys.totalTitle", { main: genesysTotal(cards) ?? 0, side: genesysTotal(side ?? []) ?? 0, cap: GENESYS_CAP })
      + (over ? ` ${t("genesys.overCap", { count: total - GENESYS_CAP, cap: GENESYS_CAP })}` : "");
  return (
    <Tooltip title={title}>
      <span className={`genesys-total ${over ? "over" : ""}`}>
        {t("genesys.total", { total: total ?? "…", cap: GENESYS_CAP })}
      </span>
    </Tooltip>
  );
}

/** "SIDE" in a blue frame, in the banlist icons' style: a card that's out of the deck it started in
 *  (sided in, or sided out). Top left on a card, or `inline` in text (a legend) */
export function SideIcon({ inline = false, className = "" }: { inline?: boolean; className?: string }) {
  const { t } = useTranslation();
  return (
    <span className={`side-icon ${inline ? "inline" : ""} ${className}`} aria-hidden="true">
      <svg viewBox="0 0 52 24" aria-hidden="true">
        <rect x="1.75" y="1.75" width="48.5" height="20.5" rx="4" className="side-face" />
        <text x="26" y="13" className="ban-text side-text" fontSize="13.5">{t("banlist.sideMark")}</text>
      </svg>
    </span>
  );
}

/** A card picture, or its name on a plain tile when there's no image. */
export function CardImage({ id, name, size = "small", className = "" }: {
  id?: string; name: string; size?: "small" | "full"; className?: string;
}) {
  const url = cardImageUrl(id, size);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  // An image loaded before (e.g. in another view, or prefetched) shows straight away, without the fade
  const [loaded, setLoaded] = useState(() => url !== null && loadedImages.has(url));
  useEffect(() => { setFailed(false); setAttempt(0); setLoaded(url !== null && loadedImages.has(url)); }, [url]);
  // The server may be holding off the image sites for a moment (it answers 503): try once more later
  useEffect(() => {
    if (!failed || attempt > 0) return;
    const timer = setTimeout(() => { setAttempt(1); setFailed(false); }, IMAGE_RETRY_MS);
    return () => clearTimeout(timer);
  }, [failed, attempt]);

  return (
    <div className={`card-image ${className}`}>
      {url && !failed ? (
        <img key={attempt} src={url} alt={name} draggable={false} loading="lazy"
             className={loaded ? "loaded" : ""}
             onLoad={() => { loadedImages.add(url); setLoaded(true); }} onError={() => setFailed(true)} />
      ) : null}
      {(!url || failed || !loaded) && <span className="card-image-name">{name}</span>}
      <BanMark id={id} />
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
 *  outside it. With `fit` the window takes its full height and doesn't scroll: the contents fill
 *  it and size themselves to it. Focus moves into it while open; the page behind should be made
 *  inert meanwhile. */
export function Overlay({ open, onClose, children, label, keepMounted = false, asWindow = false, fit = false }: {
  open: boolean; onClose: () => void; children: ReactNode; label: string; keepMounted?: boolean; asWindow?: boolean;
  fit?: boolean;
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
      <motion.div className={`overlay-panel ${fit ? "fit" : ""}`} variants={PANEL} ref={panel} tabIndex={-1}>
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

/** Pick one of a few options (MUI toggle buttons), with a pill that slides to the selected one.
 *  The pill is one element behind all the buttons, moved to the selected button's measured box:
 *  a pill inside each button (a shared layout animation) would pass over the earlier buttons'
 *  labels while sliding, and clicking quickly could leave a label hidden under it. */
export function Segmented<T extends string | number>({ value, options, onChange, label, small = false }: {
  /** null: none selected */
  value: T | null;
  options: SegmentOption<T>[];
  onChange: (value: T) => void;
  label: string;
  small?: boolean;
}) {
  const box = useRef<HTMLDivElement>(null);
  const [pill, setPill] = useState<{ x: number; y: number; width: number; height: number } | null>(null);
  // biome-ignore lint/correctness/useExhaustiveDependencies: measured again when the selected option changes
  useLayoutEffect(() => {
    const root = box.current;
    if (!root) return;
    const measure = () => {
      const selected = root.querySelector<HTMLElement>(".Mui-selected");
      if (!selected) return setPill(null);
      const outer = root.getBoundingClientRect();
      const inner = selected.getBoundingClientRect();
      // Not laid out (e.g. in a hidden deck tab): measured again once shown
      if (!outer.width || !inner.width) return;
      setPill({ x: inner.left - outer.left, y: inner.top - outer.top, width: inner.width, height: inner.height });
    };
    measure();
    // Again when the labels change size (fonts loading, the window narrowing)
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    return () => observer.disconnect();
  }, [value]);
  const tone = options.find((option) => option.value === value)?.tone;

  // The pill comes before the group so it's drawn over the group's background but under every label
  return (
    <div className="segmented" ref={box}>
      {pill && (
        <motion.span className={`segment-pill ${tone ? `tone-${tone}` : ""}`} aria-hidden="true"
                     initial={false} animate={pill}
                     transition={{ duration: 0.22, ease: [0.25, 0.8, 0.3, 1] }} />
      )}
      <ToggleButtonGroup exclusive value={value} aria-label={label} size={small ? "small" : "medium"}
                         onChange={(_, next: T | null) => next !== null && onChange(next)}>
        {options.map((option) => (
          <ToggleButton key={option.value} value={option.value}
                        className={option.tone ? `tone-${option.tone}` : ""}>
            <span className="segment-label">{option.label}</span>
          </ToggleButton>
        ))}
      </ToggleButtonGroup>
    </div>
  );
}

/** A small spinner for busy buttons */
export function Spinner() {
  return <CircularProgress size={16} color="inherit" thickness={5} />;
}

/** A number that eases to its new value whenever it changes. */
export function AnimatedPercent({ value, digits = 1 }: { value: number; digits?: number }) {
  const [shown, setShown] = useState(value);
  // biome-ignore lint/correctness/useExhaustiveDependencies: eases from what's shown when the value changes; restarting on every frame would never finish
  useEffect(() => {
    const start = performance.now();
    const from = shown;
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / 450);
      const eased = 1 - (1 - t) ** 3;
      setShown(from + (value - from) * eased);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [value]);
  // Decimals from the target, so the width doesn't jump while counting
  return <>{percent(shown, digits, percentDigits(value, digits))}</>;
}

/** The style giving a component a custom label's colour (with the "custom" tone) */
export const toneColor = (color?: string) => (color ? { ["--tone" as string]: color } : undefined);

/** A horizontal bar whose width animates to the value (0..1). `color`: a custom label's, with the
 *  "custom" tone */
export function Bar({ value, tone, color }: { value: number; tone: string; color?: string }) {
  return (
    <div className="bar" style={toneColor(color)}>
      <motion.div className={`bar-fill tone-${tone}`} initial={false}
                  animate={{ width: `${Math.max(0, Math.min(1, value)) * 100}%` }}
                  transition={{ type: "spring", stiffness: 140, damping: 22 }} />
    </div>
  );
}

/** A colour of a label or deck, as used by the tone-* classes */
export type Tone = "engine" | "non_engine" | "brick" | "deck-a" | "deck-b" | "mixed" | "untagged" | "side" | "custom";

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

/** A number with a caption under it, e.g. "40 cards"; tone adds a coloured edge (`color` for a
 *  custom label's) */
export function StatTile({ value, label, tone, color, wide = false }: {
  value: ReactNode; label: string; tone?: Tone; color?: string; wide?: boolean;
}) {
  return (
    <div className={`stat-tile ${tone ? `tone-${tone}` : ""} ${wide ? "wide" : ""}`} style={toneColor(color)}>
      <span className="stat-value">{value}</span>
      <span className="muted">{label}</span>
    </div>
  );
}
