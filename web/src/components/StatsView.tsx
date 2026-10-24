// Opening-hand probabilities & statistics

import { motion } from "framer-motion";
import { memo } from "react";
import { useTranslation } from "react-i18next";
import { type CardOdds, CATEGORIES, percent, percentWidth, type Stats } from "../api";
import { atLeast, atLeastEach } from "../odds";
import type { CustomLabelCount } from "../customLabels";
import { MAX_COPIES } from "../useDeckSetup";
import { AnimatedPercent, Bar, Dot, SectionHeader, StatTile } from "./common";

/** The card odds table's groups, in order (titled t(`categories.${group}`)) */
const GROUPS: CardOdds["group"][] = ["engine", "non_engine", "brick", "mixed", "untagged"];

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
  const { t } = useTranslation();
  const copyHeads = (side: number) => COPIES.map((n) => (
    <th key={`${side}-${n}`} scope="col" className={n === 1 ? "odds-col-start" : ""}>
      <abbr title={t("stats.atLeastCopies", { count: n })}>{t("stats.copiesPlus", { count: n })}</abbr>
    </th>
  ));
  return (
    <thead>
      <tr>
        <th scope="col" rowSpan={2}>{t("stats.qty")}</th>
        <th scope="colgroup" colSpan={COPIES.length} className="odds-col-start">{t("common.goingFirst")}</th>
        <th scope="col" rowSpan={2}>{t("stats.card")}</th>
        <th scope="colgroup" colSpan={COPIES.length} className="odds-col-start">{t("common.goingSecond")}</th>
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
  const { t } = useTranslation();
  const odds = (side: number) => COPIES.map((n) => (
    <td key={`${side}-${n}`} className={`mono ${n === 1 ? "odds-col-start" : ""} ${n > copies ? "muted" : ""}`}>
      {n > copies ? "–" : percent(atLeast(deckSize, copies, handSize + side, n))}
    </td>
  ));
  return (
    <tr>
      <td className="mono">{t("stats.copies", { count: copies })}</td>
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

/** "Going first (5 cards)" and "Going second (6 cards)" over the two columns of odds */
function SplitHeading({ handSize }: { handSize: number }) {
  const { t } = useTranslation();
  return (
    <div className="odds-split small muted" aria-hidden="true">
      <span>{t("common.goingFirstCards", { count: handSize })}</span>
      <span>{t("common.goingSecondCards", { count: handSize + 1 })}</span>
    </div>
  );
}

/** One column of odds rows, going first (side 0) or second (side 1); the heading shows over each
 *  column on phones (data-side) and is read out to screen readers */
function OddsColumn({ side, handSize, children }: { side: number; handSize: number; children: React.ReactNode }) {
  const { t } = useTranslation();
  return (
    <div className="odds-rows"
         data-side={side ? t("common.goingSecondCards", { count: handSize + 1 }) : t("common.goingFirstCards", { count: handSize })}>
      <span className="sr-only">{side ? t("common.goingSecond") : t("common.goingFirst")}</span>
      {children}
    </div>
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
  const { t } = useTranslation();
  if (!stats) {
    return (
      <div className="stats-empty">
        <ChartIcon />
        <p className="muted">{t("stats.empty")}</p>
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
        <StatTile value={stats.deck_size} label={t("stats.cards")} />
        {CATEGORIES.map((key) => <StatTile key={key} value={stats.counts[key]} label={t(`categories.${key}`)} tone={key} />)}
        {stats.counts.untagged > 0 && <StatTile value={stats.counts.untagged} label={t("categories.untagged")} />}
        {customLabels.map((label) => (
          <StatTile key={label.id} value={label.count} label={label.name} tone="custom" color={label.color} />
        ))}
      </div>

      <Section title={t("stats.openingHand")} hint={t("common.chanceXOrMore")}>
        {/* Going first (left) and second (right) side by side, one block per category */}
        <div className="odds-groups" style={{ ["--value-ch" as string]: valueWidth }}>
          <SplitHeading handSize={stats.hand_size} />
          {CATEGORIES.map((key) => (
            <div key={key} className="odds-split">
              {[stats.at_least[key], atLeastSecond[key]].map((odds, side) => (
                <OddsColumn key={side} side={side} handSize={stats.hand_size}>
                  {odds.map((p, i) => (
                    <div key={i} className="odds-row">
                      <span>{t(`stats.categoryRow.${key}`, { count: i + 1 })}</span>
                      <Bar value={p} tone={key} />
                      <span className="mono value"><AnimatedPercent value={p} /></span>
                    </div>
                  ))}
                </OddsColumn>
              ))}
            </div>
          ))}
        </div>
      </Section>

      {customOdds.length > 0 && (
        <Section title={t("stats.customLabels")} hint={t("common.chanceXOrMore")}>
          <div className="odds-groups wide-labels" style={{ ["--value-ch" as string]: customWidth }}>
            <SplitHeading handSize={stats.hand_size} />
            {customOdds.map(({ label, first, second }) => (
              label.count ? (
                <div key={label.id} className="odds-split">
                  {[first, second].map((odds, side) => (
                    <OddsColumn key={side} side={side} handSize={stats.hand_size}>
                      {odds.map((p, i) => (
                        <div key={i} className="odds-row">
                          <span className="min-w-0 truncate" title={label.name}>{t("stats.customRow", { count: i + 1, name: label.name })}</span>
                          <Bar value={p} tone="custom" color={label.color} />
                          <span className="mono value"><AnimatedPercent value={p} /></span>
                        </div>
                      ))}
                    </OddsColumn>
                  ))}
                </div>
              ) : (
                <div key={label.id} className="odds-rows">
                  <span className="flex items-center small muted" style={{ ["--tone" as string]: label.color }}>
                    <i className="dot" aria-hidden="true" />{t("stats.noneLabelled", { name: label.name })}
                  </span>
                </div>
              )
            ))}
          </div>
        </Section>
      )}

      <Section title={t("stats.matrix")} hint={t("stats.exactCounts")}>
        <div className="matrix-wrap">
          <table className="matrix">
            <thead>
              <tr>
                <th scope="col"><span className="sr-only">{t("stats.engineDrawn")}</span></th>
                {stats.matrix[0].map((_, ne) => (
                  <th key={ne} scope="col">
                    <abbr title={t("stats.nonEngineLong", { count: ne })}>{t("stats.nonEngineShort", { count: ne })}</abbr>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {stats.matrix.map((row, e) => (
                <tr key={e}>
                  <th scope="row"><abbr title={t("stats.engineLong", { count: e })}>{t("stats.engineShort", { count: e })}</abbr></th>
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

      <Section title={t("stats.bricks")}>
        <div className="stat-tiles">
          <StatTile wide value={<AnimatedPercent value={stats.bricks.open} />} label={t("stats.openWithBrick")} />
          <StatTile wide value={<AnimatedPercent value={stats.bricks.draw_sixth} />} label={t("stats.drawSixthBrick")} />
          <StatTile wide value={<AnimatedPercent value={stats.bricks.by_turn_one} />} label={t("stats.brickByTurnOne")} />
        </div>
      </Section>

      {sidedIn > 0 && (
        <Section title={t("stats.sideDeckCards")} hint={t("stats.sideDeckHint", { count: sidedIn })}>
          {/* Going first (left) and second (right) side by side, as in the opening hand odds */}
          <div className="odds-groups wide-labels" style={{ ["--value-ch" as string]: sideWidth }}>
            <SplitHeading handSize={stats.hand_size} />
            <div className="odds-split">
              {sideOdds.map((odds, side) => (
                <OddsColumn key={side} side={side} handSize={stats.hand_size}>
                  {odds.map((p, i) => (
                    <div key={i} className="odds-row">
                      <span>{t("stats.sideDeckRow", { count: i + 1 })}</span>
                      <Bar value={p} tone="side" />
                      <span className="mono value"><AnimatedPercent value={p} /></span>
                    </div>
                  ))}
                </OddsColumn>
              ))}
            </div>
          </div>
          <table className="data-table mt-4">
            <CopyOddsHead />
            <tbody>
              {sidedCards.map((card) => (
                <CopyOddsRow key={card.name} copies={card.copies} deckSize={stats.deck_size} handSize={stats.hand_size}>
                  {card.name}
                  {card.sided < card.copies && (
                    <span className="muted small"> · {t("stats.sidedOf", { sided: card.sided, copies: card.copies })}</span>
                  )}
                </CopyOddsRow>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      <Section title={t("stats.sixthCard")} hint={t("stats.basedOnHand")}>
        {(stats.sixth_card || sideSixth || customSixth.length > 0) && (
          <div className="odds-rows">
            {stats.sixth_card && CATEGORIES.map((key) => (
              <div key={key} className="odds-row">
                <span>{t(`categories.${key}`)} <span className="muted small">({stats.sixth_card![key].remaining}/{stats.sixth_card!.deck_remaining})</span></span>
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
                <span>{t("stats.sideDeckCard")} <span className="muted small">({sideSixth.remaining}/{deckRemaining})</span></span>
                <Bar value={sideSixth.probability} tone="side" />
                <span className="mono value"><AnimatedPercent value={sideSixth.probability} /></span>
              </div>
            )}
          </div>
        )}
        {!stats.sixth_card && (
          <p className={`muted small ${sideSixth || customSixth.length ? "mt-2 mb-0" : ""}`}>
            {!hasHand ? t("stats.drawToSee")
              : sideSixth || customSixth.length ? t("stats.labelToSeeCategories") : t("stats.labelToSee")}
          </p>
        )}
      </Section>

      <Section title={t("stats.cardOdds")} hint={t("stats.cardOddsHint")}>
        <table className="data-table">
          <CopyOddsHead />
          {GROUPS.map((key) => {
            const cards = stats.cards.filter((c) => c.group === key);
            if (!cards.length) return null;
            return (
              <tbody key={key}>
                {grouped && <tr className="group-row"><td colSpan={3 + 2 * COPIES.length}><Dot tone={key} />{t(`categories.${key}`)}</td></tr>}
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
