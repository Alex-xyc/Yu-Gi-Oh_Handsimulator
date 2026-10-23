// Tag each card copy as engine / non-engine / brick by clicking it. The controls (TagControls)
// and the cards (TagGrid) sit in different panels of a deck tab and share one useTagEditor.
// In advanced mode the controls are a list of labels instead: the three above plus custom ones
// (customLabels.ts), which a copy can have on top of its engine / non-engine / brick label.
// The cards can be sorted (SortControls) or dragged into any order, one or several at a time;
// both share one useDeckOrder.

import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import Switch from "@mui/material/Switch";
import TextField from "@mui/material/TextField";
import Tooltip from "@mui/material/Tooltip";
import { motion } from "framer-motion";
import {
  type KeyboardEvent as ReactKeyboardEvent, memo, type MouseEvent as ReactMouseEvent, useCallback, useEffect, useMemo,
  useState,
} from "react";
import { type Category, CATEGORIES, CATEGORY_LABELS, type DeckCard, type TagKey } from "../api";
import { type CustomLabel, isCustom, labelSettings, MAX_LABEL_NAME, nameProblem } from "../customLabels";
import { type SortMode, sortedOrder } from "../deckSort";
import { CardImage, Segmented, SideIcon } from "./common";

/** The theme colour for each tag */
const TAG_COLOR = { engine: "engine", non_engine: "nonEngine", brick: "brick" } as const;

/** Whether a key press is meant for a text field rather than a shortcut */
const typing = (target: EventTarget | null) =>
  target instanceof HTMLElement && (target.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(target.tagName));

/** What a click on a card gives it: engine / non-engine / brick, or a custom label's id */
export type Tool = TagKey | string;

export interface TagEditor {
  deckList: string[];
  tags: Category[];
  /** One custom label id per copy ("" = none), only of labels that still exist */
  custom: string[];
  /** The custom labels, and whether advanced mode (where they're used) is on */
  labels: CustomLabel[];
  advanced: boolean;
  tool: Tool;
  setTool: (tool: Tool) => void;
  allCopies: boolean;
  setAllCopies: (all: boolean) => void;
  untagged: number;
  /** Copies with this label (engine / non-engine / brick or a custom one) */
  count: (key: Tool) => number;
  canUndo: boolean;
  undo: () => void;
  clearAll: () => void;
  tagRest: (tag: TagKey) => void;
  /** Give a card (and its copies, if set) the selected label; one it already has is taken off.
   *  "" takes off all its labels */
  tagCard: (index: number, tool: Tool | "") => void;
}

interface Labelling { tags: Category[]; custom: string[] }

