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

  
  const TICK_MS = 600;
  const TICK_STEP = 1.2; 
  
  const LOOKAHEAD = 8;
  let tickHandle: ReturnType<typeof setInterval> | null = null;

  if (options.onProgress) {
    tickHandle = setInterval(() => {
     
      const cap = Math.min(92, backendProgress + LOOKAHEAD);
      if (displayProgress < cap) {
        displayProgress = Math.min(cap, displayProgress + TICK_STEP);
        emit(displayProgress);
      }
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
