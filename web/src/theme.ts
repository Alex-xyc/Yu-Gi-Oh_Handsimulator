// The MUI theme: the app's dark look (colours, shapes, buttons, inputs, menus) in one place.
// Component colours can use the tag and deck colours too, e.g. <Button color="engine">.
// All values come from the design tokens (src/design/tokens.ts).

import { alpha, createTheme, PaletteColor, PaletteColorOptions, ThemeOptions } from "@mui/material/styles";
import { colors, ease, font } from "./design/tokens";

type AppColor = "engine" | "requirement" | "nonEngine" | "brick" | "deckA" | "deckB";

declare module "@mui/material/styles" {
  interface Palette {
    engine: PaletteColor; requirement: PaletteColor; nonEngine: PaletteColor; brick: PaletteColor;
    deckA: PaletteColor; deckB: PaletteColor;
  }
  interface PaletteOptions {
    engine?: PaletteColorOptions; requirement?: PaletteColorOptions; nonEngine?: PaletteColorOptions;
    brick?: PaletteColorOptions;
    deckA?: PaletteColorOptions; deckB?: PaletteColorOptions;
  }
}
type ColorOverrides = { [K in AppColor]: true };
declare module "@mui/material/Button" { interface ButtonPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/ToggleButton" { interface ToggleButtonPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/Chip" { interface ChipPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/Checkbox" { interface CheckboxPropsColorOverrides extends ColorOverrides {} }

const ACCENT = colors.accent;
const TEXT = colors.text;
const MUTED = colors.muted;
const SURFACE_2 = colors["surface-2"];
const SURFACE_3 = colors["surface-3"];
const BORDER_STRONG = colors["line-strong"];
const EASE = ease;
const COLORS: Record<AppColor | "primary", string> = {
  primary: ACCENT, engine: colors.engine, requirement: colors.requirement, nonEngine: colors["non-engine"],
  brick: colors.brick,
  deckA: colors["deck-a"], deckB: colors["deck-b"],
};

const base = createTheme({
  palette: {
    mode: "dark",
    primary: { main: ACCENT, light: colors["accent-hover"], dark: colors["accent-strong"], contrastText: "#fff" },
    error: { main: colors.brick, light: colors.danger },
    success: { main: colors.engine, light: colors.ok },
    background: { default: colors.bg, paper: colors.surface },
    text: { primary: TEXT, secondary: MUTED },
    divider: colors.line,
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: font.sans,
    fontSize: 14,
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
});

const color = (main: string, contrastText?: string) =>
  base.palette.augmentColor({ color: { main, ...(contrastText ? { contrastText } : {}) } });

const options: ThemeOptions = {
  palette: {
    // Dark text on the bright colours keeps it readable (WCAG AA)
    engine: color(COLORS.engine, colors.ink),
    requirement: color(COLORS.requirement, colors.ink),
    nonEngine: color(COLORS.nonEngine, colors.ink),
    brick: color(COLORS.brick, colors.ink),
    deckA: color(COLORS.deckA, colors.ink),
    deckB: color(COLORS.deckB, colors.ink),
  },
  components: {
    MuiButtonBase: { defaultProps: { disableRipple: true } },
    MuiButton: {
      defaultProps: { disableElevation: true },
      styleOverrides: {
        root: {
          height: 38, padding: "0 16px", whiteSpace: "nowrap",
          transition: `background 0.18s ${EASE}, border-color 0.18s ${EASE}, transform 0.12s ${EASE}, box-shadow 0.18s ${EASE}`,
          "&:hover:not(:disabled)": { transform: "translateY(-1px)" },
          "&:active:not(:disabled)": { transform: "translateY(0) scale(0.98)" },
          "&.Mui-disabled": { opacity: 0.45 },
          "&.Mui-focusVisible": { outline: `2px solid ${ACCENT}`, outlineOffset: 2 },
        },
        sizeSmall: { height: 30, padding: "0 12px", fontSize: 13 },
        sizeLarge: { height: 44, padding: "0 22px", fontSize: 15 },
      },
      variants: [
        // Filled primary: the glowing purple gradient, dark enough for white text (WCAG AA)
        { props: { variant: "contained", color: "primary" },
          style: {
            background: `linear-gradient(180deg, ${ACCENT}, ${colors["accent-strong"]})`,
            boxShadow: `0 6px 20px ${alpha(ACCENT, 0.35)}`,
            "&:hover": { background: `linear-gradient(180deg, ${colors["accent-hover"]}, ${ACCENT})`, boxShadow: `0 8px 28px ${alpha(ACCENT, 0.5)}` },
            "&.Mui-disabled": { color: "#fff", background: colors["accent-strong"] },
          } },
        // Outlined "inherit": the plain grey button; text "inherit": the same, see-through
        { props: { variant: "outlined", color: "inherit" },
          style: { background: SURFACE_2, borderColor: BORDER_STRONG, "&:hover": { background: SURFACE_3, borderColor: BORDER_STRONG } } },
        { props: { variant: "text", color: "inherit" },
          style: { border: `1px solid ${BORDER_STRONG}`, "&:hover": { background: SURFACE_3 } } },
        // Coloured outlines: a soft tint of the colour
        ...(["primary", "engine", "requirement", "nonEngine", "brick"] as const).map((key) => ({
          props: { variant: "outlined" as const, color: key },
          style: {
            color: key === "primary" ? "#c9bcff" : TEXT,
            background: alpha(COLORS[key], 0.18), borderColor: alpha(COLORS[key], 0.5),
            "&:hover": { background: alpha(COLORS[key], 0.3), borderColor: alpha(COLORS[key], 0.6) },
          },
        })),
      ],
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          background: "rgba(0, 0, 0, 0.25)",
          transition: "box-shadow 0.18s, background 0.18s",
          "& .MuiOutlinedInput-notchedOutline": { borderColor: BORDER_STRONG, transition: "border-color 0.18s" },
          "&:hover:not(.Mui-focused):not(.Mui-disabled) .MuiOutlinedInput-notchedOutline": { borderColor: "rgba(255, 255, 255, 0.25)" },
          "&.Mui-focused": { boxShadow: `0 0 0 4px ${alpha(ACCENT, 0.16)}` },
          "&.Mui-focused .MuiOutlinedInput-notchedOutline": { borderWidth: 1 },
        },
        input: {
          height: 38, padding: "0 12px", boxSizing: "border-box",
          "&::placeholder": { color: colors.faint, opacity: 1 },
        },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: { padding: 3, borderRadius: 12, background: "rgba(0, 0, 0, 0.3)", border: `1px solid ${colors.line}`, gap: 2 },
        grouped: { border: "none !important", borderRadius: "9px !important", margin: 0 },
      },
    },
    MuiToggleButton: {
      styleOverrides: {
        // The selected look is a sliding pill drawn by the Segmented component
        root: {
          position: "relative", padding: "6px 14px", fontSize: 14, color: MUTED, lineHeight: 1.5,
          transition: "color 0.2s",
          "&:hover": { background: "rgba(255, 255, 255, 0.04)" },
          "&.Mui-selected, &.Mui-selected:hover": { background: "transparent", color: "#fff" },
          "&.Mui-focusVisible": { outline: `2px solid ${ACCENT}`, outlineOffset: 2 },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: { height: 26, fontSize: 12, borderRadius: 999, background: SURFACE_2, border: `1px solid ${colors.line}` },
        label: { paddingLeft: 10, paddingRight: 10 },
        icon: { marginLeft: 10, marginRight: -4 },
      },
      variants: (["engine", "requirement", "nonEngine", "brick", "deckA", "deckB"] as const).map((key) => ({
        props: { color: key },
        style: { color: TEXT, background: alpha(COLORS[key], 0.16), borderColor: alpha(COLORS[key], 0.4) },
      })),
    },
    MuiAlert: {
      styleOverrides: {
        root: { borderRadius: 12, boxShadow: "0 12px 36px rgba(0, 0, 0, 0.5)", alignItems: "center" },
      },
      variants: [
        { props: { variant: "filled", severity: "error" },
          style: { background: "#2a1517", color: TEXT, border: "1px solid rgba(239, 68, 68, 0.45)" } },
      ],
    },
    MuiTooltip: {
      defaultProps: { arrow: true, enterDelay: 400 },
      styleOverrides: {
        tooltip: { background: SURFACE_3, border: `1px solid ${BORDER_STRONG}`, fontSize: 12, fontWeight: 500 },
        arrow: { color: SURFACE_3 },
      },
    },
    MuiCheckbox: { styleOverrides: { root: { padding: 4 } } },
    MuiFormControlLabel: { styleOverrides: { root: { marginLeft: -4, marginRight: 0, gap: 4 }, label: { fontSize: 14 } } },
  },
};

export const theme = createTheme(base, options);