export function useTagEditor({ deckList, tags, custom: savedCustom, labels, advanced, onChange, shortcuts = true }: {
  deckList: string[];
  /** One tag per copy, in deck order */
  tags: Category[];
  /** One custom label id per copy, in deck order (ids of removed labels count as none) */
  custom: string[];
  labels: CustomLabel[];
  advanced: boolean;
  onChange: (tags: Category[], custom: string[]) => void;
  /** Ctrl+Z undoes (off while another view is on top) */
  shortcuts?: boolean;
}): TagEditor {
  const [history, setHistory] = useState<Labelling[]>([]);
  const [chosen, setTool] = useState<Tool>("engine");
  const [allCopies, setAllCopies] = useState(true);
  const custom = useMemo(() => {
    const ids = new Set(labels.map((label) => label.id));
    return deckList.map((_, i) => (ids.has(savedCustom[i]) ? savedCustom[i] : ""));
  }, [deckList, savedCustom, labels]);
  // A custom label that's been removed, or advanced mode turned off, goes back to engine
  const tool = isCustom(chosen) && (!advanced || !labels.some((label) => label.id === chosen)) ? "engine" : chosen;

  // A new deck starts a new history
  // biome-ignore lint/correctness/useExhaustiveDependencies: cleared when another deck is loaded
  useEffect(() => { setHistory([]); }, [deckList]);

  const undo = useCallback(() => {
    if (!history.length) return;
    const last = history[history.length - 1];
    onChange(last.tags, last.custom);
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
    const change = (nextTags: Category[], nextCustom: string[]) => {
      setHistory((h) => [...h, { tags, custom }]);
      onChange(nextTags, nextCustom);
    };
    const untagged = tags.filter((t) => !t).length;
    return {
      deckList, tags, custom, labels, advanced, tool, setTool, allCopies, setAllCopies, untagged,
      count: (key) => (isCustom(key) ? custom : tags).filter((t) => t === key).length,
      canUndo: history.length > 0,
      undo,
      clearAll: () => {
        if (tags.some(Boolean) || custom.some(Boolean)) change(tags.map(() => "" as Category), custom.map(() => ""));
      },
      tagRest: (tag) => { if (untagged) change(tags.map((t) => t || tag), custom); },
      tagCard: (index, label) => {
        const indices = allCopies
          ? deckList.flatMap((name, i) => (name === deckList[index] ? [i] : []))
          : [index];
        const nextTags = [...tags];
        const nextCustom = [...custom];
        if (!label) {
          for (const i of indices) { nextTags[i] = ""; nextCustom[i] = ""; }
        } else if (isCustom(label)) {
          // Clicking a card that already has the selected label takes it off
          const value = custom[index] === label ? "" : label;
          for (const i of indices) nextCustom[i] = value;
        } else {
          const value = tags[index] === label ? "" : (label as TagKey);
          for (const i of indices) nextTags[i] = value;
        }
        if (indices.every((i) => nextTags[i] === tags[i] && nextCustom[i] === custom[i])) return;
        change(nextTags, nextCustom);
      },
    };
  }, [deckList, tags, custom, labels, advanced, tool, allCopies, history, undo, onChange]);
}

/** Undo / Clear all, for the tagging panel's header */
export const TagHistoryButtons = memo(function TagHistoryButtons({ editor }: { editor: TagEditor }) {
  return (
    <div className="flex flex-wrap gap-2">
      <Tooltip title="Undo (Ctrl+Z)">
        <span><Button color="inherit" size="small" onClick={editor.undo} disabled={!editor.canUndo}>Undo</Button></span>
      </Tooltip>
      <Button color="inherit" size="small" onClick={editor.clearAll}
              disabled={!editor.tags.some(Boolean) && !editor.custom.some(Boolean)}>
        Clear all
      </Button>
    </div>
  );
});

/** The switch between the normal controls and the advanced ones (only labels) */
function AdvancedSwitch({ advanced }: { advanced: boolean }) {
  return (
    <Tooltip title={advanced ? "Back to the normal labelling" : "Only labels: engine, non-engine, brick and your own"}>
      <FormControlLabel className="ml-auto mr-0" label="Advanced" labelPlacement="start"
                        control={<Switch size="small" checked={advanced}
                                         onChange={(e) => labelSettings.setAdvanced(e.target.checked)} />} />
    </Tooltip>
  );
}

