function readPackage(pkg) {
  if (pkg.name === "next" && pkg.dependencies?.postcss === "8.4.31") {
    pkg.dependencies.postcss = "^8.5.18";
  }
  // Security: keep the (test-only, via jsdom) undici off the advisory band
  // while staying on the 7.x major jsdom expects. Mirrors the `undici`
  // entry in pnpm-workspace.yaml `overrides`.
  if (pkg.dependencies?.undici) {
    pkg.dependencies.undici = "^7.29.0";
  }
  if (pkg.devDependencies?.undici) {
    pkg.devDependencies.undici = "^7.29.0";
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage,
  },
};
