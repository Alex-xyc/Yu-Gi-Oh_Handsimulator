// Two of the open deck tabs picked side by side and their opening-hand odds compared

import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import MenuItem from "@mui/material/MenuItem";
import Select from "@mui/material/Select";
import { motion } from "framer-motion";
import { CSSProperties, memo, ReactNode, useId, useState } from "react";
import { api, combinationOdds, Comparison, decimalsFor, DeckSetupBody, OddsPair, percent, percentWidth } from "../api";
import { exportComparison } from "../export";
import { DeckSetup } from "../useDeckSetup";
import { Bar, deckTone, Dot, SectionHeader, Segmented, Spinner, TruncatedName } from "./common";
import { DeckStatus } from "./DeckPanel";
import { DeckTab } from "./DeckTabs";
import { ExportButton } from "./ExportButton";

/** An open tab and its deck */
export interface CompareDeck extends DeckTab {
  setup: DeckSetup;
}

const HAND_SIZES = [
  { size: 5, label: "Going first" },
  { size: 6, label: "Going second" },
];

/** Whether more of a composition/average row is good (true), bad (false) or neither (null) */
const MORE_IS_BETTER: Record<string, boolean | null> = {
  "Deck size": false, "Engine": true, "Non-Engine": true, "Bricks": false, "Untagged": null,
};

/** The table name for each deck: its tab's name; never the same twice */
function deckNames(decks: [CompareDeck, CompareDeck]): [string, string] {
  const [a, b] = decks.map(({ name }) => {
    // The server takes names of up to 40 characters
    return name.length > 36 ? `${name.slice(0, 35).trimEnd()}…` : name;
  });
  return a === b ? [`${a} (1)`, `${b} (2)`] : [a, b];
}

/** Deck 2 minus deck 1; green when that favours deck 2, red when it favours deck 1. */
function Diff({ value, digits = 1, better = null }: { value: number; digits?: number; better?: 1 | 2 | null }) {
  if (Math.abs(value) <= 1e-10) return <span className="diff zero" aria-label="No difference">–</span>;
  const tone = better === 2 ? "good" : better === 1 ? "bad" : "";
  return <span className={`diff ${tone}`}>{diffText(value, digits)}</span>;
}

const diffText = (value: number, digits = 1) =>
  Math.abs(value) <= 1e-10 ? "–" : `${value > 0 ? "+" : ""}${value.toFixed(decimalsFor(value, digits))}`;

/** Which deck a difference favours, given whether more is better */
function favours(diff: number, moreIsBetter: boolean | null | undefined): 1 | 2 | null {
  if (moreIsBetter == null || diff === 0) return null;
  return (diff > 0) === moreIsBetter ? 2 : 1;
}

/** Widths (in characters) for the odds rows' number columns, from their longest value, so
 * every row's bars line up however many decimals a tiny chance needs */
function columnWidths(result: Comparison): CSSProperties {
  const rows = [...result.odds, ...result.at_least.flatMap((group) => group.rows), ...result.bricks];
  return {
    ["--value-ch" as string]: percentWidth(rows.flatMap((row) => [row.a, row.b])),
    ["--diff-ch" as string]: Math.max(0, ...rows.map((row) => diffText((row.b - row.a) * 100).length)),
  };
}

/** Probabilities for both decks as paired bars, with the difference and the better deck */
function OddsRows({ rows, names }: { rows: OddsPair[]; names: [string, string] }) {
  return (
    <div className="compare-odds">
      {rows.map((row) => (
        <div key={row.label} className="compare-odds-row">
          <span className="label">{row.label}</span>
          <div className="dual-bars">
            {[row.a, row.b].map((value, side) => (
              <div key={side} className={`dual ${row.better === side + 1 ? "better" : ""}`}>
                <Bar value={value} tone={deckTone(side)} />
                <span className="mono"><span className="sr-only">{names[side]}: </span>{percent(value)}</span>
              </div>
            ))}
          </div>
          <Diff value={(row.b - row.a) * 100} better={row.better} />
          <span className="better-tag" title={row.better ? names[row.better - 1] : undefined}>
            {row.better && (
              <><Dot tone={deckTone(row.better - 1)} /><span className="sr-only">Better: </span>{names[row.better - 1]}</>
            )}
          </span>
        </div>
      ))}
    </div>
  );
}

interface TableRow {
  key: string;
  /** The row's first cell: a <th scope="row"> */
  label: ReactNode;
  a: ReactNode;
  b: ReactNode;
  diff: ReactNode;
  className?: string;
}

