"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE_URL } from "@/constants";
import type { SetupStatus } from "./types";

type SetupState =
  | { phase: "loading" }
  | { phase: "configured" }
  | { phase: "wizard"; callbackUrl: string }
  | { phase: "error"; message: string };

export function useSetup() {
  const [state, setState] = useState<SetupState>({ phase: "loading" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE_URL}/api/setup/status`);
        if (!res.ok) throw new Error(`${res.status}`);
        const data: SetupStatus = await res.json();
        if (cancelled) return;
        if (data.configured) {
          setState({ phase: "configured" });
        } else {
          setState({ phase: "wizard", callbackUrl: data.callback_url });
        }
      } catch (e) {
        if (cancelled) return;
        setState({
          phase: "error",
          message: "セットアップ状態の取得に失敗しました。バックエンドが起動しているか確認してください。",
        });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = useCallback(
    async (clientId: string, clientSecret: string): Promise<void> => {
      const res = await fetch(`${API_BASE_URL}/api/setup/github`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: clientId, client_secret: clientSecret }),
      });
      if (!res.ok) {
        let detail = `${res.status} ${res.statusText}`;
        try {
          const data = await res.json();
          if (typeof data.detail === "string") detail = data.detail;
        } catch {
          // JSONでないエラーはステータス文字列のまま
        }
        throw new Error(detail);
      }
    },
    [],
  );

  return { state, submit };
}
