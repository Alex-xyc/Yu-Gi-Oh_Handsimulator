// Opening-hand probabilities & statistics

import { motion } from "framer-motion";
import { memo } from "react";
import { CardOdds, CATEGORY_LABELS, percent, percentWidth, shownCategories, Stats } from "../api";
import { AnimatedPercent, Bar, Dot, SectionHeader, StatTile } from "./common";

const GROUPS: { key: CardOdds["group"]; title: string }[] = [
  { key: "engine", title: "Engine" },
  { key: "requirement", title: "Engine Req." },
  { key: "non_engine", title: "Non-Engine" },
  { key: "brick", title: "Brick" },
  { key: "mixed", title: "Mixed tags" },
  { key: "untagged", title: "Untagged" },
];

/** Axes with a wavy line climbing to an arrowhead; the line draws itself in. */
function ChartIcon() {
  const draw = (delay: number) => ({
    initial: { pathLength: 0, opacity: 0 },
    animate: { pathLength: 1, opacity: 1 },
    transition: { pathLength: { delay, duration: 0.9, ease: "easeInOut" as const }, opacity: { delay, duration: 0.01 } },
  });
  return (
    <svg className="chart-icon" viewBox="0 0 120 84" fill="none" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <defs>
        <linearGradient id="chart-line" x1="0" y1="1" x2="1" y2="0">
          <stop offset="0" stopColor="var(--color-accent)" />
          <stop offset="1" stopColor="var(--color-deck-b)" />
        </linearGradient>
      </defs>
      <motion.path d="M 10 6 V 74 H 112" stroke="var(--color-muted)" strokeOpacity="0.55" strokeWidth="4" {...draw(0)} />
      <motion.path d="M 22 62 C 26 46, 30 42, 34 52 S 42 62, 48 50 S 58 38, 64 48 S 78 52, 98 18"
                   stroke="url(#chart-line)" strokeWidth="5" {...draw(0.35)} />
      <motion.path d="M 84 16 L 99 16 L 99 31" stroke="var(--color-deck-b)" strokeWidth="5" {...draw(1.1)} />
    </svg>
  );
}

/** n choose k */
function choose(n: number, k: number) {
  if (k < 0 || k > n) return 0;
  let result = 1;
  for (let i = 1; i <= k; i++) result = (result * (n - k + i)) / i;
  return result;
}

/** Chance of at least `wanted` of `copies` cards in the first `cards` of a `deckSize` deck */
function atLeast(deckSize: number, copies: number, cards: number, wanted: number) {
  let p = 0;
  for (let x = wanted; x <= Math.min(copies, cards); x++) {
    p += (choose(copies, x) * choose(deckSize - copies, cards - x)) / choose(deckSize, cards);
  }
  return p;
}

/** A card with copies sided in: its copies in the deck, and how many of them were sided in */
export interface SidedCard {
  name: string;
  copies: number;
  sided: number;
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <motion.section className="stats-section" layout="position">
      <SectionHeader title={title} hint={hint} />
      {children}
    </motion.section>
  );
}

