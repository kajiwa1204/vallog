"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { api, refreshSession, setAccessToken } from "@/lib/api";
import type { User } from "@/types";

type AuthState =
  | { status: "loading"; user: null }
  | { status: "authenticated"; user: User }
  | { status: "unauthenticated"; user: null };

export function useAuth({ required = true }: { required?: boolean } = {}) {
  const [state, setState] = useState<AuthState>({
    status: "loading",
    user: null,
  });
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const session = await refreshSession();
      if (cancelled) return;
      if (session) {
        setState({ status: "authenticated", user: session.user });
      } else {
        setState({ status: "unauthenticated", user: null });
        if (required) router.replace("/");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [required, router]);

  const logout = useCallback(async () => {
    await api.post("/auth/logout");
    setAccessToken(null);
    router.replace("/");
  }, [router]);

  return { ...state, logout };
}
