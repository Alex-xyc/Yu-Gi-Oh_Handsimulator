// Opening-hand probabilities & statistics

import { motion } from "framer-motion";
import { memo } from "react";
import { CardOdds, CATEGORIES, CATEGORY_LABELS, percent, Stats } from "../api";
import { AnimatedPercent, Bar } from "./common";

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
          <stop offset="0" stopColor="var(--accent)" />
          <stop offset="1" stopColor="var(--deck-b)" />
        </linearGradient>
      </defs>
      <motion.path d="M 10 6 V 74 H 112" stroke="var(--muted)" strokeOpacity="0.55" strokeWidth="4" {...draw(0)} />
      <motion.path d="M 22 62 C 26 46, 30 42, 34 52 S 42 62, 48 50 S 58 38, 64 48 S 78 52, 98 18"
                   stroke="url(#chart-line)" strokeWidth="5" {...draw(0.35)} />
      <motion.path d="M 84 16 L 99 16 L 99 31" stroke="var(--deck-b)" strokeWidth="5" {...draw(1.1)} />
    </svg>
  );
}

function Section({ title, hint, children }: { title: string; hint?: string; children: React.ReactNode }) {
  return (
    <motion.section className="stats-section" layout="position">
      <h3>{title}{hint && <span className="muted small"> {hint}</span>}</h3>
      {children}
    </motion.section>
  );
}

export const StatsView = memo(function StatsView({ stats, tagged, hasHand }: { stats: Stats | null; tagged: boolean; hasHand: boolean }) {
  if (!stats) {
    return (
      <div className="stats-empty">
        <ChartIcon />
        <p className="muted">Statistics appear here once a deck is loaded.</p>
      </div>
    );
  }
  const maxCell = Math.max(...stats.matrix.flat().map((p) => p ?? 0), 0.0001);
  const grouped = tagged;

  return (
    <div className="stats">
      <div className="composition">
        <div className="stat-tile"><span className="stat-value">{stats.deck_size}</span><span className="muted">cards</span></div>
        {CATEGORIES.map((key) => (
          <div key={key} className={`stat-tile tone-${key}`}>
            <span className="stat-value">{stats.counts[key]}</span>
            <span className="muted">{CATEGORY_LABELS[key]}</span>
          </div>
        ))}
        {stats.counts.untagged > 0 && (
          <div className="stat-tile"><span className="stat-value">{stats.counts.untagged}</span><span className="muted">Untagged</span></div>
        )}
      </div>

      <Section title="Opening hand" hint="(chance of drawing X or more)">
        <div className="odds-groups">
          {CATEGORIES.map((key) => (
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
              <tr><th />{stats.matrix[0].map((_, ne) => <th key={ne}>{ne} NE</th>)}</tr>
            </thead>
            <tbody>
              {stats.matrix.map((row, e) => (
                <tr key={e}>
                  <th>{e} E</th>
                  {row.map((p, ne) => (
                    <td key={ne} className="mono"
                        style={{ ["--heat" as string]: p ? String(0.08 + 0.72 * (p / maxCell)) : "0" }}>
                      {p && p >= 0.0005 ? percent(p) : "–"}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      <Section title="Bricks">
        <div className="tiles">
          <div className="stat-tile wide"><span className="stat-value"><AnimatedPercent value={stats.bricks.open} /></span><span className="muted">Open with a brick</span></div>
          <div className="stat-tile wide"><span className="stat-value"><AnimatedPercent value={stats.bricks.draw_sixth} /></span><span className="muted">Draw one 6th</span></div>
          <div className="stat-tile wide"><span className="stat-value"><AnimatedPercent value={stats.bricks.by_turn_one} /></span><span className="muted">See one by turn 1</span></div>
        </div>
      </Section>

      <Section title="6th card" hint="(based on the current hand)">
        {stats.sixth_card ? (
          <div className="odds-rows">
            {CATEGORIES.map((key) => (
              <div key={key} className="odds-row">
                <span>{CATEGORY_LABELS[key]} <span className="muted small">({stats.sixth_card![key].remaining}/{stats.sixth_card!.deck_remaining})</span></span>
                <Bar value={stats.sixth_card![key].probability} tone={key} />
                <span className="mono value"><AnimatedPercent value={stats.sixth_card![key].probability} /></span>
              </div>
            ))}
          </div>
        ) : (
          <p className="muted small">
            {!hasHand ? "Draw a hand to see these." :
              "Label your cards in the decklist to see these."}
          </p>
        )}
      </Section>

      <Section title="Card odds" hint="(at least 1 copy)">
        <table className="card-odds">
          <thead>
            <tr><th>Qty</th><th>Going first</th><th>Going second</th><th>Card</th></tr>
          </thead>
          {GROUPS.map(({ key, title }) => {
            const cards = stats.cards.filter((c) => c.group === key);
            if (!cards.length) return null;
            return (
              <tbody key={key}>
                {grouped && <tr className="group-row"><td colSpan={4}><i className={`dot tone-${key}`} />{title}</td></tr>}
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
