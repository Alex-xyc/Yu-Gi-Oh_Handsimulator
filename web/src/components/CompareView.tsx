// Two decks set up side by side (tabs) and their opening-hand odds compared

import Button from "@mui/material/Button";
import Chip from "@mui/material/Chip";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Tooltip from "@mui/material/Tooltip";
import { motion } from "framer-motion";
import { memo, useState } from "react";
import { api, Comparison, percent } from "../api";
import { DeckSetup } from "../useDeckSetup";
import { Bar, Segmented, Spinner } from "./common";
import { CategoryControls, DeckLoader } from "./DeckPanel";

const DEFAULT_NAMES = ["Deck 1", "Deck 2"] as const;
const HAND_SIZES = [
  { size: 5, label: "Going first" },
  { size: 6, label: "Going second" },
];

/** Whether more of a composition/average row is good (true), bad (false) or neither (null) */
const MORE_IS_BETTER: Record<string, boolean | null> = {
  "Deck size": false, "Engine": true, "Non-Engine": true, "Bricks": false, "Untagged": null,
};

/** The tab/table name for each deck: its file name, else "Deck 1"/"Deck 2"; never the same twice */
function deckNames(setups: [DeckSetup, DeckSetup]): [string, string] {
  const [a, b] = setups.map((setup, i) => {
    const name = setup.name ?? DEFAULT_NAMES[i];
    // The server takes names of up to 40 characters
    return name.length > 36 ? `${name.slice(0, 35).trimEnd()}…` : name;
  });
  return a === b ? [`${a} (1)`, `${b} (2)`] : [a, b];
}

/** Deck 2 minus deck 1; green when that favours deck 2, red when it favours deck 1. */
function Diff({ value, digits = 1, better = null }: { value: number; digits?: number; better?: 1 | 2 | null }) {
  if (Math.abs(value) < 0.5 * 10 ** -digits) return <span className="diff zero">–</span>;
  const tone = better === 2 ? "good" : better === 1 ? "bad" : "";
  return <span className={`diff ${tone}`}>{value > 0 ? "+" : ""}{value.toFixed(digits)}</span>;
}

/** Which deck a difference favours, given whether more is better */
function favours(diff: number, moreIsBetter: boolean | null | undefined): 1 | 2 | null {
  if (moreIsBetter == null || diff === 0) return null;
  return (diff > 0) === moreIsBetter ? 2 : 1;
}

/** A deck name that shortens with an ellipsis when it doesn't fit; hover shows it in full */
function Name({ children }: { children: string }) {
  return <Tooltip title={children}><span className="deck-name">{children}</span></Tooltip>;
}

