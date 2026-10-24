// The page's text in each language: locales/<code>.json, one file per language with the same keys
// as en.json (English, the only language so far, and the fallback for any key a language lacks).
// Components take their text from useTranslation(), so they update when the language changes;
// code outside components (exports, error messages) uses i18n.t, which reads the current language.
//
// To add a language: copy en.json to locales/<code>.json, translate the values (keep the keys and
// the {{placeholders}}; plural forms are the _one / _other / … suffixes of the language), and add
// it to `resources` below. Switching is then i18n.changeLanguage("<code>").

import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import en from "./locales/en.json";

export const resources = {
  en: { translation: en },
} as const;

export type Language = keyof typeof resources;

i18n.use(initReactI18next).init({
  resources,
  lng: "en",
  fallbackLng: "en",
  supportedLngs: Object.keys(resources),
  // React escapes text itself
  interpolation: { escapeValue: false },
  // The translations are bundled, so they're ready as soon as this module has run
  initAsync: false,
});

// Keep the page's language and title in step (no document in the unit tests)
const applyLanguage = (language: string) => {
  if (typeof document === "undefined") return;
  document.documentElement.lang = language;
  document.title = i18n.t("app.pageTitle");
};
applyLanguage(i18n.language);
i18n.on("languageChanged", applyLanguage);

export default i18n;
