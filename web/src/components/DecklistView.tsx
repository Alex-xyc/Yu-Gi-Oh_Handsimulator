// Tag each card copy as engine / non-engine / brick by clicking it. The controls (TagControls)
// and the cards (TagGrid) sit in different panels of a deck tab and share one useTagEditor.

import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import Tooltip from "@mui/material/Tooltip";
import { motion } from "framer-motion";
import { memo, ReactNode, useCallback, useEffect, useId, useMemo, useState } from "react";
import { Category, CATEGORIES, CATEGORY_LABELS, TagKey } from "../api";
import { CardImage, Segmented } from "./common";

/** The theme colour for each tag */
const TAG_COLOR = { engine: "engine", non_engine: "nonEngine", brick: "brick" } as const;

/** Whether a key press is meant for a text field rather than a shortcut */
const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));

export interface TagEditor {
  deckList: string[];
  tags: Category[];
  tool: TagKey;
  setTool: (tool: TagKey) => void;
  allCopies: boolean;
  setAllCopies: (all: boolean) => void;
  untagged: number;
  count: (key: TagKey) => number;
  canUndo: boolean;
  undo: () => void;
  clearAll: () => void;
  tagRest: (tag: TagKey) => void;
  /** Tag a card (and its copies, if set) with the selected tag; "" untags */
  tagCard: (index: number, tag: Category) => void;
}

export function useTagEditor({ deckList, tags, onChange, shortcuts = true }: {
  deckList: string[];
  /** One tag per copy, in deck order */
  tags: Category[];
  onChange: (tags: Category[]) => void;
  /** Ctrl+Z undoes (off while another view is on top) */
  shortcuts?: boolean;
}): TagEditor {
  const [history, setHistory] = useState<Category[][]>([]);
  const [tool, setTool] = useState<TagKey>("engine");
  const [allCopies, setAllCopies] = useState(true);

  // A new deck starts a new history
  useEffect(() => { setHistory([]); }, [deckList]);

  const undo = useCallback(() => {
    if (!history.length) return;
    onChange(history[history.length - 1]);
    setHistory(history.slice(0, -1));
  }, [history, onChange]);

  useEffect(() => {
    if (!shortcuts) return;
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z" && !typing(e.target)) {
        e.preventDefault();
        undo();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo, shortcuts]);

  // The same object until something in it changes, so the memoised controls and grid only
  // re-render when the labels or the tool change (not when, say, the compare view opens)
  return useMemo(() => {
    const change = (next: Category[]) => {
      setHistory((h) => [...h, tags]);
      onChange(next);
    };
    const untagged = tags.filter((t) => !t).length;
    return {
      deckList, tags, tool, setTool, allCopies, setAllCopies, untagged,
      count: (key) => tags.filter((t) => t === key).length,
      canUndo: history.length > 0,
      undo,
      clearAll: () => { if (tags.some(Boolean)) change(tags.map(() => "" as Category)); },
      tagRest: (tag) => { if (untagged) change(tags.map((t) => t || tag)); },
      tagCard: (index, tag) => {
        // Clicking a card that already has the selected tag untags it
        if (tag && tags[index] === tag) tag = "";
        const indices = allCopies
          ? deckList.flatMap((name, i) => (name === deckList[index] ? [i] : []))
          : [index];
        if (indices.every((i) => tags[i] === tag)) return;
        const next = [...tags];
        for (const i of indices) next[i] = tag;
        change(next);
      },
    };
  }, [deckList, tags, tool, allCopies, history, undo, onChange]);
}

/** Totals, Undo / Clear all, the tag to apply and "mark the rest" */
export const TagControls = memo(function TagControls({ editor, actions }: { editor: TagEditor; actions?: ReactNode }) {
  const pillId = useId();
  const disabled = editor.deckList.length === 0;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap gap-1.5">
          {CATEGORIES.map((key) => (
            <Chip key={key} color={TAG_COLOR[key]} label={<>{CATEGORY_LABELS[key]} <b>{editor.count(key)}</b></>} />
          ))}
          <Chip label={<>Untagged <b>{editor.untagged}</b></>} />
        </div>
        <div className="flex flex-wrap gap-2">
          <Tooltip title="Undo (Ctrl+Z)">
            <span><Button color="inherit" size="small" onClick={editor.undo} disabled={!editor.canUndo}>Undo</Button></span>
          </Tooltip>
          <Button color="inherit" size="small" onClick={editor.clearAll} disabled={!editor.tags.some(Boolean)}>
            Clear all
          </Button>
          {actions}
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-muted">Click a card to tag it as</span>
          <Segmented value={editor.tool} onChange={editor.setTool} pillId={pillId} label="Tag to apply"
                     options={CATEGORIES.map((key) => ({ value: key, label: CATEGORY_LABELS[key], tone: key }))} />
          <FormControlLabel label="Label all copies" disabled={disabled}
                            control={<Checkbox checked={editor.allCopies} onChange={(e) => editor.setAllCopies(e.target.checked)} />} />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-muted">Mark the rest ({editor.untagged}) as</span>
          {CATEGORIES.map((key) => (
            <Button key={key} variant="outlined" size="small" color={TAG_COLOR[key]} disabled={!editor.untagged}
                    onClick={() => editor.tagRest(key)}>
              {CATEGORY_LABELS[key]}
            </Button>
          ))}
          <span className="text-xs text-muted">Click again or right-click to untag</span>
        </div>
      </div>
    </div>
  );
});

/** The deck's cards; click to tag, right-click to untag. `scroll` keeps them inside a fixed-height panel. */
export const TagGrid = memo(function TagGrid({ editor, idByName, scroll = false }: {
  editor: TagEditor;
  idByName: Record<string, string>;
  scroll?: boolean;
}) {
  // 10 cards per row (5 on phones, where 10 would be too small to click); tiles scale to the width
  return (
    <div className={`grid grid-cols-5 content-start gap-2 px-1 py-1.5 sm:grid-cols-10 ${scroll ? "min-h-0 flex-1 overflow-y-auto" : ""}`}>
      {editor.deckList.map((name, index) => {
        const tag = editor.tags[index];
        return (
          <motion.button key={index} type="button" className={`tag-tile ${tag ? `tagged tone-${tag}` : ""}`}
                         aria-label={`${name}, ${tag ? CATEGORY_LABELS[tag] : "unlabelled"}`}
                         title={name}
                         initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                         transition={{ delay: Math.min(index * 0.008, 0.3) }}
                         whileHover={{ y: -3 }} whileTap={{ scale: 0.96 }}
                         onClick={() => editor.tagCard(index, editor.tool)}
                         onContextMenu={(e) => { e.preventDefault(); editor.tagCard(index, ""); }}>
            <CardImage id={idByName[name]} name={name} />
            <span className="tile-tint" />
            {tag && <span className={`card-badge tile-badge tone-${tag}`}>{CATEGORY_LABELS[tag]}</span>}
          </motion.button>
        );
      })}
    </div>
  );
});
