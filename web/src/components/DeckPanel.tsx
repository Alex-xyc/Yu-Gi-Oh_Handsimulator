// Loading a deck (ydke:// code or .ydk file) and showing its label totals

import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import { motion } from "framer-motion";
import { type DragEvent, memo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { CATEGORIES } from "../api";
import type { DeckSetup } from "../useDeckSetup";
import { Dot, Spinner } from "./common";

export const DeckLoader = memo(function DeckLoader({ setup, onError }: { setup: DeckSetup; onError: (message: string) => void }) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = async (text: string, name?: string) => {
    try {
      await setup.load(text, name);
    } catch (e) {
      onError(e instanceof Error ? e.message : t("loader.failed"));
    }
  };

  const loadCode = () => {
    const trimmed = code.trim();
    if (!trimmed) return onError(t("loader.noCode"));
    if (!trimmed.startsWith("ydke://")) return onError(t("loader.invalidCode"));
    load(trimmed);
  };

  const loadFile = async (file: File | undefined) => {
    if (!file) return;
    load(await file.text(), file.name.replace(/\.ydk$/i, ""));
  };

  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDragging(false);
    loadFile(e.dataTransfer.files[0]);
  };

  return (
    // biome-ignore lint/a11y/noStaticElementInteractions: dropping a .ydk file is a shortcut for the file button and the code field
    <div className={`deck-loader ${dragging ? "dragging" : ""}`}
         onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
         onDragLeave={() => setDragging(false)} onDrop={onDrop}>
      <div className="loader-row">
        <TextField className="grow" placeholder={t("loader.placeholder")} value={code} fullWidth
                   onChange={(e) => setCode(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && loadCode()}
                   slotProps={{ htmlInput: { "aria-label": t("loader.codeLabel"), spellCheck: false } }} />
        <Button variant="contained" onClick={loadCode} disabled={setup.loading} sx={{ minWidth: 72 }}>
          {setup.loading ? <Spinner /> : t("loader.load")}
        </Button>
      </div>
      <div className="loader-row secondary">
        <span className="muted">{t("loader.or")}</span>
        <Button color="inherit" size="small" onClick={() => fileInput.current?.click()}>
          {t("loader.upload")}
        </Button>
        <span className="muted file-name" title={setup.name ?? undefined}>
          {setup.name ? t("loader.loaded", { name: setup.name }) : t("loader.dropHint")}
        </span>
        <input ref={fileInput} type="file" accept=".ydk,text/plain" hidden
               onChange={(e) => { loadFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
    </div>
  );
});

/** A deck's size and label totals (used in the compare view; labelling is done in the deck's tab) */
export function DeckStatus({ setup }: { setup: DeckSetup }) {
  const { t } = useTranslation();
  const count = (key: string) => setup.tags.filter((tag) => tag === key).length;
  const unlabelled = count("");
  return (
    <motion.div className="deck-status" key={`${setup.size}-${setup.tags.join()}`}
                initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
      {!setup.cards ? (
        <span className="muted">{t("deckStatus.noDeck")}</span>
      ) : (
        <span className="flex flex-wrap items-center gap-x-3">
          <span className="ok">{t("deckStatus.cards", { count: setup.size })}</span>
          {CATEGORIES.map((key) => (
            <span key={key} className="muted">
              <Dot tone={key} />{t("deckStatus.categoryCount", { count: count(key), label: t(`categories.${key}`) })}
            </span>
          ))}
          {unlabelled > 0 && <span className="muted">{t("deckStatus.unlabelled", { count: unlabelled })}</span>}
        </span>
      )}
    </motion.div>
  );
}