export const StatsView = memo(function StatsView({ stats, tagged, hasHand, sidedCards = [], sidedInHand = null }: {
  stats: Stats | null; tagged: boolean; hasHand: boolean;
  /** The cards with copies sided in (their odds are shown when there are any) */
  sidedCards?: SidedCard[];
  /** How many of the drawn hand's cards were sided in; null with no hand */
  sidedInHand?: number | null;
}) {
  if (!stats) {
    return (
      <div className="stats-empty">
        <ChartIcon />
        <p className="muted">Statistics appear here once a deck is loaded.</p>
      </div>
    );
  }
  const maxCell = Math.max(...stats.matrix.flat().map((p) => p ?? 0), 0.0001);
  // The value column fits the longest number, so every row's bar lines up
  const categories = shownCategories(stats.counts);
  const valueWidth = percentWidth(categories.flatMap((key) => stats.at_least[key]));
  const grouped = tagged;

  // Opening at least 1 .. 5 of the cards sided in, going first and second
  const sidedIn = sidedCards.reduce((total, card) => total + card.sided, 0);
  const sideOdds = Array.from({ length: Math.min(5, sidedIn) }, (_, i) => ({
    first: atLeast(stats.deck_size, sidedIn, stats.hand_size, i + 1),
    second: atLeast(stats.deck_size, sidedIn, stats.hand_size + 1, i + 1),
  }));
  // The 6th card being one of the sided-in cards still in the deck, after the current hand
  const deckRemaining = stats.deck_size - stats.hand_size;
  const sideSixth = sidedIn > 0 && sidedInHand !== null && deckRemaining > 0
    ? { remaining: sidedIn - sidedInHand, probability: (sidedIn - sidedInHand) / deckRemaining } : null;
  const sideWidth = percentWidth(sideOdds.flatMap(({ first, second }) => [first, second]));

  return (
    <div className="stats">
      <div className="stat-tiles">
        <StatTile value={stats.deck_size} label="cards" />
        {categories.map((key) => <StatTile key={key} value={stats.counts[key]} label={CATEGORY_LABELS[key]} tone={key} />)}
        {stats.counts.untagged > 0 && <StatTile value={stats.counts.untagged} label="Untagged" />}
      </div>

      <Section title="Opening hand" hint="(chance of drawing X or more)">
        <div className="odds-groups" style={{ ["--value-ch" as string]: valueWidth }}>
          {categories.map((key) => (
            <div key={key} className="odds-rows">
              {stats.at_least[key].map((p, i) => (
                <div key={i} className="odds-row">
                  <span>At least {i + 1} {CATEGORY_LABELS[key].toLowerCase()}{key === "brick" && i ? "s" : ""}</span>
                  <Bar value={p} tone={key} />
                  <span className="mono value"><AnimatedPercent value={p} /></span>
                </div>
              ))}
            </div>
          ))}
        </div>
      </Section>

      <Section title="Engine × Non-Engine" hint="(exact counts in hand)">
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">Engine drawn</span></th>
                {stats.matrix[0].map((_, ne) => <th key={ne} scope="col"><abbr title={`${ne} non-engine`}>{ne} NE</abbr></th>)}
              </tr>
            </thead>
            <tbody>
              {stats.matrix.map((row, e) => (
                <tr key={e}>
                  <th scope="row"><abbr title={`${e} engine`}>{e} E</abbr></th>
                  {row.map((p, ne) => (
                    <td key={ne} className="mono"
                        style={{ ["--heat" as string]: p ? String(0.08 + 0.72 * (p / maxCell)) : "0" }}>
                      {p && p > 1e-12 ? percent(p) : "–"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Bricks">
        <div className="stat-tiles">
          <StatTile wide value={<AnimatedPercent value={stats.bricks.open} />} label="Open with a brick" />
          <StatTile wide value={<AnimatedPercent value={stats.bricks.draw_sixth} />} label="Draw one 6th" />
          <StatTile wide value={<AnimatedPercent value={stats.bricks.by_turn_one} />} label="See one by turn 1" />
        </div>
      </Section>

      {sidedIn > 0 && (
        <Section title="Side deck cards" hint={`(${sidedIn} sided in · chance of drawing X or more)`}>
          {/* At least 1 up to 5 of them (no more than there are), going first (with a bar) and second */}
          <div className="odds-rows" style={{ ["--value-ch" as string]: sideWidth }}>
            <div className="odds-row two-values small muted" aria-hidden="true">
              <span />{/* Where the bar is; on phones the bar has its own line */}<span className="max-[700px]:hidden" /><span className="value">First</span><span className="value">Second</span>
            </div>
            {sideOdds.map(({ first, second }, i) => (
              <div key={i} className="odds-row two-values">
                <span>At least {i + 1} side deck card{i ? "s" : ""}</span>
                <Bar value={first} tone="side" />
                <span className="mono value" aria-label={`Going first ${percent(first)}`}><AnimatedPercent value={first} /></span>
                <span className="mono value muted" aria-label={`Going second ${percent(second)}`}><AnimatedPercent value={second} /></span>
              </div>
            ))}
          </div>
          <table className="data-table mt-4">
            <thead>
              <tr><th scope="col">Qty</th><th scope="col">Going first</th><th scope="col">Going second</th><th scope="col">Card</th></tr>
            </thead>
            <tbody>
              {sidedCards.map((card) => (
                <tr key={card.name}>
                  <td className="mono">{card.copies}×</td>
                  <td className="mono">{percent(atLeast(stats.deck_size, card.copies, stats.hand_size, 1))}</td>
                  <td className="mono">{percent(atLeast(stats.deck_size, card.copies, stats.hand_size + 1, 1))}</td>
                  <td className="card-name">
                    <i className="side-dot static mr-2 align-middle" aria-hidden="true" />{card.name}
                    {card.sided < card.copies && <span className="muted small"> · {card.sided} of {card.copies} sided in</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      <Section title="6th card" hint="(based on the current hand)">
        {(stats.sixth_card || sideSixth) && (
          <div className="odds-rows">
            {stats.sixth_card && categories.map((key) => (
              <div key={key} className="odds-row">
                <span>{CATEGORY_LABELS[key]} <span className="muted small">({stats.sixth_card![key].remaining}/{stats.sixth_card!.deck_remaining})</span></span>
                <Bar value={stats.sixth_card![key].probability} tone={key} />
                <span className="mono value"><AnimatedPercent value={stats.sixth_card![key].probability} /></span>
              </div>
            ))}
            {/* Shown without labels too: which cards were sided in is known either way */}
            {sideSixth && (
              <div className="odds-row">
                <span className="flex items-center">
                  <i className="side-dot static mr-2" aria-hidden="true" />Side deck card
                  <span className="muted small ml-1">({sideSixth.remaining}/{deckRemaining})</span>
                </span>
                <Bar value={sideSixth.probability} tone="side" />
                <span className="mono value"><AnimatedPercent value={sideSixth.probability} /></span>
              </div>
            )}
          </div>
        )}
        {!stats.sixth_card && (
          <p className={`muted small ${sideSixth ? "mt-2 mb-0" : ""}`}>
            {!hasHand ? "Draw a hand to see these." :
              `Label your cards in the decklist to see ${sideSixth ? "the label odds" : "these"}.`}
          </p>
        )}
      </Section>

      <Section title="Card odds" hint="(at least 1 copy)">
        <table className="data-table">
          <thead>
            <tr><th scope="col">Qty</th><th scope="col">Going first</th><th scope="col">Going second</th><th scope="col">Card</th></tr>
          </thead>
          {GROUPS.map(({ key, title }) => {
            const cards = stats.cards.filter((c) => c.group === key);
            if (!cards.length) return null;
            return (
              <tbody key={key}>
                {grouped && <tr className="group-row"><td colSpan={4}><Dot tone={key} />{title}</td></tr>}
                {cards.map((card) => (
                  <tr key={card.name}>
                    <td className="mono">{card.copies}×</td>
                    <td className="mono">{percent(card.first)}</td>
                    <td className="mono">{percent(card.second)}</td>
                    <td className="card-name">{card.name}</td>
                  </tr>
                ))}
              </tbody>
            );
          })}
        </table>
      </Section>
    </div>
  );
});
