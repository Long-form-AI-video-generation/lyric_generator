import { getJobStatus } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

type PollJobOptions = {
  intervalMs?: number;
  timeoutMs: number;
  timeoutMessage: string;
  onProgress?: (progressPct: number) => void;
};

const DEFAULT_INTERVAL_MS = 2000;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function pollJobStatus(jobToken: string, options: PollJobOptions): Promise<JobStatus> {
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  const deadline = Date.now() + options.timeoutMs;

  while (Date.now() < deadline) {
    await wait(intervalMs);
    const status = await getJobStatus(jobToken);
    options.onProgress?.(status.progress_pct);

    if (status.status === "failed" || status.status === "complete") {
      return status;
    }
  }

  throw new Error(options.timeoutMessage);
}

