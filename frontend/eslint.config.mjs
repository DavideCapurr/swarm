import { FlatCompat } from "@eslint/eslintrc";
import securityPlugin from "eslint-plugin-security";

const compat = new FlatCompat({
  baseDirectory: import.meta.dirname,
});

export default [
  { ignores: [".next/**", "node_modules/**"] },
  ...compat.extends("next/core-web-vitals"),
  {
    plugins: { security: securityPlugin },
    rules: {
      // Core OWASP-style checks. Tuned to surface real issues without
      // false-positive noise on the existing typed surface.
      "security/detect-eval-with-expression": "error",
      "security/detect-new-buffer": "error",
      "security/detect-no-csrf-before-method-override": "error",
      "security/detect-non-literal-fs-filename": "warn",
      "security/detect-non-literal-regexp": "warn",
      "security/detect-pseudoRandomBytes": "error",
      "security/detect-unsafe-regex": "error",
      // React already escapes by default; this catches manual escapes.
      "security/detect-disable-mustache-escape": "error",
    },
  },
];