/** A name for a label, typed in: Enter (or leaving the field) saves it, Escape cancels */
function LabelNameField({ initial = "", except, placeholder, onSave, onCancel, keepOpen = false }: {
  initial?: string;
  /** The label being renamed, whose own name doesn't count as taken */
  except?: string;
  placeholder: string;
  onSave: (name: string) => void;
  onCancel?: () => void;
  /** Stays (emptied) after saving, for adding several labels */
  keepOpen?: boolean;
}) {
  const [name, setName] = useState(initial);
  const [touched, setTouched] = useState(false);
  const problem = nameProblem(name, except);
  const save = () => {
    setTouched(true);
    if (problem) return;
    onSave(name);
    if (keepOpen) { setName(""); setTouched(false); }
  };
  const field = (
    <TextField size="small" value={name} placeholder={placeholder} autoFocus={!keepOpen}
               error={touched && !!problem && name !== ""} helperText={touched && name !== "" ? problem : undefined}
               slotProps={{ htmlInput: { maxLength: MAX_LABEL_NAME, "aria-label": placeholder } }}
               onChange={(e) => { setName(e.target.value); setTouched(false); }}
               onKeyDown={(e) => {
                 if (e.key === "Enter") { e.preventDefault(); save(); }
                 if (e.key === "Escape" && onCancel) { e.stopPropagation(); onCancel(); }
               }}
               onBlur={() => { if (!keepOpen) { if (!problem && name.trim() !== initial) onSave(name); else onCancel?.(); } }} />
  );
  if (!keepOpen) return field;
  return (
    <div className="flex items-start gap-2">
      {field}
      <Button variant="outlined" onClick={save} disabled={!name.trim()} className="shrink-0">Add label</Button>
    </div>
  );
}

/** One label in the advanced list: picks it as the label to give cards. A custom one can be
 *  renamed and removed. */
function LabelPill({ name, count, tone, color, selected, onSelect, label }: {
  name: string; count: number; tone: string; color?: string; selected: boolean; onSelect: () => void;
  /** A custom label (renamable, removable) */
  label?: CustomLabel;
}) {
  const [renaming, setRenaming] = useState(false);
  const style = color ? { ["--tone" as string]: color } : undefined;
  if (label && renaming) {
    return (
      <div className="label-pill editing" style={style}>
        <LabelNameField initial={label.name} except={label.id} placeholder="Label name"
                        onSave={(next) => { labelSettings.rename(label.id, next); setRenaming(false); }}
                        onCancel={() => setRenaming(false)} />
      </div>
    );
  }
  return (
    <div className={`label-pill tone-${tone} ${selected ? "selected" : ""}`} style={style}>
      <button type="button" className="label-pill-main" aria-pressed={selected} onClick={onSelect}
              onDoubleClick={label ? () => setRenaming(true) : undefined}>
        <i className="dot" aria-hidden="true" />
        <span className="label-pill-name">{name}</span>
        <b className="label-pill-count">{count}</b>
      </button>
      {label && (
        <>
          <Tooltip title="Rename">
            <IconButton size="small" className="label-pill-action" aria-label={`Rename ${label.name}`}
                        onClick={() => setRenaming(true)}>
              <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                <path d="M4 20h4L19 9l-4-4L4 16v4zM14 6l4 4" fill="none" stroke="currentColor" strokeWidth="2"
                      strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </IconButton>
          </Tooltip>
          <Tooltip title="Remove label">
            <IconButton size="small" className="label-pill-action" aria-label={`Remove ${label.name}`}
                        onClick={() => {
                          if (count && !window.confirm(`Remove the label "${label.name}"? ${count} card${count === 1 ? "" : "s"} in this deck ${count === 1 ? "has" : "have"} it.`)) return;
                          labelSettings.remove(label.id);
                        }}>
              <svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true">
                <path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
              </svg>
            </IconButton>
          </Tooltip>
        </>
      )}
    </div>
  );
}

/** Advanced mode: only the labels, engine / non-engine / brick and custom ones, and a field to
 *  add more. Picking one makes it the label clicking a card gives. */
