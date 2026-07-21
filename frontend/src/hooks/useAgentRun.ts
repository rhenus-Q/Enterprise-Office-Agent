/**
 * The request lifecycle: idle -> loading -> (success | error).
 *
 * Degraded and unsupported are not separate phases — they are classifications of
 * a successful response (see `classifyRunStatus`), because the engine returned a
 * real result in both cases.
 */

import { useCallback, useEffect, useRef, useState } from 'react';

import { AgentApiError, isCancellation, type AgentClient } from '../api/client';
import type { AgentRunResponse, RunOptions } from '../types/api';

/**
 * The settings snapshot a run was submitted with.
 *
 * Held in run state rather than read from the live controls, so changing a
 * control mid-run cannot affect the request already in flight, and Retry can
 * reproduce the original run exactly.
 */
export type RunOptionsSnapshot = RunOptions | null;

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
  | {
      phase: 'loading';
      text: string;
      previous: AgentRunResponse | null;
      options: RunOptionsSnapshot;
    }
  | { phase: 'success'; text: string; response: AgentRunResponse; options: RunOptionsSnapshot }
  /**
   * The user pressed Stop. `previous` carries the same result the loading phase
   * was holding, so a stopped retry lands back on the result it started from and
   * a stopped new request lands on the neutral stopped state.
   *
   * This describes the browser only: it stopped waiting. Server-side work that
   * had already begun is not interrupted by it.
   */
  | {
      phase: 'stopped';
      text: string;
      previous: AgentRunResponse | null;
      options: RunOptionsSnapshot;
    }
  | { phase: 'error'; text: string; errorType: string; options: RunOptionsSnapshot };

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
   *
   * `options` is the settings snapshot for this run. It is captured into state
   * here and sent verbatim, so later control changes cannot reach a request
   * that has already started.
   */
  const run = useCallback(
    async (
      text: string,
      { isRetry = false, options = null }: { isRetry?: boolean; options?: RunOptionsSnapshot } = {},
    ) => {
      // A replacement supersedes whatever was in flight, rather than racing it.
      abortActive();

      const requestId = latestRequestRef.current;
      const controller = new AbortController();
      controllerRef.current = controller;

      setState((current) => ({
        phase: 'loading',
        text,
        previous: isRetry && current.phase === 'success' ? current.response : null,
        options,
      }));

      try {
        // `options` is omitted entirely when null, so a run with no per-run
        // settings sends the original request body and the backend keeps its
        // existing behavior.
        const request = options === null ? { text } : { text, options };
        const response = await client.run(request, { signal: controller.signal });
        if (latestRequestRef.current === requestId) {
          setState({ phase: 'success', text, response, options });
          setCompletedRuns((count) => count + 1);
        }
      } catch (error) {
        // Superseded or stopped: `stop()` and `run()` already own the next
        // state, so a cancellation must never overwrite it with an error card.
        if (latestRequestRef.current !== requestId || isCancellation(error)) {
          return;
        }
        setState({ phase: 'error', text, errorType: toErrorType(error), options });
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
        ? {
            phase: 'stopped',
            text: current.text,
            previous: current.previous,
            options: current.options,
          }
        : current,
    );
  }, [abortActive]);

  const reset = useCallback(() => {
    abortActive();
    setState({ phase: 'idle' });
  }, [abortActive]);

  return { state, run, stop, reset, completedRuns };
}
