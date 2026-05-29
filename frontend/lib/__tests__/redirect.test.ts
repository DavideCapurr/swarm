import { describe, expect, it } from "vitest";

import { safeInternalRedirect } from "@/lib/redirect";

describe("safeInternalRedirect", () => {
  it("allows relative app paths", () => {
    expect(safeInternalRedirect("/console")).toBe("/console");
    expect(safeInternalRedirect("/console?tab=fleet#unit")).toBe(
      "/console?tab=fleet#unit"
    );
  });

  it("falls back for external or protocol-relative URLs", () => {
    expect(safeInternalRedirect("https://evil.example")).toBe("/");
    expect(safeInternalRedirect("//evil.example")).toBe("/");
  });

  it("falls back for backslash host tricks", () => {
    // The URL parser normalizes "\" to "/" for special schemes, so these
    // would resolve to an external origin if the origin check were skipped.
    expect(safeInternalRedirect("/\\evil.example")).toBe("/");
    expect(safeInternalRedirect("/\\/evil.example")).toBe("/");
    expect(safeInternalRedirect("/\\\\evil.example")).toBe("/");
  });

  it("falls back for empty input", () => {
    expect(safeInternalRedirect(null)).toBe("/");
    expect(safeInternalRedirect("")).toBe("/");
    expect(safeInternalRedirect("   ")).toBe("/");
  });
});