function Results({ result }: { result: Comparison }) {
  const [a, b] = result.names;
  return (
    <motion.div className="compare-results" key={JSON.stringify(result.names) + result.hand_size}
                initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
      <div className="compare-legend">
        <Chip color="deckA" icon={<i className="dot deck-a" />} label={<Name>{a}</Name>} />
        <Chip color="deckB" icon={<i className="dot deck-b" />} label={<Name>{b}</Name>} />
        <span className="muted small">
          Diff = {b} − {a} (percentage points for odds) · <span className="ok">green</span> favours {b},{" "}
          <span className="error">red</span> favours {a} · card odds: green when higher in {b}
        </span>
      </div>

      <section className="stats-section">
        <h3>Composition</h3>
        <table className="compare-table">
          <thead><tr><th /><th><Name>{a}</Name></th><th><Name>{b}</Name></th><th>Diff</th></tr></thead>
          <tbody>
            {result.composition.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td><td className="mono">{row.a}</td><td className="mono">{row.b}</td>
                <td><Diff value={row.b - row.a} digits={0} better={favours(row.b - row.a, MORE_IS_BETTER[row.label])} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="stats-section">
        <h3>Opening hand <span className="muted small">({result.hand_size === 5 ? "going first" : "going second"})</span></h3>
        <div className="compare-odds">
          {result.odds.map((row) => (
            <div key={row.label} className="compare-odds-row">
              <span className="label">{row.label}</span>
              <div className="dual-bars">
                <div className={`dual ${row.better === 1 ? "better" : ""}`}>
                  <Bar value={row.a} tone="deck-a" /><span className="mono">{percent(row.a)}</span>
                </div>
                <div className={`dual ${row.better === 2 ? "better" : ""}`}>
                  <Bar value={row.b} tone="deck-b" /><span className="mono">{percent(row.b)}</span>
                </div>
              </div>
              <Diff value={(row.b - row.a) * 100} better={row.better} />
              <span className={`better-tag ${row.better === 1 ? "deck-a" : row.better === 2 ? "deck-b" : ""}`}
                    title={row.better ? result.names[row.better - 1] : undefined}>
                {row.better && <><i className={`dot ${row.better === 1 ? "deck-a" : "deck-b"}`} />{result.names[row.better - 1]}</>}
              </span>
            </div>
          ))}
        </div>
      </section>

      <section className="stats-section">
        <h3>Average per hand</h3>
        <table className="compare-table">
          <thead><tr><th /><th><Name>{a}</Name></th><th><Name>{b}</Name></th><th>Diff</th></tr></thead>
          <tbody>
            {result.averages.map((row) => (
              <tr key={row.label}>
                <td>{row.label}</td><td className="mono">{row.a.toFixed(2)}</td><td className="mono">{row.b.toFixed(2)}</td>
                <td><Diff value={row.b - row.a} digits={2} better={favours(row.b - row.a, MORE_IS_BETTER[row.label])} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="stats-section">
        <h3>Card odds <span className="muted small">(at least 1 copy, changed cards first)</span></h3>
        <table className="compare-table cards">
          <thead><tr><th>Card</th><th><Name>{a}</Name></th><th><Name>{b}</Name></th><th>Diff</th></tr></thead>
          <tbody>
            {result.cards.map((card) => (
              <tr key={card.name} className={card.changed ? "changed" : ""}>
                <td className="card-name">{card.name}</td>
                <td className="mono">{card.a_copies ? `${card.a_copies}× ${percent(card.a)}` : "–"}</td>
                <td className="mono">{card.b_copies ? `${card.b_copies}× ${percent(card.b)}` : "–"}</td>
                <td><Diff value={(card.b - card.a) * 100} better={favours(card.b - card.a, true)} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </motion.div>
  );
}

export const CompareView = memo(function CompareView({ setups, onClose, onTag, onError }: {
  setups: [DeckSetup, DeckSetup];
  onClose: () => void;
  onTag: (index: 0 | 1) => void;
  onError: (message: string) => void;
}) {
  const [tab, setTab] = useState<0 | 1>(0);
  const [handSize, setHandSize] = useState(5);
  const [result, setResult] = useState<Comparison | null>(null);
  const [busy, setBusy] = useState(false);

  const names = deckNames(setups);

  const compare = async (size = handSize) => {
    const bodies = setups.map((setup, i) => setup.body(names[i]));
    for (const i of [0, 1] as const) {
      if (!bodies[i]) {
        setTab(i);
        return onError(`${names[i]}: No deck loaded.`);
      }
    }
    setBusy(true);
    try {
      setResult(await api.compare([bodies[0]!, bodies[1]!], size));
    } catch (e) {
      onError(e instanceof Error ? e.message : "Comparison failed.");
    } finally {
      setBusy(false);
    }
  };

  const changeHandSize = (size: number) => {
    setHandSize(size);
    if (result) compare(size);
  };

  const setup = setups[tab];

  return (
    <div className="compare-view">
      <header className="overlay-header">
        <h2>Compare decks</h2>
        <Button color="inherit" onClick={onClose}>Close</Button>
      </header>

      {/* The underline takes the colour of the selected deck */}
      <Tabs value={tab} onChange={(_, next: 0 | 1) => setTab(next)} className="tabs" aria-label="Decks"
            sx={{ "& .MuiTabs-indicator": { bgcolor: tab ? "deckB.main" : "deckA.main" } }}>
        {names.map((name, i) => (
          <Tab key={i} value={i} className="tab" label={
            <span className="tab-label">
              <i className={`dot ${i ? "deck-b" : "deck-a"}`} />
              <Tooltip title={name}>
                <motion.span key={name} className="tab-name"
                             initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }}>{name}</motion.span>
              </Tooltip>
              {setups[i].cards && <span className="muted small tab-size">· {setups[i].size} cards</span>}
            </span>
          } />
        ))}
      </Tabs>

      {/* The panel swaps in place (same size for both decks), so nothing below it moves */}
      <div className="card-panel">
        <motion.div key={tab} className="tab-content"
                    initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.18 }}>
          <DeckLoader setup={setup} onError={onError} />
          <CategoryControls setup={setup} onShowDecklist={() => onTag(tab)} />
        </motion.div>
      </div>

      <div className="compare-actions">
        <Segmented value={handSize} onChange={changeHandSize} pillId="hand-pill" label="Hand size"
                   options={HAND_SIZES.map(({ size, label }) => ({ value: size, label }))} />
        <Button variant="contained" size="large" onClick={() => compare()} disabled={busy} sx={{ minWidth: 200 }}>
          {busy ? <Spinner /> : "Calculate & Compare"}
        </Button>
      </div>

      {result ? <Results result={result} /> : (
        <p className="muted center">Load both decks and label their cards, then calculate.</p>
      )}
    </div>
  );
});
