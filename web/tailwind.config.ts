// Tailwind's theme, from the app's design tokens (src/design/tokens.ts). Loaded by index.css
// with @config. Gives classes such as text-engine, bg-surface-2, border-line, rounded-panel,
// shadow-panel and font-mono, and writes every token as a CSS variable for styles.css.

import plugin from "tailwindcss/plugin";
import { colors, cssVariables, font, radius, shadow } from "./src/design/tokens";

export default {
  theme: {
    extend: {
      colors,
      borderRadius: radius,
      boxShadow: shadow,
      fontFamily: { sans: font.sans, mono: font.mono },
      // Where a deck tab's panels go side by side: wider than landscape tablets (up to ~1180px),
      // which get the roomier one-column layout
      screens: { wide: "75rem" },
    },
  },
  plugins: [
    plugin(({ addBase }) => {
      addBase({ ":root": cssVariables() });
    }),
  ],
};
