import { getJobStatus } from "@/lib/api";
import type { JobStatus } from "@/lib/types";

type PollJobOptions = {
  intervalMs?: number;
  timeoutMs: number;
  timeoutMessage: string;
  onProgress?: (progressPct: number) => void;
  
  onStatus?: (status: JobStatus) => void;
};

const DEFAULT_INTERVAL_MS = 2000;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}


export async function pollJobStatus(jobToken: string, options: PollJobOptions): Promise<JobStatus> {
  const intervalMs = options.intervalMs ?? DEFAULT_INTERVAL_MS;
  const deadline = Date.now() + options.timeoutMs;

  let backendProgress = 0;
  let displayProgress = 0;

  const emit = (pct: number) => options.onProgress?.(Math.round(Math.min(100, pct)));

  // Tick every 600 ms. Uses an exponential approach toward 90% so the bar
  // keeps moving even when the backend never reports intermediate progress
  // (e.g. Whisper stays at 0% until it finishes). Each tick closes 2.5% of
  // the remaining gap to the ceiling, giving a natural deceleration.
  const TICK_MS = 600;
  const CREEP_CEILING = 90;
  let tickHandle: ReturnType<typeof setInterval> | null = null;

  if (options.onProgress) {
    tickHandle = setInterval(() => {
      if (displayProgress < CREEP_CEILING) {
        const gap = CREEP_CEILING - displayProgress;
        displayProgress = Math.min(CREEP_CEILING, displayProgress + Math.max(0.15, gap * 0.025));
      }
      // Never let the display fall behind what the backend reported
      displayProgress = Math.max(displayProgress, backendProgress);
      emit(displayProgress);
    }, TICK_MS);
  }

  try {
    while (Date.now() < deadline) {
      await wait(intervalMs);
      const status = await getJobStatus(jobToken);

      backendProgress = status.progress_pct;
      options.onStatus?.(status);

     
      if (backendProgress > displayProgress) {
        displayProgress = backendProgress;
        emit(displayProgress);
      }

      if (status.status === "failed" || status.status === "complete") {
        
        displayProgress = status.progress_pct;
        emit(displayProgress);
        return status;
      }
    }
  } finally {
    if (tickHandle !== null) clearInterval(tickHandle);
  }

  throw new Error(options.timeoutMessage);
}