function AdvancedControls({ editor }: { editor: TagEditor }) {
  const disabled = editor.deckList.length === 0;
  return (
    <div className="flex flex-col gap-2.5 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
      <span className="text-muted">Pick a label, then click cards to give it to them</span>
      <fieldset className="m-0 flex flex-wrap gap-2 border-0 p-0" aria-label="Labels">
        {CATEGORIES.map((key) => (
          <LabelPill key={key} name={CATEGORY_LABELS[key]} count={editor.count(key)} tone={key}
                     selected={editor.tool === key} onSelect={() => editor.setTool(key)} />
        ))}
        {editor.labels.map((label) => (
          <LabelPill key={label.id} label={label} name={label.name} count={editor.count(label.id)} tone="custom"
                     color={label.color} selected={editor.tool === label.id} onSelect={() => editor.setTool(label.id)} />
        ))}
      </fieldset>
      <LabelNameField keepOpen placeholder="New label, e.g. Starter"
                      onSave={(name) => { const label = labelSettings.add(name); if (label) editor.setTool(label.id); }} />
      {/* The switch on the right of "Label all copies" */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <FormControlLabel label="Label all copies" disabled={disabled}
                          control={<Checkbox checked={editor.allCopies} onChange={(e) => editor.setAllCopies(e.target.checked)} />} />
        <AdvancedSwitch advanced />
      </div>
      <span className="text-xs text-muted">
        A card can have a custom label as well as engine, non-engine or brick · right-click a card to take its labels off
      </span>
    </div>
  );
}

/** Totals, the tag to apply and "mark the rest"; in advanced mode, only the labels */
export const TagControls = memo(function TagControls({ editor }: { editor: TagEditor }) {
  const disabled = editor.deckList.length === 0;
  if (editor.advanced) return <AdvancedControls editor={editor} />;
  return (
    <div className="flex flex-col gap-2.5">
      <div className="tag-totals flex flex-wrap gap-1">
        {CATEGORIES.map((key) => (
          <Chip key={key} color={TAG_COLOR[key]} label={<>{CATEGORY_LABELS[key]} <b>{editor.count(key)}</b></>} />
        ))}
        <Chip label={<>Untagged <b>{editor.untagged}</b></>} />
      </div>

      <div className="flex flex-col gap-2 rounded-xl border border-line bg-surface-2 px-3 py-2.5">
        <div className="tag-tool flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className="text-muted">Click a card to tag it as</span>
          <Segmented value={isCustom(editor.tool) ? null : editor.tool as TagKey} onChange={editor.setTool} label="Tag to apply"
                     options={CATEGORIES.map((key) => ({ value: key, label: CATEGORY_LABELS[key], tone: key }))} />
          <FormControlLabel label="Label all copies" disabled={disabled}
                            control={<Checkbox checked={editor.allCopies} onChange={(e) => editor.setAllCopies(e.target.checked)} />} />
        </div>
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="text-muted">Mark the rest ({editor.untagged}) as:</span>
            <AdvancedSwitch advanced={false} />
          </div>
          <div className="grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            {CATEGORIES.map((key) => (
              <Button key={key} variant="outlined" size="small" color={TAG_COLOR[key]} disabled={!editor.untagged}
                      onClick={() => editor.tagRest(key)}>
                {CATEGORY_LABELS[key]}
              </Button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
});

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "name", label: "Name" },
  { value: "label", label: "Label" },
];

export interface DeckOrder {
  /** What the list is sorted by, or null once it's been rearranged since (or never sorted) */
  sortedBy: SortMode | null;
  sort: (mode: SortMode) => void;
  descending: boolean;
  toggleDirection: () => void;
  /** The deck positions (indices into deckList and tags) in the order shown */
  order: number[];
  /** Move cards (deck positions, kept in their shown order) next to the card at `target` */
  move: (cards: number[], target: number, after: boolean) => void;
}

/** The order the decklist is shown in (deck order to begin with). Sorting rearranges it once;
 *  after that it stays put: dragging cards, or relabelling a list sorted by label, only marks it
 *  as no longer sorted. Only the view changes, never the deck or its labels. */
