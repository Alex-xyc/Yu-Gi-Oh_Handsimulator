import { afterEach, describe, expect, it, vi } from "vitest";
import {
  api, ApiError, cardImageUrl, combinationOdds, type Comparison, decimalsFor, type OddsPair, percent, percentWidth,
} from "./api";

describe("decimalsFor", () => {
  it("keeps the default digits for zero and ordinary values", () => {
    expect(decimalsFor(0)).toBe(1);
    expect(decimalsFor(42.5)).toBe(1);
    expect(decimalsFor(0.05)).toBe(1);
    expect(decimalsFor(3, 2)).toBe(2);
  });

  it("shows two significant figures of a small value", () => {
    expect(decimalsFor(0.038)).toBe(3);
    expect(decimalsFor(0.0049)).toBe(4);
    // Rounds to 0.010, not 0.0100
    expect(decimalsFor(0.00999)).toBe(3);
  });

  it("works for negative values (differences)", () => {
    expect(decimalsFor(-0.038)).toBe(3);
  });
});

describe("percent", () => {
  it("formats a 0..1 chance", () => {
    expect(percent(0)).toBe("0.0%");
    expect(percent(1)).toBe("100.0%");
    expect(percent(0.992)).toBe("99.2%");
  });

  it("never rounds a small non-zero chance to 0", () => {
    expect(percent(0.00038)).toBe("0.038%");
    expect(percent(0.000049)).toBe("0.0049%");
  });

  it("takes other digits or decimals", () => {
    expect(percent(0.5, 2)).toBe("50.00%");
    expect(percent(0.5, 1, 0)).toBe("50%");
  });
});

describe("percentWidth", () => {
  it("is the longest value's length", () => {
    expect(percentWidth([0.5, 1, 0.000049])).toBe("0.0049%".length);
    expect(percentWidth([0.05])).toBe("5.0%".length);
  });

  it("is 0 without values", () => {
    expect(percentWidth([])).toBe(0);
  });
});

describe("cardImageUrl", () => {
  it("builds the URL for a card ID", () => {
    expect(cardImageUrl("89631139")).toBe("/api/cards/89631139/image?size=small");
    expect(cardImageUrl("89631139", "full")).toBe("/api/cards/89631139/image?size=full");
  });

  it("is null without a numeric ID", () => {
    expect(cardImageUrl(undefined)).toBeNull();
    expect(cardImageUrl("")).toBeNull();
    expect(cardImageUrl("abc")).toBeNull();
    expect(cardImageUrl("12/../34")).toBeNull();
  });
});

describe("combinationOdds", () => {
  const pair = (label: string): OddsPair => ({ label, a: 0.5, b: 0.5, better: null });

  it("leaves out the rows already in the at-least breakdown", () => {
    const result = {
      odds: [pair("At least 1 engine"), pair("1+ engine & no bricks"), pair("At least 1 brick")],
      at_least: [
        { key: "engine", label: "Engine", rows: [pair("At least 1 engine")] },
        { key: "brick", label: "Brick", rows: [pair("At least 1 brick")] },
      ],
    } as unknown as Comparison;
    expect(combinationOdds(result).map((row) => row.label)).toEqual(["1+ engine & no bricks"]);
  });
});

describe("api", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  const respond = (status: number, body: string) => {
    // A new response each call: a body can only be read once
    const fetch = vi.fn().mockImplementation(async () => new Response(body, { status }));
    vi.stubGlobal("fetch", fetch);
    return fetch;
  };

  it("posts JSON and returns the answer", async () => {
    const fetch = respond(200, JSON.stringify({ cards: [], side: [], size: 0 }));
    await expect(api.loadDeck("ydke://abc")).resolves.toEqual({ cards: [], side: [], size: 0 });
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/decks");
    expect(init.method).toBe("POST");
    expect(init.headers).toEqual({ "Content-Type": "application/json" });
    expect(JSON.parse(init.body)).toEqual({ code: "ydke://abc" });
  });

  it("asks for the odds going second with hand size 6", async () => {
    const fetch = respond(200, "{}");
    const deck = { name: "Deck", cards: [{ name: "Ash", copies: 3 }], tags: null, counts: null };
    await api.stats(deck);
    await api.stats(deck, undefined, 6);
    expect(fetch.mock.calls.map(([url]) => url)).toEqual(["/api/stats?hand_size=5", "/api/stats?hand_size=6"]);
  });

  it("throws the server's message", async () => {
    respond(400, JSON.stringify({ detail: "No main deck cards found." }));
    await expect(api.loadDeck("hello")).rejects.toEqual(new ApiError("No main deck cards found."));
  });

  it("throws a generic message when the answer isn't JSON", async () => {
    respond(500, "Internal Server Error");
    const error = await api.loadDeck("#main\n124").catch((e) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error.message).toBe("Request failed (500)");
  });

  it("throws a generic message when the detail isn't text", async () => {
    respond(422, JSON.stringify({ detail: [{ msg: "Field required" }] }));
    await expect(api.loadDeck("")).rejects.toThrow("Request failed (422)");
  });
});
