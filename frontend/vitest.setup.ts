/**
 * Vitest setup — runs before every test file.
 *
 * Pulls in `@testing-library/jest-dom` matchers (toBeInTheDocument,
 * toBeDisabled, …) and resets per-test side-effects.
 */

import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => {
  cleanup();
  if (typeof window !== "undefined") {
    window.localStorage.clear();
    window.sessionStorage.clear();
  }
});
