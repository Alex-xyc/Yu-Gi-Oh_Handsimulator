import GlobalStyles from "@mui/material/GlobalStyles";
import { StyledEngineProvider, ThemeProvider } from "@mui/material/styles";
import { MotionConfig } from "framer-motion";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
// The translations, set up before anything renders
import "./i18n";
import App from "./App";
// The fonts are bundled with the app (no requests to Google Fonts)
import "@fontsource/inter/latin-400.css";
import "@fontsource/inter/latin-500.css";
import "@fontsource/inter/latin-600.css";
import "@fontsource/inter/latin-700.css";
import "@fontsource/jetbrains-mono/latin-500.css";
import "./index.css";
import { theme } from "./theme";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {/* MUI's styles go in the "mui" CSS layer, below the app's stylesheet and Tailwind
        utilities (see index.css); the order is declared first, before any styles */}
    <StyledEngineProvider enableCssLayer>
      <GlobalStyles styles="@layer theme, base, mui, components, utilities;" />
      <ThemeProvider theme={theme}>
        {/* Follows the system "reduce motion" setting */}
        <MotionConfig reducedMotion="user">
          <App />
        </MotionConfig>
      </ThemeProvider>
    </StyledEngineProvider>
  </StrictMode>,
);
