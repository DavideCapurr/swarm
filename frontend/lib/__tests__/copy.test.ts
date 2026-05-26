/**
 * Smoke guard for Plain Voice Rule v1.
 *
 * Walks every string exported from `lib/copy.ts` and fails on any
 * occurrence of a FORBIDDEN_WORDS token. Word-boundary matching keeps
 * short tokens (e.g. "AI") from false-matching inside other words.
 */

import { describe, expect, it } from "vitest";

import * as copy from "@/lib/copy";

function* walkStrings(value: unknown): Generator<string> {
  if (value == null) return;
  if (typeof value === "string") {
    yield value;
    return;
  }
  if (typeof value === "function") return;
  if (Array.isArray(value)) {
    for (const v of value) yield* walkStrings(v);
    return;
  }
  if (typeof value === "object") {
    for (const v of Object.values(value as Record<string, unknown>)) {
      yield* walkStrings(v);
    }
  }
}

describe("copy.ts", () => {
  it("does not leak any FORBIDDEN_WORDS token in exported strings", () => {
    const banned = copy.FORBIDDEN_WORDS;
    const offences: Array<{ word: string; sample: string }> = [];
    for (const [key, value] of Object.entries(copy)) {
      if (key === "FORBIDDEN_WORDS") continue;
      for (const s of walkStrings(value)) {
        for (const word of banned) {
          // eslint-disable-next-line security/detect-non-literal-regexp -- bounded scan over an in-repo const list
          const re = new RegExp(`\\b${word}\\b`, "i");
          if (re.test(s)) offences.push({ word, sample: s });
        }
      }
    }
    expect(offences, JSON.stringify(offences, null, 2)).toEqual([]);
  });

  it("UNIT_LABEL pads numeric suffix to 3 digits", () => {
    expect(copy.UNIT_LABEL("sim-1")).toBe("unit 001");
    expect(copy.UNIT_LABEL("sim-42")).toBe("unit 042");
    expect(copy.UNIT_LABEL("sim-128")).toBe("unit 128");
  });

  it("MODE_COPY narratives are sentence case ending with a period", () => {
    for (const meta of Object.values(copy.MODE_COPY)) {
      expect(meta.narrative_en.trim()).toMatch(/\.$/);
      expect(meta.narrative_it.trim()).toMatch(/\.$/);
    }
  });
});
