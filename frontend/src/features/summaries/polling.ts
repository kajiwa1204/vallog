import type { SummaryJob } from "@/types";

export const POLL_INTERVAL_MS = 3000;
export const MAX_CONSECUTIVE_POLL_FAILURES = 3;
export const MAX_POLL_DURATION_MS = 15 * 60 * 1000;

export function pollingDelay(consecutiveFailures: number): number {
  return Math.min(POLL_INTERVAL_MS * 2 ** consecutiveFailures, 30000);
}

export function activeJobStartedAt(jobs: SummaryJob[]): number | null {
  const timestamps = jobs
    .filter((job) => job.status === "pending" || job.status === "running")
    .map((job) => Date.parse(job.created_at))
    .filter(Number.isFinite);
  return timestamps.length > 0 ? Math.min(...timestamps) : null;
}
