"use client";

/**
 * SWARM Console — auth provider.
 *
 * Phase 6.C: pure JWT (access + refresh) issued by SwarmOS, role-based
 * authorisation enforced server-side. The Console:
 *
 *   1. Hydrates from `localStorage` on boot so a refresh doesn't sign
 *      the operator out.
 *   2. Calls `/auth/login` (with TOTP for commander) and stores the
 *      tokens returned.
 *   3. Attaches `Authorization: Bearer <access>` on every REST call.
 *   4. Sends the access token as a query param on the WS upgrade so the
 *      browser API constraint (no custom WS headers) doesn't block us.
 *   5. Refreshes proactively before the access token expires.
 *   6. Logs out on hard 401 (revocation / expiry / store demotion).
 *
 * Storage caveat (documented in `docs/security/auth.md`): we keep the
 * access token in localStorage. CSP restricts script-src to `'self'`, no
 * external scripts run, the access TTL is 15 min, and the refresh
 * rotates on every use. Moving the refresh token to an HttpOnly cookie
 * is the documented Phase 6.E hardening pass — it requires CSRF +
 * SameSite + a server-side cookie issuer pipe that's out of scope for
 * 6.C.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { api, AUTH_API_URL } from "./api";

// ── Types ──────────────────────────────────────────────────────────────────────

export type Role = "viewer" | "operator" | "commander";

export type Session = {
  accessToken: string;
  refreshToken: string;
  expiresAt: number; // wall-clock ms — when the *access* token expires
  role: Role;
  operatorId: string;
  siteId: string;
  mfa: boolean;
};

type AuthState =
  | { status: "loading"; session: Session | null }
  | { status: "anonymous"; session: null }
  | { status: "authenticated"; session: Session };

type Action =
  | { type: "boot"; session: Session | null }
  | { type: "login"; session: Session }
  | { type: "logout" };

type LoginInput = {
  operatorId: string;
  password: string;
  totpCode?: string;
};

export type LoginError =
  | "invalid_credentials"
  | "rate_limited"
  | "service_unavailable"
  | "network";

export type AuthContextValue = {
  state: AuthState;
  login: (input: LoginInput) => Promise<LoginError | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

const STORAGE_KEY = "swarm.session.v1";
const REFRESH_LEEWAY_S = 60; // refresh 60s before access expires

// ── Storage helpers ────────────────────────────────────────────────────────────

function readSession(): Session | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (
      typeof parsed.accessToken !== "string" ||
      typeof parsed.refreshToken !== "string" ||
      typeof parsed.expiresAt !== "number" ||
      typeof parsed.role !== "string" ||
      typeof parsed.operatorId !== "string"
    ) {
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

function writeSession(session: Session | null): void {
  if (typeof window === "undefined") return;
  if (session === null) {
    window.localStorage.removeItem(STORAGE_KEY);
    return;
  }
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
}

function tokenToSession(payload: {
  access_token: string;
  refresh_token: string;
  expires_in: number;
  role: Role;
  operator_id: string;
  site_id: string;
  mfa: boolean;
}): Session {
  return {
    accessToken: payload.access_token,
    refreshToken: payload.refresh_token,
    expiresAt: Date.now() + payload.expires_in * 1000,
    role: payload.role,
    operatorId: payload.operator_id,
    siteId: payload.site_id,
    mfa: payload.mfa,
  };
}

// ── Provider ───────────────────────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading", session: null });
  const sessionRef = useRef<Session | null>(null);
  sessionRef.current = state.session;
  // Track in-flight refresh so concurrent callers share one network round trip.
  const refreshInFlight = useRef<Promise<Session | null> | null>(null);

  // Hydrate from localStorage exactly once.
  useEffect(() => {
    const saved = readSession();
    if (saved && saved.expiresAt > Date.now() + 1_000) {
      setState({ status: "authenticated", session: saved });
    } else if (saved) {
      // Have a refresh? Try a silent refresh. Else, anonymous.
      void silentRefresh(saved).then((next) => {
        if (next) {
          setState({ status: "authenticated", session: next });
        } else {
          writeSession(null);
          setState({ status: "anonymous", session: null });
        }
      });
    } else {
      setState({ status: "anonymous", session: null });
    }
  }, []);

  // Proactively refresh tokens before expiry.
  useEffect(() => {
    if (state.status !== "authenticated") return;
    const session = state.session;
    const msUntilRefresh = Math.max(
      1_000,
      session.expiresAt - Date.now() - REFRESH_LEEWAY_S * 1_000
    );
    const id = window.setTimeout(() => {
      void silentRefresh(session).then((next) => {
        if (next) {
          writeSession(next);
          setState({ status: "authenticated", session: next });
        } else {
          writeSession(null);
          setState({ status: "anonymous", session: null });
        }
      });
    }, msUntilRefresh);
    return () => window.clearTimeout(id);
  }, [state]);

  async function silentRefresh(session: Session): Promise<Session | null> {
    if (refreshInFlight.current) return refreshInFlight.current;
    const p = (async () => {
      try {
        const r = await fetch(`${AUTH_API_URL}/auth/refresh`, {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: session.refreshToken }),
        });
        if (!r.ok) return null;
        const body = await r.json();
        return tokenToSession(body);
      } catch {
        return null;
      } finally {
        refreshInFlight.current = null;
      }
    })();
    refreshInFlight.current = p;
    return p;
  }

  const login = useCallback(
    async (input: LoginInput): Promise<LoginError | null> => {
      try {
        const r = await fetch(`${AUTH_API_URL}/auth/login`, {
          method: "POST",
          cache: "no-store",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            operator_id: input.operatorId,
            password: input.password,
            totp_code: input.totpCode || undefined,
          }),
        });
        if (r.status === 200) {
          const body = await r.json();
          const session = tokenToSession(body);
          writeSession(session);
          setState({ status: "authenticated", session });
          return null;
        }
        if (r.status === 429) return "rate_limited";
        if (r.status === 503) return "service_unavailable";
        return "invalid_credentials";
      } catch {
        return "network";
      }
    },
    []
  );

  const logout = useCallback(async () => {
    const session = sessionRef.current;
    if (session) {
      try {
        await fetch(`${AUTH_API_URL}/auth/logout`, {
          method: "POST",
          cache: "no-store",
          headers: {
            Authorization: `Bearer ${session.accessToken}`,
            "X-Refresh-Token": session.refreshToken,
          },
        });
      } catch {
        /* best-effort */
      }
    }
    writeSession(null);
    setState({ status: "anonymous", session: null });
  }, []);

  // Wire the API client so it can read the current token and force a logout
  // on hard 401. This pattern keeps the API module React-free.
  useEffect(() => {
    api.setAuthHooks({
      getAccessToken: () => sessionRef.current?.accessToken ?? null,
      onUnauthorized: () => {
        writeSession(null);
        setState({ status: "anonymous", session: null });
      },
    });
    return () => api.setAuthHooks(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ state, login, logout }),
    [state, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside <AuthProvider>");
  }
  return ctx;
}

export function useSession(): Session | null {
  const { state } = useAuth();
  return state.status === "authenticated" ? state.session : null;
}

export function useRole(): Role | null {
  return useSession()?.role ?? null;
}

export function canDo(role: Role | null, required: Role): boolean {
  if (role === null) return false;
  const rank: Record<Role, number> = { viewer: 0, operator: 1, commander: 2 };
  return rank[role] >= rank[required];
}
