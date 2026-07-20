/**
 * The request lifecycle: idle -> loading -> (success | error).
 *
 * Degraded and unsupported are not separate phases — they are classifications of
 * a successful response (see `classifyRunStatus`), because the engine returned a
 * real result in both cases.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { AgentApiError, isCancellation, type AgentClient } from '../api/client';
import type { AgentRunResponse } from '../types/api';

export type RunState =
  | { phase: 'idle' }
  /**
   * `previous` carries the result that was on screen when the run started, so a
   * retry can keep showing it instead of blanking the results area.
   *
   * It is populated for retries **only**. A new request produces a result with a
   * different identity — potentially a different capability entirely, which the
   * frontend cannot predict because routing belongs to the backend — so holding
   * the old card in place would misreport what is being run.
   */
  | { phase: 'loading'; text: string; previous: AgentRunResponse | null }
  | { phase: 'success'; text: string; response: AgentRunResponse }
  /**
   * The user pressed Stop. `previous` carries the same result the loading phase
   * was holding, so a stopped retry lands back on the result it started from and
   * a stopped new request lands on the neutral stopped state.
   *
   * This describes the browser only: it stopped waiting. Server-side work that
   * had already begun is not interrupted by it.
   */
  | { phase: 'stopped'; text: string; previous: AgentRunResponse | null }
  | { phase: 'error'; text: string; errorType: string };

function toErrorType(error: unknown): string {
  if (error instanceof AgentApiError) {
    return error.errorType;
  }
  if (error instanceof Error) {
    // Type name only — messages may carry paths or secrets.
    return error.name;
  }
  return 'UnknownError';
}

export function useAgentRun(client: AgentClient) {
  const [state, setState] = useState<RunState>({ phase: 'idle' });
  /**
   * Counts completed runs. A UI-side nonce only — it exists so the result can
   * replay its entry animation when a rerun returns an identical response, and
   * it is never presented as engine data.
   */
  const [completedRuns, setCompletedRuns] = useState(0);
  // Guards against an earlier slow request overwriting a newer one. Bumping it
  // is what makes a late response inert, whatever the reason it is late.
  const latestRequestRef = useRef(0);
  // The in-flight call's abort handle, so it can be dropped on stop, on reset,
  // when a replacement run starts, and on unmount.
  const controllerRef = useRef<AbortController | null>(null);

  /** Invalidate the in-flight run and stop the browser waiting for it. */
  const abortActive = useCallback(() => {
    latestRequestRef.current += 1;
    controllerRef.current?.abort();
    controllerRef.current = null;
  }, []);

  // A pending request outlives the component otherwise.
  useEffect(() => abortActive, [abortActive]);

  /**
   * Start a run.
   *
   * `isRetry` is the single source of truth for "this run targets the result
   * already on screen". It is passed explicitly rather than inferred, because
   * only the caller knows whether the user pressed Run or Retry.
   */
  const run = useCallback(
    async (text: string, { isRetry = false }: { isRetry?: boolean } = {}) => {
      // A replacement supersedes whatever was in flight, rather than racing it.
      abortActive();

      const requestId = latestRequestRef.current;
      const controller = new AbortController();
      controllerRef.current = controller;

      setState((current) => ({
        phase: 'loading',
        text,
        previous: isRetry && current.phase === 'success' ? current.response : null,
      }));

      try {
        const response = await client.run({ text }, { signal: controller.signal });
        if (latestRequestRef.current === requestId) {
          setState({ phase: 'success', text, response });
          setCompletedRuns((count) => count + 1);
        }
      } catch (error) {
        // Superseded or stopped: `stop()` and `run()` already own the next
        // state, so a cancellation must never overwrite it with an error card.
        if (latestRequestRef.current !== requestId || isCancellation(error)) {
          return;
        }
        setState({ phase: 'error', text, errorType: toErrorType(error) });
      } finally {
        if (controllerRef.current === controller) {
          controllerRef.current = null;
        }
      }
    },
    [abortActive, client],
  );

  /**
   * Stop waiting for the in-flight run.
   *
   * A stopped retry returns to the result it was refreshing; a stopped new
   * request has nothing to return to, so it lands on the stopped state.
   */
  const stop = useCallback(() => {
    abortActive();
    setState((current) =>
      current.phase === 'loading'
        ? { phase: 'stopped', text: current.text, previous: current.previous }
        : current,
    );
  }, [abortActive]);

  const reset = useCallback(() => {
    abortActive();
    setState({ phase: 'idle' });
  }, [abortActive]);

  return { state, run, stop, reset, completedRuns };
}
