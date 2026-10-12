// Loading a deck (ydke:// code or .ydk file) and showing its label totals

import Button from "@mui/material/Button";
import TextField from "@mui/material/TextField";
import { motion } from "framer-motion";
import { DragEvent, memo, useRef, useState } from "react";
import { CATEGORIES, CATEGORY_LABELS } from "../api";
import { DeckSetup } from "../useDeckSetup";
import { Dot, Spinner } from "./common";

export const DeckLoader = memo(function DeckLoader({ setup, onError }: { setup: DeckSetup; onError: (message: string) => void }) {
  const [code, setCode] = useState("");
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);

  const load = async (text: string, name?: string) => {
    try {
      await setup.load(text, name);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Failed to load deck.");
    }
  };

  const loadCode = () => {
    const trimmed = code.trim();
    if (!trimmed) return onError("Please paste a ydke:// code.");
    if (!trimmed.startsWith("ydke://")) return onError("Invalid format. Code must start with 'ydke://'.");
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
    <div className={`deck-loader ${dragging ? "dragging" : ""}`}
         onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
         onDragLeave={() => setDragging(false)} onDrop={onDrop}>
      <div className="loader-row">
        <TextField className="grow" placeholder="Paste a ydke:// code…" value={code} fullWidth
                   onChange={(e) => setCode(e.target.value)}
                   onKeyDown={(e) => e.key === "Enter" && loadCode()}
                   slotProps={{ htmlInput: { "aria-label": "ydke:// code", spellCheck: false } }} />
        <Button variant="contained" onClick={loadCode} disabled={setup.loading} sx={{ minWidth: 72 }}>
          {setup.loading ? <Spinner /> : "Load"}
        </Button>
      </div>
      <div className="loader-row secondary">
        <span className="muted">or</span>
        <Button color="inherit" size="small" onClick={() => fileInput.current?.click()}>
          Upload .ydk
        </Button>
        <span className="muted file-name" title={setup.name ?? undefined}>
          {setup.name ? `Loaded ${setup.name}` : "or drop a .ydk file here"}
        </span>
        <input ref={fileInput} type="file" accept=".ydk,text/plain" hidden
               onChange={(e) => { loadFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
    </div>
  );
});

/** A deck's size and label totals (used in the compare view; labelling is done in the deck's tab) */
export function DeckStatus({ setup }: { setup: DeckSetup }) {
  const count = (key: string) => setup.tags.filter((t) => t === key).length;
  const unlabelled = count("");
  return (
    <motion.div className="deck-status" key={`${setup.size}-${setup.tags.join()}`}
                initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }}>
      {!setup.cards ? (
        <span className="muted">No deck loaded. Load one in its tab.</span>
      ) : (
        <span className="flex flex-wrap items-center gap-x-3">
          <span className="ok">✓ {setup.size} cards</span>
          {CATEGORIES.map((key) => (
            <span key={key} className="muted"><Dot tone={key} />{count(key)} {CATEGORY_LABELS[key]}</span>
          ))}
          {unlabelled > 0 && <span className="muted">{unlabelled} unlabelled</span>}
        </span>
      )}
    </motion.div>
  );
}
