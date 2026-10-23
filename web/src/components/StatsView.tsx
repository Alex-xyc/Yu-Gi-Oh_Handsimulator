// Opening-hand probabilities & statistics

import { motion } from "framer-motion";
import { memo } from "react";
import { type CardOdds, CATEGORIES, CATEGORY_LABELS, percent, percentWidth, type Stats } from "../api";
import { atLeast, atLeastEach } from "../odds";
import type { CustomLabelCount } from "../customLabels";
import { MAX_COPIES } from "../useDeckSetup";
import { AnimatedPercent, Bar, Dot, SectionHeader, StatTile } from "./common";

const GROUPS: { key: CardOdds["group"]; title: string }[] = [
  { key: "engine", title: "Engine" },
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

/** A card with copies sided in: its copies in the deck, and how many of them were sided in */
export interface SidedCard {
  name: string;
  copies: number;
  sided: number;
}

/** At least 1, 2, … up to the most copies a deck can have */
const COPIES = Array.from({ length: MAX_COPIES }, (_, i) => i + 1);

/** Card odds table heading: the quantity, the chance of at least 1, 2 and 3 copies going first,
 *  the card, then the same going second (on the right, as in the opening hand odds) */
function CopyOddsHead() {
  const copyHeads = (side: number) => COPIES.map((n) => (
    <th key={`${side}-${n}`} scope="col" className={n === 1 ? "odds-col-start" : ""}>
      <abbr title={`At least ${n} ${n === 1 ? "copy" : "copies"}`}>{n}+</abbr>
    </th>
  ));
  return (
    <thead>
      <tr>
        <th scope="col" rowSpan={2}>Qty</th>
        <th scope="colgroup" colSpan={COPIES.length} className="odds-col-start">Going first</th>
        <th scope="col" rowSpan={2}>Card</th>
        <th scope="colgroup" colSpan={COPIES.length} className="odds-col-start">Going second</th>
      </tr>
      <tr>{copyHeads(0)}{copyHeads(1)}</tr>
    </thead>
  );
}

/** One card's row: its quantity, its chance of at least 1, 2 and 3 copies going first, the card
 *  (`children`), then the same going second ("–" for more copies than it has) */
function CopyOddsRow({ copies, deckSize, handSize, children }: {
  copies: number; deckSize: number; handSize: number; children: React.ReactNode;
}) {
  const odds = (side: number) => COPIES.map((n) => (
    <td key={`${side}-${n}`} className={`mono ${n === 1 ? "odds-col-start" : ""} ${n > copies ? "muted" : ""}`}>
      {n > copies ? "–" : percent(atLeast(deckSize, copies, handSize + side, n))}
    </td>
  ));
  return (
    <tr>
      <td className="mono">{copies}×</td>
      {odds(0)}
      <td className="card-name">{children}</td>
      {odds(1)}
    </tr>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <motion.section className="stats-section" layout="position">
      <SectionHeader title={title} hint={hint} />
      {children}
    </motion.section>
  );
}

export const StatsView = memo(function StatsView({ stats, tagged, hasHand, sidedCards = [], sidedInHand = null, customLabels = [],
  customInHand = null }: {
  stats: Stats | null; tagged: boolean; hasHand: boolean;
  /** The custom labels (advanced mode), whose odds are shown when there are any */
  customLabels?: CustomLabelCount[];
  /** How many of the drawn hand's cards have each custom label (by id); null with no hand */
  customInHand?: Record<string, number> | null;
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
  // Going second draws one more card: at least 1 .. hand_size + 1 of each category
  const atLeastSecond = Object.fromEntries(CATEGORIES.map((key) => [key,
    Array.from({ length: stats.hand_size + 1 }, (_, i) => atLeast(stats.deck_size, stats.counts[key], stats.hand_size + 1, i + 1)),
  ])) as Record<(typeof CATEGORIES)[number], number[]>;
  const valueWidth = percentWidth(CATEGORIES.flatMap((key) => [...stats.at_least[key], ...atLeastSecond[key]]));
  const grouped = tagged;

  // Opening at least 1 .. hand_size of the cards sided in going first, 1 .. hand_size + 1 going
  // second, as in the opening hand odds (0% for more than were sided in)
  const sidedIn = sidedCards.reduce((total, card) => total + card.sided, 0);
  const sideOdds = [stats.hand_size, stats.hand_size + 1].map((cards) =>
    Array.from({ length: cards }, (_, i) => atLeast(stats.deck_size, sidedIn, cards, i + 1)));
  // The 6th card being one of the sided-in cards still in the deck, after the current hand
  const deckRemaining = stats.deck_size - stats.hand_size;
  const sideSixth = sidedIn > 0 && sidedInHand !== null && deckRemaining > 0
    ? { remaining: sidedIn - sidedInHand, probability: (sidedIn - sidedInHand) / deckRemaining } : null;
  const sideWidth = percentWidth(sideOdds.flat());

  // Each custom label: at least 1 .. as many as it has (no more than the hand), going first and second
  const customOdds = customLabels.map((label) => ({
    label,
    first: atLeastEach(stats.deck_size, label.count, stats.hand_size),
    second: atLeastEach(stats.deck_size, label.count, stats.hand_size + 1),
  }));
  const customWidth = percentWidth(customOdds.flatMap(({ first, second }) => [...first, ...second]));
  // The 6th card having each custom label, after the current hand
  const customSixth = customInHand && deckRemaining > 0
    ? customLabels.filter((label) => label.count).map((label) => {
      const remaining = label.count - (customInHand[label.id] ?? 0);
      return { label, remaining, probability: remaining / deckRemaining };
    }) : [];

  return (
    <div className="stats">
      <div className="stat-tiles">
        <StatTile value={stats.deck_size} label="cards" />
        {CATEGORIES.map((key) => <StatTile key={key} value={stats.counts[key]} label={CATEGORY_LABELS[key]} tone={key} />)}
        {stats.counts.untagged > 0 && <StatTile value={stats.counts.untagged} label="Untagged" />}
        {customLabels.map((label) => (
          <StatTile key={label.id} value={label.count} label={label.name} tone="custom" color={label.color} />
        ))}
      </div>

      <Section title="Opening hand" hint="(chance of drawing X or more)">
        {/* Going first (left) and second (right) side by side, one block per category */}
        <div className="odds-groups" style={{ ["--value-ch" as string]: valueWidth }}>
          <div className="odds-split small muted" aria-hidden="true">
            <span>Going first ({stats.hand_size} cards)</span>
            <span>Going second ({stats.hand_size + 1} cards)</span>
          </div>
          {CATEGORIES.map((key) => (
            <div key={key} className="odds-split">
              {[stats.at_least[key], atLeastSecond[key]].map((odds, side) => (
                <div key={side} className="odds-rows"
                     data-side={side ? `Going second (${stats.hand_size + 1} cards)` : `Going first (${stats.hand_size} cards)`}>
                  <span className="sr-only">{side ? "Going second" : "Going first"}</span>
                  {odds.map((p, i) => (
                    <div key={i} className="odds-row">
                      <span>{i + 1} {CATEGORY_LABELS[key].toLowerCase()}{key === "brick" && i ? "s" : ""}</span>
                      <Bar value={p} tone={key} />
                      <span className="mono value"><AnimatedPercent value={p} /></span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </div>
      </Section>

      {customOdds.length > 0 && (
        <Section title="Custom labels" hint="(chance of drawing X or more)">
          <div className="odds-groups wide-labels" style={{ ["--value-ch" as string]: customWidth }}>
            <div className="odds-split small muted" aria-hidden="true">
              <span>Going first ({stats.hand_size} cards)</span>
              <span>Going second ({stats.hand_size + 1} cards)</span>
            </div>
            {customOdds.map(({ label, first, second }) => (
              label.count ? (
                <div key={label.id} className="odds-split">
                  {[first, second].map((odds, side) => (
                    <div key={side} className="odds-rows"
                         data-side={side ? `Going second (${stats.hand_size + 1} cards)` : `Going first (${stats.hand_size} cards)`}>
                      <span className="sr-only">{side ? "Going second" : "Going first"}</span>
                      {odds.map((p, i) => (
                        <div key={i} className="odds-row">
                          <span className="min-w-0 truncate" title={label.name}>{i + 1} {label.name}</span>
                          <Bar value={p} tone="custom" color={label.color} />
                          <span className="mono value"><AnimatedPercent value={p} /></span>
                        </div>
                      ))}
                    </div>
                  ))}
                </div>
              ) : (
                <div key={label.id} className="odds-rows">
                  <span className="flex items-center small muted" style={{ ["--tone" as string]: label.color }}>
                    <i className="dot" aria-hidden="true" />No cards labelled {label.name} yet
                  </span>
                </div>
              )
            ))}
          </div>
        </Section>
      )}

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
          {/* Going first (left) and second (right) side by side, as in the opening hand odds */}
          <div className="odds-groups wide-labels" style={{ ["--value-ch" as string]: sideWidth }}>
            <div className="odds-split small muted" aria-hidden="true">
              <span>Going first ({stats.hand_size} cards)</span>
              <span>Going second ({stats.hand_size + 1} cards)</span>
            </div>
            <div className="odds-split">
              {sideOdds.map((odds, side) => (
                <div key={side} className="odds-rows"
                     data-side={side ? `Going second (${stats.hand_size + 1} cards)` : `Going first (${stats.hand_size} cards)`}>
                  <span className="sr-only">{side ? "Going second" : "Going first"}</span>
                  {odds.map((p, i) => (
                    <div key={i} className="odds-row">
                      <span>{i + 1} side deck card{i ? "s" : ""}</span>
                      <Bar value={p} tone="side" />
                      <span className="mono value"><AnimatedPercent value={p} /></span>
                    </div>
                  ))}
                </div>
              ))}
            </div>
          </div>
          <table className="data-table mt-4">
            <CopyOddsHead />
            <tbody>
              {sidedCards.map((card) => (
                <CopyOddsRow key={card.name} copies={card.copies} deckSize={stats.deck_size} handSize={stats.hand_size}>
                  {card.name}
                  {card.sided < card.copies && <span className="muted small"> · {card.sided} of {card.copies} sided in</span>}
                </CopyOddsRow>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      <Section title="6th card" hint="(based on the current hand)">
        {(stats.sixth_card || sideSixth || customSixth.length > 0) && (
          <div className="odds-rows">
            {stats.sixth_card && CATEGORIES.map((key) => (
              <div key={key} className="odds-row">
                <span>{CATEGORY_LABELS[key]} <span className="muted small">({stats.sixth_card![key].remaining}/{stats.sixth_card!.deck_remaining})</span></span>
                <Bar value={stats.sixth_card![key].probability} tone={key} />
                <span className="mono value"><AnimatedPercent value={stats.sixth_card![key].probability} /></span>
              </div>
            ))}
            {customSixth.map(({ label, remaining, probability }) => (
              <div key={label.id} className="odds-row">
                <span className="min-w-0 truncate" title={label.name}>{label.name} <span className="muted small">({remaining}/{deckRemaining})</span></span>
                <Bar value={probability} tone="custom" color={label.color} />
                <span className="mono value"><AnimatedPercent value={probability} /></span>
              </div>
            ))}
            {/* Shown without labels too: which cards were sided in is known either way */}
            {sideSixth && (
              <div className="odds-row">
                <span>Side deck card <span className="muted small">({sideSixth.remaining}/{deckRemaining})</span></span>
                <Bar value={sideSixth.probability} tone="side" />
                <span className="mono value"><AnimatedPercent value={sideSixth.probability} /></span>
              </div>
            )}
          </div>
        )}
        {!stats.sixth_card && (
          <p className={`muted small ${sideSixth || customSixth.length ? "mt-2 mb-0" : ""}`}>
            {!hasHand ? "Draw a hand to see these." :
              `Label your cards in the decklist to see ${sideSixth || customSixth.length ? "the engine, non-engine and brick odds" : "these"}.`}
          </p>
        )}
      </Section>

      <Section title="Card odds" hint="(at least 1, 2 or 3 copies)">
        <table className="data-table">
          <CopyOddsHead />
          {GROUPS.map(({ key, title }) => {
            const cards = stats.cards.filter((c) => c.group === key);
            if (!cards.length) return null;
            return (
              <tbody key={key}>
                {grouped && <tr className="group-row"><td colSpan={3 + 2 * COPIES.length}><Dot tone={key} />{title}</td></tr>}
                {cards.map((card) => (
                  <CopyOddsRow key={card.name} copies={card.copies} deckSize={stats.deck_size} handSize={stats.hand_size}>
                    {card.name}
                  </CopyOddsRow>
                ))}
              </tbody>
            );
          })}
        </table>
      </Section>
    </div>
  );
});
