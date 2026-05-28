export function safeInternalRedirect(
  value: string | null | undefined,
  fallback = "/"
): string {
  const candidate = value?.trim() ?? "";
  if (!candidate || !candidate.startsWith("/") || candidate.startsWith("//")) {
    return fallback;
  }
  try {
    const parsed = new URL(candidate, "https://swarm.local");
    if (parsed.origin !== "https://swarm.local") return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}` || fallback;
  } catch {
    return fallback;
  }
}
