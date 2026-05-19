/// <reference types="vitest" />

/**
 * Vitest config — Phase 6.J critical-path coverage.
 *
 * The roadmap requires 70% coverage on the frontend critical path
 * only — auth, API surface, and the safety-critical components.
 * `coverage.include` lists those files explicitly so the gate
 * measures the SUT, not the whole UI tree.
 *
 * Coverage runner is v8 (`@vitest/coverage-v8`) because it doesn't
 * require Babel instrumentation and works cleanly with Next 16 +
 * React 19 + TypeScript.
 */

import { defineConfig } from "vitest/config";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  resolve: {
    alias: {
      "@": resolve(here, "."),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: [
      "lib/**/*.test.ts",
      "lib/**/*.test.tsx",
      "components/**/*.test.ts",
      "components/**/*.test.tsx",
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "json-summary"],
      include: [
        "lib/auth.tsx",
        "lib/api.ts",
        "lib/ws.ts",
        "components/EmergencyStop.tsx",
        "components/AuthGate.tsx",
      ],
      thresholds: {
        lines: 70,
        functions: 70,
        statements: 70,
        branches: 60,
      },
    },
  },
});
