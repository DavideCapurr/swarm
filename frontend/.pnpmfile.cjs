function readPackage(pkg) {
  if (pkg.name === "next" && pkg.dependencies?.postcss === "8.4.31") {
    pkg.dependencies.postcss = "^8.5.14";
  }
  return pkg;
}

module.exports = {
  hooks: {
    readPackage,
  },
};
