// Excel (.xlsx) downloads of the probabilities and the comparison. exceljs is large, so it's
// only loaded when an export is clicked.

import type { Workbook, Worksheet } from "exceljs";
import { CATEGORIES, CATEGORY_LABELS, combinationOdds, Comparison, DrawResult, OddsPair, percentDigits, Stats } from "./api";

type Cell = string | number | null;
/** How a column's numbers are shown */
type Format = "percent" | "number" | "decimal" | "text";

const NUM_FMT: Record<Format, string | undefined> = {
  percent: "0.0%", number: "0", decimal: "0.00", text: undefined,
};

const HEADER_FILL = { type: "pattern", pattern: "solid", fgColor: { argb: "FF1C202B" } } as const;

/** A titled table: a bold title row, a header row, then the rows; returns the next free row */
function addTable(sheet: Worksheet, startRow: number, title: string, headers: string[], formats: Format[], rows: Cell[][]): number {
  sheet.getCell(startRow, 1).value = title;
  sheet.getCell(startRow, 1).font = { bold: true, size: 13 };

  const header = sheet.getRow(startRow + 1);
  headers.forEach((text, i) => {
    const cell = header.getCell(i + 1);
    cell.value = text;
    cell.font = { bold: true, color: { argb: "FFFFFFFF" } };
    cell.fill = HEADER_FILL;
  });

  rows.forEach((values, r) => {
    const row = sheet.getRow(startRow + 2 + r);
    values.forEach((value, i) => {
      const cell = row.getCell(i + 1);
      cell.value = value;
      const fmt = NUM_FMT[formats[i] ?? "text"];
      if (fmt && typeof value === "number") {
        // A tiny chance gets enough decimals not to show as 0.0%
        const places = formats[i] === "percent" ? percentDigits(Math.abs(value)) : 1;
        cell.numFmt = places > 1 ? `0.${"0".repeat(places)}%` : fmt;
      }
    });
  });
  return startRow + rows.length + 3;
}

/** Widen each column to its longest value */
function fitColumns(sheet: Worksheet) {
  sheet.columns.forEach((column) => {
    let width = 8;
    column.eachCell?.({ includeEmpty: false }, (cell) => {
      const text = typeof cell.value === "number" ? cell.value.toFixed(3) : String(cell.value ?? "");
      width = Math.max(width, Math.min(text.length + 2, 48));
    });
    column.width = width;
  });
}

async function newWorkbook(): Promise<Workbook> {
  const { default: ExcelJS } = await import("exceljs");
  const workbook = new ExcelJS.Workbook();
  workbook.creator = "Yu-Gi-Oh! Hand Simulator";
  workbook.created = new Date();
  return workbook;
}

