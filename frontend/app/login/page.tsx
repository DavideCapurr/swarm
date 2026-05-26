"use client";

/**
 * SWARM Console — login surface (Phase 6.C).
 *
 * Single-column card; design-system compliant (monochrome + Orbital Blue
 * focus, no red, no decorative shadow, no external icon kit). The TOTP
 * field appears only when the operator's account requires MFA — the
 * Console doesn't know the role until the first attempt comes back, so
 * we surface the field opportunistically.
 */

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";

import { useAuth, type LoginError } from "@/lib/auth";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/";
  const { state, login } = useAuth();
  const [operatorId, setOperatorId] = useState("");
  const [password, setPassword] = useState("");
  const [totpCode, setTotpCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<LoginError | null>(null);
  const [showTotp, setShowTotp] = useState(false);

  useEffect(() => {
    if (state.status === "authenticated") {
      router.replace(next);
    }
  }, [state, router, next]);

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    setError(null);
    const err = await login({
      operatorId: operatorId.trim(),
      password,
      totpCode: totpCode.trim() || undefined,
    });
    setBusy(false);
    if (err === null) {
      // navigation handled by the effect once state flips
      return;
    }
    setError(err);
    // Surface the TOTP field after the first invalid attempt so a
    // commander can supply the code without us leaking the role of the
    // operator id.
    if (err === "invalid_credentials") setShowTotp(true);
  }

  return (
    <main className="min-h-screen bg-absolute-black flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="flex items-center gap-2 mb-8">
          <span className="swarm-ring" style={{ width: 8, height: 8 }} />
          <span className="swarm-wordmark text-platinum" style={{ fontSize: 13 }}>
            SWARM
          </span>
          <span className="eyebrow-mono text-muted-silver">/ sign in</span>
        </div>
        <form onSubmit={onSubmit} className="card p-6 flex flex-col gap-4" noValidate>
          <label className="flex flex-col gap-1">
            <span className="eyebrow-mono text-ash">operator id</span>
            <input
              type="text"
              autoCapitalize="off"
              autoCorrect="off"
              autoComplete="username"
              required
              maxLength={64}
              value={operatorId}
              onChange={(e) => setOperatorId(e.target.value)}
              placeholder="op-…"
              className="bg-absolute-black border border-graphite rounded-input p-3 text-platinum focus:outline-none focus:border-orbital-blue mono-num"
              data-testid="login-operator-id"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow-mono text-ash">password</span>
            <input
              type="password"
              required
              autoComplete="current-password"
              maxLength={512}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="bg-absolute-black border border-graphite rounded-input p-3 text-platinum focus:outline-none focus:border-orbital-blue"
              data-testid="login-password"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="eyebrow-mono text-ash">
              totp code
              <span className="text-muted-silver"> · commander only</span>
            </span>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]{6}"
              maxLength={6}
              autoComplete="one-time-code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value.replace(/[^0-9]/g, ""))}
              placeholder={showTotp ? "6-digit code" : "leave blank for viewer / operator"}
              className="bg-absolute-black border border-graphite rounded-input p-3 text-platinum focus:outline-none focus:border-orbital-blue mono-num"
              data-testid="login-totp"
            />
          </label>
          {error && (
            <div
              role="alert"
              className="border border-launch-amber rounded-input p-3 text-launch-amber eyebrow-mono"
              data-testid="login-error"
            >
              {errorCopy(error)}
            </div>
          )}
          <button
            type="submit"
            disabled={busy || !operatorId.trim() || !password}
            className="bg-platinum text-absolute-black font-display text-ui rounded-input py-3 px-4 transition-all duration-press ease-swarm hover:brightness-105 active:scale-[0.99] disabled:opacity-40 disabled:cursor-not-allowed"
            data-testid="login-submit"
          >
            {busy ? "signing in…" : "sign in"}
          </button>
          <p className="eyebrow-mono text-ash">
            sessions expire after 15 minutes · re-auth happens silently
          </p>
        </form>
      </div>
    </main>
  );
}

function errorCopy(err: LoginError): string {
  switch (err) {
    case "invalid_credentials":
      return "credentials rejected · check operator id, password, and totp";
    case "rate_limited":
      return "too many attempts · wait a minute before trying again";
    case "service_unavailable":
      return "auth service unavailable · contact ops";
    case "network":
      return "network unreachable · check connectivity";
  }
}

export default function LoginPage() {
  // useSearchParams() requires a Suspense boundary at build time.
  return (
    <Suspense fallback={<main className="min-h-screen bg-absolute-black" />}>
      <LoginInner />
    </Suspense>
  );
}
