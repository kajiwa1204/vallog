"use client";

import { useEffect } from "react";
import {
  MAX_CONSECUTIVE_POLL_FAILURES,
  MAX_POLL_DURATION_MS,
  POLL_INTERVAL_MS,
  pollingDelay,
} from "./polling";

type Options = {
  enabled: boolean;
  startedAt: number | null;
  refresh: () => Promise<boolean>;
  onStopped: (message: string) => void;
};

/** 応答完了後に次回を予約し、多重実行せず生成状況を更新する。 */
export function useSummaryPolling({
  enabled,
  startedAt,
  refresh,
  onStopped,
}: Options) {
  useEffect(() => {
    if (!enabled || startedAt === null) return;

    let cancelled = false;
    let timer: number | undefined;
    let consecutiveFailures = 0;

    const schedule = (delay: number) => {
      timer = window.setTimeout(poll, delay);
    };
    const poll = async () => {
      if (Date.now() - startedAt >= MAX_POLL_DURATION_MS) {
        onStopped(
          "生成状況の確認を15分で停止しました。生成をやり直すか、再読み込みしてください。",
        );
        return;
      }

      const succeeded = await refresh();
      if (cancelled) return;

      consecutiveFailures = succeeded ? 0 : consecutiveFailures + 1;
      if (consecutiveFailures >= MAX_CONSECUTIVE_POLL_FAILURES) {
        onStopped(
          "生成状況を繰り返し取得できなかったため、確認を停止しました。接続を確認して再読み込みしてください。",
        );
        return;
      }
      schedule(pollingDelay(consecutiveFailures));
    };

    schedule(POLL_INTERVAL_MS);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, [enabled, startedAt, refresh, onStopped]);
}