/** A name that's safe as a file name */
const fileSafe = (name: string) => name.replace(/[\\/:*?"<>|]+/g, "_").trim() || "deck";

async function download(workbook: Workbook, fileName: string) {
  workbook.worksheets.forEach(fitColumns);
  const buffer = await workbook.xlsx.writeBuffer();
  const blob = new Blob([buffer], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${fileSafe(fileName)}.xlsx`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

/** Card groups as the Probabilities panel shows them */
const GROUP_LABELS: Record<string, string> = { ...CATEGORY_LABELS, mixed: "Mixed tags", untagged: "Untagged" };

/** One deck's statistics: everything its Probabilities panel shows, going first (5 cards) and
 *  going second (6 cards) side by side, in the panel's order, plus the test hand if one was drawn */
export async function exportStats({ name, first, second, draw, labelled }: {
  name: string;
  first: Stats;
  second: Stats;
  draw: DrawResult | null;
  /** Whether the deck's cards are labelled (the panel groups the card odds by label then) */
  labelled: boolean;
}) {
  const workbook = await newWorkbook();
  const sheet = workbook.addWorksheet("Probabilities");
  const both = ["", "Going first", "Going second"];
  const pct: Format[] = ["text", "percent", "percent"];

  sheet.getCell(1, 1).value = name;
  sheet.getCell(1, 1).font = { bold: true, size: 15 };
  sheet.getCell(2, 1).value = `Exported ${new Date().toLocaleString()} · going first = 5-card hand, going second = 6 cards`;
  sheet.getCell(2, 1).font = { italic: true, color: { argb: "FF6B7280" } };

  let row = addTable(sheet, 4, "Composition", ["", "Cards"], ["text", "number"], [
    ["Deck size", first.deck_size],
    ...CATEGORIES.map((key): Cell[] => [CATEGORY_LABELS[key], first.counts[key]]),
    ["Untagged", first.counts.untagged],
  ]);

  // Chance of drawing X or more: 1..5 going first, 1..6 going second
  const atLeast = CATEGORIES.flatMap((key) =>
    second.at_least[key].map((p2, i): Cell[] => [
      `At least ${i + 1} ${CATEGORY_LABELS[key].toLowerCase()}`, first.at_least[key][i] ?? null, p2,
    ]));
  row = addTable(sheet, row, "Opening hand (chance of drawing X or more)", both, pct, atLeast);

  row = addTable(sheet, row, "Opening hand combinations", both, pct,
    first.combinations.map((c, i) => [c.label, c.probability, second.combinations[i]?.probability ?? null]));

  row = addTable(sheet, row, "Average per hand", both, ["text", "decimal", "decimal"],
    CATEGORIES.map((key) => [CATEGORY_LABELS[key], first.averages[key], second.averages[key]]));

  row = addTable(sheet, row, "Bricks", both, pct, [
    ["Open with a brick", first.bricks.open, second.bricks.open],
    ["Draw one as the next card (6th / 7th)", first.bricks.draw_sixth, second.bricks.draw_sixth],
    ["See one by the next draw (6 / 7 cards)", first.bricks.by_turn_one, second.bricks.by_turn_one],
  ]);

  // The Engine × Non-Engine table, once per hand size
  for (const [stats, label] of [[first, "going first"], [second, "going second"]] as const) {
    row = addTable(sheet, row, `Engine × Non-Engine, exact counts in hand (${label})`,
      ["Engine \\ Non-engine", ...stats.matrix[0].map((_, ne) => `${ne} NE`)],
      ["text", ...stats.matrix[0].map((): Format => "percent")],
      stats.matrix.map((cells, e) => [`${e} E`, ...cells]));
  }

  if (draw) {
    row = addTable(sheet, row, "Test hand", ["Card", "Label"], ["text", "text"], [
      ...draw.hand.map((card): Cell[] => [card.name, card.category ? CATEGORY_LABELS[card.category] : ""]),
      ...(draw.sixth ? [[`6th card: ${draw.sixth.name}`, draw.sixth.category ? CATEGORY_LABELS[draw.sixth.category] : ""]] : []),
      ...draw.draws.map((card, i): Cell[] => [`Draw ${i + 7}: ${card.name}`, card.category ? CATEGORY_LABELS[card.category] : ""]),
    ]);
  }
  const sixth = first.sixth_card;
  if (sixth) {
    row = addTable(sheet, row, "6th card (based on the test hand)", ["", "Left in deck", "Chance"],
      ["text", "number", "percent"],
      CATEGORIES.map((key) => [CATEGORY_LABELS[key], sixth[key].remaining, sixth[key].probability]));
  }

  addTable(sheet, row, "Card odds (at least 1 copy)", ["Card", "Qty", "Label", "Going first", "Going second"],
    ["text", "number", "text", "percent", "percent"],
    first.cards.map((card) => [
      card.name, card.copies, labelled ? GROUP_LABELS[card.group] ?? "" : "", card.first, card.second,
    ]));

  await download(workbook, `${name} - probabilities`);
}

/** The comparison of two decks, going first and going second (results for hand sizes 5 and 6) */
export async function exportComparison([first, second]: [Comparison, Comparison]) {
  const [a, b] = first.names;
  const sides = [{ result: first, label: "going first" }, { result: second, label: "going second" }];
  const workbook = await newWorkbook();

  const overview = workbook.addWorksheet("Comparison");
  // The composition doesn't depend on the hand size
  let row = addTable(overview, 1, "Composition", ["", a, b, `Diff (${b} − ${a})`], ["text", "number", "number", "number"],
    first.composition.map((r) => [r.label, r.a, r.b, r.b - r.a]));
  const oddsRows = (result: Comparison, rows: OddsPair[]): Cell[][] =>
    rows.map((r) => [r.label, r.a, r.b, r.b - r.a, r.better ? result.names[r.better - 1] : ""]);
  const oddsTable = (title: string, result: Comparison, rows: OddsPair[]) =>
    addTable(overview, row, title, ["", a, b, "Diff", "Better"], ["text", "percent", "percent", "percent", "text"],
      oddsRows(result, rows));
  for (const { result, label } of sides) {
    row = oddsTable(`Opening hand (${label})`, result, combinationOdds(result));
  }
  for (const { result, label } of sides) {
    row = oddsTable(`Chance of drawing X or more (${label})`, result, result.at_least.flatMap((group) => group.rows));
  }
  for (const { result, label } of sides) {
    row = oddsTable(`Bricks (${label})`, result, result.bricks);
  }
  for (const { result, label } of sides) {
    row = addTable(overview, row, `Average per hand (${label})`, ["", a, b, "Diff"], ["text", "decimal", "decimal", "decimal"],
      result.averages.map((r) => [r.label, r.a, r.b, r.b - r.a]));
  }

  // One row per card with both hand sizes side by side
  const secondByName = new Map(second.cards.map((c) => [c.name, c]));
  const cards = workbook.addWorksheet("Card odds");
  addTable(cards, 1, "Chance of at least 1 copy",
    ["Card", `${a} qty`, `${b} qty`,
     `${a} going first`, `${b} going first`, "Diff going first",
     `${a} going second`, `${b} going second`, "Diff going second", "Changed"],
    ["text", "number", "number", "percent", "percent", "percent", "percent", "percent", "percent", "text"],
    first.cards.map((c) => {
      const s = secondByName.get(c.name);
      return [
        c.name, c.a_copies, c.b_copies,
        c.a_copies ? c.a : null, c.b_copies ? c.b : null, c.b - c.a,
        s && c.a_copies ? s.a : null, s && c.b_copies ? s.b : null, s ? s.b - s.a : null,
        c.changed ? "Yes" : "",
      ];
    }));

  await download(workbook, `${a} vs ${b} - comparison`);
}
