// The MUI theme: the app's dark look (colours, shapes, buttons, inputs, dialogs) in one place.
// Component colours can use the tag and deck colours too, e.g. <Button color="engine">.

import { alpha, createTheme, PaletteColor, PaletteColorOptions, ThemeOptions } from "@mui/material/styles";

type AppColor = "engine" | "nonEngine" | "brick" | "deckA" | "deckB";

declare module "@mui/material/styles" {
  interface Palette { engine: PaletteColor; nonEngine: PaletteColor; brick: PaletteColor; deckA: PaletteColor; deckB: PaletteColor }
  interface PaletteOptions {
    engine?: PaletteColorOptions; nonEngine?: PaletteColorOptions; brick?: PaletteColorOptions;
    deckA?: PaletteColorOptions; deckB?: PaletteColorOptions;
  }
}
type ColorOverrides = { [K in AppColor]: true };
declare module "@mui/material/Button" { interface ButtonPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/ToggleButton" { interface ToggleButtonPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/Chip" { interface ChipPropsColorOverrides extends ColorOverrides {} }
declare module "@mui/material/Checkbox" { interface CheckboxPropsColorOverrides extends ColorOverrides {} }

// Keep in step with the colour tokens at the top of styles.css
const ACCENT = "#7c5cff";
const TEXT = "#e9ebf2";
const MUTED = "#8a92a6";
const SURFACE_2 = "#1c202b";
const SURFACE_3 = "#252a37";
const BORDER_STRONG = "rgba(255, 255, 255, 0.13)";
const EASE = "cubic-bezier(0.2, 0.7, 0.2, 1)";
const COLORS: Record<AppColor | "primary", string> = {
  primary: ACCENT, engine: "#22c55e", nonEngine: "#eab308", brick: "#ef4444", deckA: "#4f8dff", deckB: "#f472b6",
};

const base = createTheme({
  palette: {
    mode: "dark",
    primary: { main: ACCENT, light: "#8f74ff", contrastText: "#fff" },
    error: { main: "#ef4444", light: "#f87171" },
    success: { main: "#22c55e", light: "#4ade80" },
    background: { default: "#0a0c11", paper: "#151821" },
    text: { primary: TEXT, secondary: MUTED },
    divider: "rgba(255, 255, 255, 0.07)",
  },
  shape: { borderRadius: 10 },
  typography: {
    fontFamily: 'Inter, system-ui, -apple-system, "Segoe UI", sans-serif',
    fontSize: 14,
    button: { textTransform: "none", fontWeight: 600, letterSpacing: 0 },
  },
});

const color = (main: string, contrastText?: string) =>
  base.palette.augmentColor({ color: { main, ...(contrastText ? { contrastText } : {}) } });

const options: ThemeOptions = {
  palette: {
    engine: color(COLORS.engine, "#0b0d12"),
    nonEngine: color(COLORS.nonEngine, "#0b0d12"),
    brick: color(COLORS.brick),
    deckA: color(COLORS.deckA),
    deckB: color(COLORS.deckB, "#0b0d12"),
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
        // Filled primary: the glowing purple gradient
        { props: { variant: "contained", color: "primary" },
          style: {
            background: `linear-gradient(180deg, #8f74ff, ${ACCENT})`,
            boxShadow: `0 6px 20px ${alpha(ACCENT, 0.35)}`,
            "&:hover": { background: "linear-gradient(180deg, #a08aff, #8f74ff)", boxShadow: `0 8px 28px ${alpha(ACCENT, 0.5)}` },
            "&.Mui-disabled": { color: "#fff", background: ACCENT },
          } },
        // Outlined "inherit": the plain grey button; text "inherit": the same, see-through
        { props: { variant: "outlined", color: "inherit" },
          style: { background: SURFACE_2, borderColor: BORDER_STRONG, "&:hover": { background: SURFACE_3, borderColor: BORDER_STRONG } } },
        { props: { variant: "text", color: "inherit" },
          style: { border: `1px solid ${BORDER_STRONG}`, "&:hover": { background: SURFACE_3 } } },
        // Coloured outlines: a soft tint of the colour
        ...(["primary", "engine", "nonEngine", "brick"] as const).map((key) => ({
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
          "&::placeholder": { color: "#5d6476", opacity: 1 },
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: { minHeight: 44, borderBottom: "1px solid rgba(255, 255, 255, 0.07)" },
        indicator: { height: 2, borderRadius: 2 },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          minHeight: 44, minWidth: 0, padding: "10px 16px", fontSize: 14, color: MUTED,
          "&.Mui-selected": { color: TEXT },
          "&.Mui-focusVisible": { outline: `2px solid ${ACCENT}`, outlineOffset: -2, borderRadius: 8 },
        },
      },
    },
    MuiToggleButtonGroup: {
      styleOverrides: {
        root: { padding: 3, borderRadius: 12, background: "rgba(0, 0, 0, 0.3)", border: "1px solid rgba(255, 255, 255, 0.07)", gap: 2 },
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
        root: { height: 26, fontSize: 12, borderRadius: 999, background: SURFACE_2, border: "1px solid rgba(255, 255, 255, 0.07)" },
        label: { paddingLeft: 10, paddingRight: 10 },
        icon: { marginLeft: 10, marginRight: -4 },
      },
      variants: (["engine", "nonEngine", "brick", "deckA", "deckB"] as const).map((key) => ({
        props: { color: key },
        style: { color: TEXT, background: alpha(COLORS[key], 0.16), borderColor: alpha(COLORS[key], 0.4) },
      })),
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          background: SURFACE_2, backgroundImage: "none", border: `1px solid ${BORDER_STRONG}`,
          borderRadius: 16, boxShadow: "0 30px 80px rgba(0, 0, 0, 0.6)",
        },
      },
    },
    MuiDialogTitle: { styleOverrides: { root: { fontSize: 16, fontWeight: 650, padding: "22px 22px 8px" } } },
    MuiDialogContent: { styleOverrides: { root: { padding: "0 22px", color: MUTED } } },
    MuiDialogActions: { styleOverrides: { root: { padding: 22, gap: 8, "& > :not(style) ~ :not(style)": { marginLeft: 0 } } } },
    MuiBackdrop: { styleOverrides: { root: { backgroundColor: "rgba(0, 0, 0, 0.5)" } } },
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
