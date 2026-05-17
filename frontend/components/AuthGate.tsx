"use client";

/**
 * AuthGate — redirect to /login when the operator is not authenticated.
 *
 * Renders nothing while auth is hydrating from localStorage so we don't
 * flash the Console layout before kicking the user out, and we don't
 * stack pushes to /login on re-renders while loading.
 */

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";

import { useAuth } from "@/lib/auth";

export function AuthGate({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (state.status === "anonymous") {
      const next = pathname && pathname !== "/login" ? `?next=${encodeURIComponent(pathname)}` : "";
      router.replace(`/login${next}`);
    }
  }, [state.status, pathname, router]);

  if (state.status !== "authenticated") {
    return (
      <main className="min-h-screen bg-absolute-black flex items-center justify-center">
        <span className="eyebrow-mono text-ash">linking session…</span>
      </main>
    );
  }
  return <>{children}</>;
}
