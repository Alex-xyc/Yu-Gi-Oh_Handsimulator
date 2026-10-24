import { describe, expect, it } from "vitest";
import i18n, { resources } from ".";

type Tree = { [key: string]: string | Tree };

/** Every key in a translation file ("a.b.c"), with its text */
function flatten(tree: Tree, prefix = ""): Map<string, string> {
  const keys = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix ? `${prefix}.${key}` : key;
    if (typeof value === "string") keys.set(path, value);
    else for (const [k, v] of flatten(value, path)) keys.set(k, v);
  }
  return keys;
}

/** The base keys, without plural suffixes (a language can have other plural forms than English) */
const baseKeys = (keys: Map<string, string>) =>
  [...new Set([...keys.keys()].map((key) => key.replace(/_(zero|one|two|few|many|other)$/, "")))].sort();

const placeholders = (text: string) => [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort();

const english = flatten(resources.en.translation);

describe("translations", () => {
  it.each(Object.entries(resources))("%s has the same keys and placeholders as English", (_, { translation }) => {
    const keys = flatten(translation);
    expect(baseKeys(keys)).toEqual(baseKeys(english));
    for (const [key, text] of keys) {
      const base = english.get(key) ?? english.get(key.replace(/_\w+$/, "_other"));
      if (base) expect(placeholders(text), key).toEqual(placeholders(base));
    }
  });

  it("fills in values and picks plural forms", () => {
    expect(i18n.t("app.name")).toBe("YGO Calc");
    expect(i18n.t("stats.categoryRow.brick", { count: 1 })).toBe("1 brick");
    expect(i18n.t("stats.categoryRow.brick", { count: 2 })).toBe("2 bricks");
    expect(i18n.t("common.atLeastLabel", { count: 2, name: "<Starter>" })).toBe("At least 2 <Starter>");
  });
});