/** One value per deck in each row (composition, averages, card odds), and the difference */
function CompareTable({ names, rows, firstHeader }: {
  names: [string, string];
  rows: TableRow[];
  /** The first column's heading; when not given it's only read out by screen readers */
  firstHeader?: string;
}) {
  return (
    <table className="data-table compare-table">
      <thead>
        <tr>
          <th scope="col">{firstHeader ?? <span className="sr-only">Statistic</span>}</th>
          {names.map((name) => <th key={name} scope="col"><TruncatedName>{name}</TruncatedName></th>)}
          <th scope="col">Diff</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row.key} className={row.className}>
            {row.label}<td className="mono">{row.a}</td><td className="mono">{row.b}</td><td>{row.diff}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

const rowHeader = (text: string, className = "") =>
  <th scope="row" className={`text-left font-normal ${className}`}>{text}</th>;

/** Rows of whole numbers or decimals, the difference coloured by which deck it favours */
const valueRows = (rows: { label: string; a: number; b: number }[], digits: number): TableRow[] =>
  rows.map((row) => ({
    key: row.label, label: rowHeader(row.label), a: row.a.toFixed(digits), b: row.b.toFixed(digits),
    diff: <Diff value={row.b - row.a} digits={digits} better={favours(row.b - row.a, MORE_IS_BETTER[row.label])} />,
  }));

function Results({ result, onExport, onError }: {
  result: Comparison;
  onExport: () => Promise<void>;
  onError: (message: string) => void;
}) {
  const [a, b] = result.names;
  const turn = result.hand_size === 5 ? "going first" : "going second";
  return (
    <motion.div className="compare-results" key={JSON.stringify(result.names) + result.hand_size}
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} style={columnWidths(result)}>
      <div className="compare-legend">
        {result.names.map((name, side) => (
          <Chip key={side} color={side ? "deckB" : "deckA"} icon={<Dot tone={deckTone(side)} />}
                label={<TruncatedName>{name}</TruncatedName>} />
        ))}
        <span className="muted small">
          Diff = {b} − {a} (percentage points for odds) · <span className="ok">green</span> favours {b},{" "}
          <span className="error">red</span> favours {a} · card odds: green when higher in {b}
        </span>
      </div>

      <section className="stats-section">
        <SectionHeader title="Composition" action={<ExportButton onExport={onExport} onError={onError} />} />
        <CompareTable names={result.names} rows={valueRows(result.composition, 0)} />
      </section>

      <section className="stats-section">
        <SectionHeader title="Opening hand" hint={`(${turn})`} />
        <OddsRows rows={combinationOdds(result)} names={result.names} />
      </section>

      <section className="stats-section">
        <SectionHeader title="Chance of drawing X or more" hint={`(${turn})`} />
        <div className="compare-groups">
          {result.at_least.map((group) => (
            <div key={group.key}>
              <h4 className="compare-group-title"><Dot tone={group.key} />{group.label}</h4>
              <OddsRows rows={group.rows} names={result.names} />
            </div>
          ))}
        </div>
      </section>

      <section className="stats-section">
        <SectionHeader title="Bricks" hint={`(${turn})`} />
        <OddsRows rows={result.bricks} names={result.names} />
      </section>

      <section className="stats-section">
        <SectionHeader title="Average per hand" hint={`(${turn})`} />
        <CompareTable names={result.names} rows={valueRows(result.averages, 2)} />
      </section>

      <section className="stats-section">
        <SectionHeader title="Card odds" hint={`(at least 1 copy, ${turn}, changed cards first)`} />
        <CompareTable names={result.names} firstHeader="Card" rows={result.cards.map((card) => ({
          key: card.name, className: card.changed ? "changed" : "", label: rowHeader(card.name, "card-name"),
          a: card.a_copies ? `${card.a_copies}× ${percent(card.a)}` : "–",
          b: card.b_copies ? `${card.b_copies}× ${percent(card.b)}` : "–",
          diff: <Diff value={(card.b - card.a) * 100} better={favours(card.b - card.a, true)} />,
        }))} />
      </section>
    </motion.div>
  );
}

