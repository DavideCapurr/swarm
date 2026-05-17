import { fileURLToPath } from "node:url";

/**
 * Next.js config for the SWARM Console.
 *
 * Security headers mirror what the backend's SecurityHeadersMiddleware emits
 * on every API response (see backend/app/security.py). They are applied to
 * every Console route via `headers()` below.
 *
 * The CSP allows:
 *   - script-src stays `self` in prod; dev allows Next/Turbopack inline/eval
 *     diagnostics so `make demo` remains interactive.
 *   - style-src 'self' 'unsafe-inline' — Tailwind emits inline style attrs
 *     for hover/transition utilities. Tighten to nonce-based in Phase 6.
 *   - img-src 'self' data: blob: https: — MapLibre raster basemap (CartoDB)
 *     + inline SVG icons. We tighten to specific hostnames when we self-host
 *     tiles.
 *   - connect-src allows same-origin plus the Phase 2 SwarmOS backend on
 *     port 8765 for localhost/LAN demos. Production should set explicit
 *     NEXT_PUBLIC_API_URL / NEXT_PUBLIC_WS_URL origins.
 *
 * X-Frame-Options + frame-ancestors close the door on clickjacking.
 */

const FRONTEND_ROOT = fileURLToPath(new URL(".", import.meta.url));

function originFromEnv(value) {
  if (!value) return null;
  try {
    return new URL(value).origin;
  } catch {
    return null;
  }
}

const DEV_CONNECT_SRC =
  process.env.SWARM_ENV === "prod"
    ? []
    : ["http://localhost:8765", "http://127.0.0.1:8765", "http://*:8765"];
const MAP_CONNECT_SRC = [
  "https://a.basemaps.cartocdn.com",
  "https://b.basemaps.cartocdn.com",
  "https://c.basemaps.cartocdn.com",
  "https://demotiles.maplibre.org",
];
const CONNECT_SRC = [
  "'self'",
  ...DEV_CONNECT_SRC,
  ...MAP_CONNECT_SRC,
  originFromEnv(process.env.NEXT_PUBLIC_API_URL),
  originFromEnv(process.env.NEXT_PUBLIC_WS_URL),
  "ws:",
  "wss:",
]
  .filter(Boolean)
  .filter((value, index, values) => values.indexOf(value) === index)
  .join(" ");
const SCRIPT_SRC =
  process.env.SWARM_ENV === "prod"
    ? "'self'"
    : "'self' 'unsafe-inline' 'unsafe-eval'";

const CSP = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "object-src 'none'",
  `connect-src ${CONNECT_SRC}`,
  "img-src 'self' data: blob: https:",
  "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
  `script-src ${SCRIPT_SRC}`,
  "font-src 'self' data: https://fonts.gstatic.com",
  "worker-src 'self' blob:",
].join("; ");

const SECURITY_HEADERS = [
  { key: "Content-Security-Policy", value: CSP },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "no-referrer" },
  {
    key: "Permissions-Policy",
    value: "geolocation=(), camera=(), microphone=(), payment=()",
  },
  { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  { key: "Cross-Origin-Resource-Policy", value: "same-origin" },
];

if (process.env.SWARM_ENV === "prod") {
  SECURITY_HEADERS.push({
    key: "Strict-Transport-Security",
    value: "max-age=63072000; includeSubDomains; preload",
  });
}

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  turbopack: {
    root: FRONTEND_ROOT,
  },
  env: {
    NEXT_PUBLIC_API_URL:
      process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765",
    NEXT_PUBLIC_WS_URL:
      process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:8765/ws/telemetry",
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: SECURITY_HEADERS,
      },
    ];
  },
};

export default nextConfig;
