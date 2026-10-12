// The design tokens: every colour, radius, shadow and font of the app, defined once.
//
// Used by tailwind.config.ts, which turns them into Tailwind classes (text-engine, bg-surface-2,
// rounded-panel, …) and CSS variables (--color-engine, --radius-panel, …) for styles.css, and by
// theme.ts for the MUI components.
//
// Naming: kebab-case. Colours are named by role, not by hue (surface, line, accent, ink);
// the tag colours match the data keys (engine, non-engine, brick).

export const colors = {
  /** Page background, behind everything */
  bg: "#0a0c11",
  /** A see-through panel over the page */
  panel: "rgba(22, 25, 34, 0.86)",
  /** Solid surfaces, from lowest to highest */
  surface: "#151821",
  "surface-2": "#1c202b",
  "surface-3": "#252a37",
  /** Borders and dividers */
  line: "rgba(255, 255, 255, 0.07)",
  "line-strong": "rgba(255, 255, 255, 0.13)",
  text: "#e9ebf2",
  muted: "#8a92a6",
  /** Placeholder text in inputs */
  faint: "#7a8296",
  /** Dark text on light or brightly coloured backgrounds */
  ink: "#0b0d12",
  /** Purple brand colour; accent-strong holds white text at WCAG AA (4.5:1) */
  accent: "#7c5cff",
  "accent-hover": "#8f74ff",
  "accent-strong": "#6a46f5",
  "accent-soft": "rgba(124, 92, 255, 0.16)",
  /** The call to action in the comparison (React-logo blue) */
  highlight: "#61dafb",
  "highlight-hover": "#8ae4fc",
  /** Card labels: brick red, non-engine yellow, engine green */
  engine: "#22c55e",
  "non-engine": "#eab308",
  brick: "#ef4444",
  /** The two decks in the comparison: blue and pink, apart from the accent and the labels */
  "deck-a": "#4f8dff",
  "deck-b": "#f472b6",
  /** The 6th card's marker: Okabe–Ito sky blue, readable with colour blindness */
  sixth: "#56b4e9",
  /** Status text */
  ok: "#4ade80",
  danger: "#f87171",
} as const;

export type ColorName = keyof typeof colors;

export const radius = {
  /** Panels and cards */
  panel: "16px",
  /** Buttons, inputs, small boxes */
  control: "10px",
} as const;

export const shadow = {
  panel: "0 10px 40px rgba(0, 0, 0, 0.45), 0 1px 0 rgba(255, 255, 255, 0.04) inset",
  overlay: "0 30px 80px rgba(0, 0, 0, 0.6)",
} as const;

export const font = {
  sans: 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
  mono: '"JetBrains Mono", Consolas, monospace',
} as const;

/** The app's easing curve (quick start, soft landing) */
export const ease = "cubic-bezier(0.2, 0.7, 0.2, 1)";

/** The faint purple and cyan glows behind the page */
export const bgGlow =
  "radial-gradient(1200px 600px at 15% -10%, rgba(124, 92, 255, 0.16), transparent 60%), " +
  "radial-gradient(900px 500px at 100% 0%, rgba(34, 211, 238, 0.08), transparent 60%)";

/** All tokens as CSS variables (--color-engine, --radius-panel, …) for styles.css */
export function cssVariables(): Record<string, string> {
  return {
    ...Object.fromEntries(Object.entries(colors).map(([name, value]) => [`--color-${name}`, value])),
    ...Object.fromEntries(Object.entries(radius).map(([name, value]) => [`--radius-${name}`, value])),
    ...Object.fromEntries(Object.entries(shadow).map(([name, value]) => [`--shadow-${name}`, value])),
    "--font-sans": font.sans,
    "--font-mono": font.mono,
    "--ease-smooth": ease,
    "--bg-glow": bgGlow,
  };
}