export function useDeckOrder(cards: DeckCard[] | null, deckList: string[], tags: Category[]): DeckOrder {
  const [descending, setDescending] = useState(false);
  // Kept with the list it was made for, so a new deck starts in deck order
  const [state, setState] = useState<{
    list: string[]; order: number[]; sortedBy: SortMode | null; tagsAtSort: Category[];
  } | null>(null);
  const current = state?.list === deckList ? state : null;
  const order = useMemo(() => current?.order ?? deckList.map((_, i) => i), [current, deckList]);
  const sortedBy = current?.sortedBy === "label" && current.tagsAtSort !== tags ? null : current?.sortedBy ?? null;

  const apply = useCallback((mode: SortMode, desc: boolean) => {
    setState({ list: deckList, order: sortedOrder(mode, desc, cards, deckList, tags), sortedBy: mode, tagsAtSort: tags });
  }, [cards, deckList, tags]);

  const move = useCallback((moving: number[], target: number, after: boolean) => {
    const set = new Set(moving);
    if (set.has(target)) return;
    const next = order.filter((i) => !set.has(i));
    next.splice(next.indexOf(target) + (after ? 1 : 0), 0, ...order.filter((i) => set.has(i)));
    setState({ list: deckList, order: next, sortedBy: null, tagsAtSort: tags });
  }, [order, deckList, tags]);

  return useMemo(() => ({
    sortedBy, descending, order, move,
    sort: (mode: SortMode) => apply(mode, descending),
    toggleDirection: () => {
      setDescending(!descending);
      if (sortedBy) apply(sortedBy, !descending);
    },
  }), [sortedBy, descending, order, move, apply]);
}

/** Sort by name or label, and the ascending / descending toggle, for the panel header */
export const SortControls = memo(function SortControls({ deckOrder }: { deckOrder: DeckOrder }) {
  const { descending } = deckOrder;
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-xs text-muted">Sort by</span>
      <Segmented small value={deckOrder.sortedBy} onChange={deckOrder.sort} label="Sort the decklist by"
                 options={SORT_OPTIONS} />
      <Tooltip title={descending ? "Descending (click for ascending)" : "Ascending (click for descending)"}>
        <IconButton size="small" onClick={deckOrder.toggleDirection} aria-pressed={descending}
                    aria-label={descending ? "Descending order" : "Ascending order"}>
          <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"
               className={`transition-transform duration-200 ${descending ? "rotate-180" : ""}`}>
            <path d="M12 19V5M5 12l7-7 7 7" fill="none" stroke="currentColor" strokeWidth="2.2"
                  strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </IconButton>
      </Tooltip>
    </div>
  );
});

/** What's under the pointer while dragging: a plain card-shaped outline the size of `tile` (no
 *  art or name), with how many cards are moving when it's more than one */
function dragGhost(tile: HTMLElement, count: number): HTMLElement {
  const ghost = document.createElement("div");
  ghost.className = "drag-ghost";
  ghost.style.width = `${tile.offsetWidth}px`;
  ghost.style.height = `${tile.offsetHeight}px`;
  if (count > 1) {
    const badge = document.createElement("span");
    badge.className = "drag-count";
    badge.textContent = String(count);
    ghost.append(badge);
  }
  document.body.append(ghost);
  setTimeout(() => ghost.remove());
  return ghost;
}

/** The deck's cards in `order`. Click to tag, right-click to untag (all its labels); drag a card to move it.
 *  Shift- or Ctrl-click picks several cards (click one again to drop it, Esc to drop them all)
 *  and dragging any of them moves them together. There's deliberately no drag-a-box selection:
 *  a press-and-drag always moves cards. `scroll` keeps the cards inside a fixed-height panel. */
