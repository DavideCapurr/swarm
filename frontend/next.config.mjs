/**
 * Next.js config for the SWARM Console.
 *
 * Security headers mirror what the backend's SecurityHeadersMiddleware emits
 * on every API response (see backend/app/security.py). They are applied to
 * every Console route via `headers()` below.
 *
 * The CSP allows:
 *   - script-src 'self' — no inline scripts; Next 15 builds with hashed
 *     chunks.
 *   - style-src 'self' 'unsafe-inline' — Tailwind emits inline style attrs
 *     for hover/transition utilities. Tighten to nonce-based in Phase 6.
 *   - img-src 'self' data: blob: https: — MapLibre raster basemap (CartoDB)
 *     + inline SVG icons. We tighten to specific hostnames when we self-host
 *     tiles.
 *   - connect-src 'self' ws: wss: — same-origin REST + WS to SwarmOS.
 *
 * X-Frame-Options + frame-ancestors close the door on clickjacking.
 */

const CSP = [
  "default-src 'self'",
  "base-uri 'self'",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "object-src 'none'",
  "connect-src 'self' ws: wss:",
  "img-src 'self' data: blob: https:",
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self'",
  "font-src 'self' data:",
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
