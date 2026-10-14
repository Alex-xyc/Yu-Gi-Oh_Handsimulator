// Tag each card copy as engine / non-engine / brick by clicking it. The controls (TagControls)
// and the cards (TagGrid) sit in different panels of a deck tab and share one useTagEditor.
// The cards can be sorted (SortControls) or dragged into any order, one or several at a time;
// both share one useDeckOrder.

import Button from "@mui/material/Button";
import Checkbox from "@mui/material/Checkbox";
import Chip from "@mui/material/Chip";
import FormControlLabel from "@mui/material/FormControlLabel";
import IconButton from "@mui/material/IconButton";
import Tooltip from "@mui/material/Tooltip";
import { motion } from "framer-motion";
import {
  KeyboardEvent as ReactKeyboardEvent, memo, MouseEvent as ReactMouseEvent, ReactNode, useCallback, useEffect, useMemo,
  useState,
} from "react";
import { Category, CATEGORIES, CATEGORY_LABELS, DeckCard, TagKey } from "../api";
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
          <Segmented value={editor.tool} onChange={editor.setTool} label="Tag to apply"
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

export type SortMode = "name" | "label";

const SORT_OPTIONS: { value: SortMode; label: string }[] = [
  { value: "name", label: "Name" },
  { value: "label", label: "Label" },
];

/** Monsters, then spells, then traps, each by subtype; unknown cards last */
const KIND_ORDER = [
  "monster",
  "spell_normal", "spell_quick_play", "spell_continuous", "spell_field", "spell_equip", "spell_ritual",
  "trap_normal", "trap_continuous", "trap_counter",
];
const LABEL_ORDER: Record<Category, number> = { engine: 0, non_engine: 1, brick: 2, "": 3 };

/** Deck positions sorted by name within each card type (the arrow flips the names, not the
 *  types), or by label (the arrow flips the labels; unlabelled cards stay last), then type, then name */
function sortedOrder(mode: SortMode, descending: boolean, cards: DeckCard[] | null, deckList: string[], tags: Category[]) {
  const kinds = new Map((cards ?? []).map((card) => [card.name, card.kind ?? ""]));
  const kindRank = (i: number) => {
    const rank = KIND_ORDER.indexOf(kinds.get(deckList[i]) ?? "");
    return rank < 0 ? KIND_ORDER.length : rank;
  };
  const byName = (a: number, b: number) => deckList[a].localeCompare(deckList[b]) || a - b;
  const dir = descending ? -1 : 1;
  const unlabelled = (i: number) => (tags[i] ? 0 : 1);
  const compare = mode === "name"
    ? (a: number, b: number) => kindRank(a) - kindRank(b) || dir * byName(a, b)
    : (a: number, b: number) => unlabelled(a) - unlabelled(b) || dir * (LABEL_ORDER[tags[a]] - LABEL_ORDER[tags[b]])
      || kindRank(a) - kindRank(b) || byName(a, b);
  return deckList.map((_, i) => i).sort(compare);
}

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

/** The deck's cards in `order`. Click to tag, right-click to untag; drag a card to move it.
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

  // 10 cards per row (5 on phones, where 10 would be too small to click); tiles scale to the width.
  // A plain div is dragged (native drag and drop; motion components take over the drag events),
  // inside a motion div that fades it in. Reordering is instant, not animated: with 40 cards
  // crossing over each other, quick clicks of the sort buttons left them in a jumble mid-flight.
  return (
    <>
      <div className="flex min-h-8 flex-wrap items-center gap-x-3 gap-y-1 px-1 pb-1.5 text-xs text-muted" aria-live="polite">
        {selected.size ? (
          <>
            <span className="selection-count">{selected.size} selected</span>
            <span>Drag one to move them all · click a card again to unselect it</span>
            <Button size="small" color="inherit" onClick={clear} className="ml-auto">Clear selection (Esc)</Button>
          </>
        ) : (
          <span>Drag a card to move it · <b className="font-semibold text-text">Shift+click</b> to select several and move them together</span>
        )}
        {sided?.some(Boolean) && (
          <span className={`flex items-center gap-1.5 ${selected.size ? "" : "ml-auto"}`}>
            <i className="side-dot static" aria-hidden="true" />Sided in
          </span>
        )}
      </div>
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
          const isSelected = selected.has(index);
          const isSided = sided?.[index] ?? false;
          const drop = dropTarget?.index === index ? (dropTarget.after ? "drop-after" : "drop-before") : "";
          return (
            <motion.div key={index}
                        initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(position * 0.008, 0.3) }}>
              <div role="button" tabIndex={0} draggable aria-pressed={isSelected}
                   className={`tag-tile ${tag ? `tagged tone-${tag}` : ""} ${isSelected ? "selected" : ""} ${dragging?.includes(index) ? "dragging" : ""} ${drop}`}
                   aria-label={`${name}, ${tag ? CATEGORY_LABELS[tag] : "unlabelled"}${isSided ? ", sided in" : ""}${isSelected ? ", selected" : ""}`}
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
                {isSided && <i className="side-dot" aria-hidden="true" />}
                {isSelected && (
                  <span className="tile-check" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="12" height="12">
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
