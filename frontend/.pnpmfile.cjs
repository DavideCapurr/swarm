function readPackage(pkg) {
  if (pkg.name === "next" && pkg.dependencies?.postcss === "8.4.31") {
    pkg.dependencies.postcss = "^8.5.14";
  }
  // Security: keep the (test-only, via jsdom) undici off the <7.28.0 advisory
  // band (GHSA-vxpw-j846-p89q et al.) while staying on the 7.x major jsdom
  // expects. Mirrors the `undici` entry in package.json pnpm.overrides.
  if (pkg.dependencies?.undici) {
    pkg.dependencies.undici = "^7.28.0";
  }
  if (pkg.devDependencies?.undici) {
    pkg.devDependencies.undici = "^7.28.0";
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage,
  },
};