export const TagGrid = memo(function TagGrid({ editor, idByName, sided, order, onMove, scroll = false }: {
  editor: TagEditor;
  idByName: Record<string, string>;
  /** Per copy, in deck order: whether it was sided in (marked with a dot) */
  sided?: boolean[];
  /** Deck positions in the order shown */
  order: number[];
  onMove: (cards: number[], target: number, after: boolean) => void;
  scroll?: boolean;
}) {
  // The picked cards (deck positions), kept with the list they belong to
  const [picked, setPicked] = useState<{ list: string[]; cards: Set<number> }>({ list: editor.deckList, cards: new Set() });
  const selected = picked.list === editor.deckList ? picked.cards : new Set<number>();
  const select = (next: Set<number>) => setPicked({ list: editor.deckList, cards: next });
  const toggle = (index: number) => {
    const next = new Set(selected);
    if (!next.delete(index)) next.add(index);
    select(next);
  };
  const clear = () => { if (selected.size) select(new Set()); };

  // The cards being dragged, and where they'd land: before or after the card under the pointer
  const [dragging, setDragging] = useState<number[] | null>(null);
  const [over, setOver] = useState<{ index: number; after: boolean } | null>(null);
  const endDrag = () => { setDragging(null); setOver(null); };

  useEffect(() => {
    if (!selected.size) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !typing(e.target)) clear(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const click = (e: ReactMouseEvent | ReactKeyboardEvent, index: number) => {
    if (e.shiftKey || e.ctrlKey || e.metaKey) toggle(index);
    // A plain click on a picked card puts it back; on any other card it tags it
    else if (selected.has(index)) toggle(index);
    else editor.tagCard(index, editor.tool);
  };

  const dropTarget = over && dragging && !dragging.includes(over.index) ? over : null;
  const labelById = useMemo(() => new Map(editor.labels.map((label) => [label.id, label])), [editor.labels]);

  // 10 cards per row (5 on phones, where 10 would be too small to click); tiles scale to the width.
  // A plain div is dragged (native drag and drop; motion components take over the drag events),
  // inside a motion div that fades it in. Reordering is instant, not animated: with 40 cards
  // crossing over each other, quick clicks of the sort buttons left them in a jumble mid-flight.
  return (
    <>
      <div className="flex flex-wrap [@media(hover:hover)]:min-h-8 items-center gap-x-3 gap-y-1 px-1 pb-1.5 text-xs text-muted" aria-live="polite">
        {selected.size ? (
          <>
            <span className="selection-count">{selected.size} selected</span>
            <span>Drag one to move them all · click a card again to unselect it</span>
            <Button size="small" color="inherit" onClick={clear} className="ml-auto">Clear selection (Esc)</Button>
          </>
        ) : (
          <span className="mouse-hint">Drag a card to move it · <b className="font-semibold text-text">Shift+click</b> to select several and move them together</span>
        )}
        {sided?.some(Boolean) && (
          <span className={`flex items-center gap-1.5 ${selected.size ? "" : "ml-auto"}`}>
            <SideIcon inline />Sided in
          </span>
        )}
      </div>
      {/* biome-ignore lint/a11y/noStaticElementInteractions lint/a11y/useKeyWithClickEvents: mouse shortcuts for the space between cards (Escape also clears the selection, the sort buttons also order the cards) */}
      <div className={`grid select-none grid-cols-5 content-start gap-2 px-1.5 py-1.5 sm:grid-cols-10 ${scroll ? "min-h-0 flex-1 overflow-y-auto overscroll-contain" : ""}`}
           // A click on the space between cards drops the selection; dragging past the last card
           // puts the cards at the end
           onClick={(e) => { if (e.target === e.currentTarget) clear(); }}
           onDragOver={(e) => {
             if (!dragging || e.target !== e.currentTarget) return;
             e.preventDefault();
             // In a gap between cards the last marker stays; past the last card, it goes there
             const lastTile = e.currentTarget.lastElementChild?.getBoundingClientRect();
             const pastEnd = lastTile && (e.clientY > lastTile.bottom || (e.clientY >= lastTile.top && e.clientX > lastTile.right));
             const last = order[order.length - 1];
             if (pastEnd && (over?.index !== last || !over.after)) setOver({ index: last, after: true });
           }}
           onDrop={(e) => {
             e.preventDefault();
             if (dragging && dropTarget) onMove(dragging, dropTarget.index, dropTarget.after);
             endDrag();
           }}>
        {order.map((index, position) => {
          const name = editor.deckList[index];
          const tag = editor.tags[index];
          const custom = editor.advanced ? labelById.get(editor.custom[index]) : undefined;
          const isSelected = selected.has(index);
          const isSided = sided?.[index] ?? false;
          const drop = dropTarget?.index === index ? (dropTarget.after ? "drop-after" : "drop-before") : "";
          return (
            <motion.div key={index}
                        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(position * 0.008, 0.3) }}>
              {/* biome-ignore lint/a11y/useSemanticElements: a <button> can't be dragged in Firefox */}
              <div role="button" tabIndex={0} draggable aria-pressed={isSelected}
                   className={`tag-tile ${tag || custom ? `tagged tone-${tag || "custom"}` : ""} ${isSelected ? "selected" : ""} ${dragging?.includes(index) ? "dragging" : ""} ${drop}`}
                   // A card with only a custom label takes its colour
                   style={!tag && custom ? { ["--tone" as string]: custom.color } : undefined}
                   aria-label={`${name}, ${[tag && CATEGORY_LABELS[tag], custom?.name].filter(Boolean).join(" and ") || "unlabelled"}${isSided ? ", sided in" : ""}${isSelected ? ", selected" : ""}`}
                   // No name tooltip while dragging
                   title={dragging ? undefined : isSided ? `${name} (sided in)` : name}
                   // Shift-click would otherwise select the page's text
                   onMouseDown={(e) => { if (e.shiftKey) e.preventDefault(); }}
                   onClick={(e) => click(e, index)}
                   onKeyDown={(e) => {
                     if (e.key === "Enter" || e.key === " ") { e.preventDefault(); click(e, index); }
                   }}
                   onContextMenu={(e) => { e.preventDefault(); editor.tagCard(index, ""); }}
                   onDragStart={(e) => {
                     // A picked card takes the other picked cards along; any other card moves alone
                     const moving = isSelected ? order.filter((i) => selected.has(i)) : [index];
                     e.dataTransfer.effectAllowed = "move";
                     // Some data must be set for Firefox to start the drag; not the card names, so
                     // nothing gives away which card it is (e.g. dropped on a text field)
                     e.dataTransfer.setData("application/x-ygo-cards", String(moving.length));
                     const rect = e.currentTarget.getBoundingClientRect();
                     e.dataTransfer.setDragImage(dragGhost(e.currentTarget, moving.length), e.clientX - rect.left, e.clientY - rect.top);
                     setDragging(moving);
                   }}
                   onDragOver={(e) => {
                     if (!dragging) return;
                     e.preventDefault();
                     e.dataTransfer.dropEffect = "move";
                     const rect = e.currentTarget.getBoundingClientRect();
                     const after = e.clientX > rect.left + rect.width / 2;
                     if (over?.index !== index || over.after !== after) setOver({ index, after });
                   }}
                   onDrop={(e) => {
                     e.preventDefault();
                     e.stopPropagation();
                     if (dragging && dropTarget) onMove(dragging, dropTarget.index, dropTarget.after);
                     endDrag();
                   }}
                   onDragEnd={endDrag}>
                <CardImage id={idByName[name]} name={name} />
                <span className="tile-tint" />
                {tag && <span className={`card-badge tile-badge tone-${tag}`}>{CATEGORY_LABELS[tag]}</span>}
                {custom && (
                  <span className={`card-badge tile-badge custom-badge ${tag ? "stacked" : ""}`}
                        style={{ ["--tone" as string]: custom.color }}>{custom.name}</span>
                )}
                {isSided && <SideIcon />}
                {isSelected && (
                  <span className="tile-check" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true">
                      <path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" strokeWidth="3.2" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </span>
                )}
              </div>
            </motion.div>
          );
        })}
      </div>
    </>
  );
});