export const CompareView = memo(function CompareView({ decks, onClose, onError }: {
  /** The open tabs, in tab order */
  decks: CompareDeck[];
  onClose: () => void;
  onError: (message: string) => void;
}) {
  const [picked, setPicked] = useState<[number, number]>([0, 1]);
  const [handSize, setHandSize] = useState(5);
  const [result, setResult] = useState<Comparison | null>(null);
  /** The decks as they were when the result was calculated (the export recalculates from them) */
  const [resultBodies, setResultBodies] = useState<[DeckSetupBody, DeckSetupBody] | null>(null);
  const [busy, setBusy] = useState(false);
  const id = useId();

  // A picked tab that has since been closed falls back to the first open tab not on the other side
  const bySlot = (slot: number) => decks.find((deck) => deck.slot === slot);
  const a = bySlot(picked[0]) ?? decks[0];
  const b = (picked[1] !== a.slot && bySlot(picked[1])) || decks.find((deck) => deck.slot !== a.slot);
  const chosen: [CompareDeck, CompareDeck] | null = b ? [a, b] : null;
  const names = chosen && deckNames(chosen);

  /** Picking the deck that's already on the other side swaps the two */
  const pick = (side: number, slot: number) => {
    if (!chosen) return;
    const next: [number, number] = [chosen[0].slot, chosen[1].slot];
    if (next[1 - side] === slot) next[1 - side] = next[side];
    next[side] = slot;
    setPicked(next);
  };

  const compare = async (size = handSize) => {
    if (!chosen || !names) return onError("Open a second deck tab to compare.");
    const bodies = chosen.map((deck, i) => deck.setup.body(names[i]));
    for (const i of [0, 1] as const) {
      if (!bodies[i]) return onError(`${names[i]}: No deck loaded.`);
    }
    setBusy(true);
    try {
      const pair: [DeckSetupBody, DeckSetupBody] = [bodies[0]!, bodies[1]!];
      setResult(await api.compare(pair, size));
      setResultBodies(pair);
    } catch (e) {
      onError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setBusy(false);
    }
  };

  /** Both hand sizes in one file: the one on screen, and the other fetched for the same decks */
  const exportBoth = async () => {
    if (!result || !resultBodies) return;
    const other = await api.compare(resultBodies, result.hand_size === 5 ? 6 : 5);
    await exportComparison(result.hand_size === 5 ? [result, other] : [other, result]);
  };

  const changeHandSize = (size: number) => {
    setHandSize(size);
    if (result) compare(size);
  };

  return (
    <div className="compare-view">
      <div className="overlay-header">
        <h2 id={`${id}-title`}>Compare decks</h2>
        <Button color="inherit" onClick={onClose}>Close</Button>
      </div>

      {chosen ? (
        <div className="compare-picks">
          {chosen.map((deck, side) => (
            <div key={side} className="card-panel compare-pick">
              <span className="compare-pick-label" id={`${id}-pick-${side}`}>
                <Dot tone={deckTone(side)} />{side ? "Deck B" : "Deck A"}
              </span>
              <Select labelId={`${id}-pick-${side}`} fullWidth value={deck.slot} className="compare-select"
                      onChange={(e) => pick(side, Number(e.target.value))}>
                {decks.map((option) => (
                  <MenuItem key={option.slot} value={option.slot} className="compare-option">
                    <span className="truncate-name">{option.name}</span>
                    {option.size !== null && <span className="muted small deck-count">· {option.size} cards</span>}
                  </MenuItem>
                ))}
              </Select>
              <DeckStatus setup={deck.setup} />
            </div>
          ))}
        </div>
      ) : (
        <p className="card-panel muted center m-0">
          Only one deck is open. Open another with the <b>+</b> next to the deck tabs, then pick the two to compare here.
        </p>
      )}

      <div className="compare-actions">
        <Segmented value={handSize} onChange={changeHandSize} label="Hand size"
                   options={HAND_SIZES.map(({ size, label }) => ({ value: size, label }))} />
        <Button variant="contained" size="large" onClick={() => compare()} disabled={busy || !chosen} className="compare-button">
          {busy ? <Spinner /> : "Calculate & Compare"}
        </Button>
      </div>

      {/* A short status for screen readers when a comparison finishes (not the whole result) */}
      <p className="sr-only" role="status">
        {busy ? "Calculating…" : result ? `Compared ${result.names[0]} and ${result.names[1]}, ${result.hand_size === 5 ? "going first" : "going second"}.` : ""}
      </p>
      {result ? <Results result={result} onExport={exportBoth} onError={onError} /> : (
        <p className="muted center">Pick two of your open decks, then calculate. Labels are set in each deck's tab.</p>
      )}
    </div>
  );
});
