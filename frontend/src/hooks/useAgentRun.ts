/**
 * The request lifecycle: idle -> loading -> (success | error).
 *
 * Degraded and unsupported are not separate phases — they are classifications of
 * a successful response (see `classifyRunStatus`), because the engine returned a
 * real result in both cases.
 */

import { useCallback, useRef, useState } from 'react';

import { AgentApiError, type AgentClient } from '../api/client';
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
  // Guards against an earlier slow request overwriting a newer one.
  const latestRequestRef = useRef(0);

  /**
   * Start a run.
   *
   * `isRetry` is the single source of truth for "this run targets the result
   * already on screen". It is passed explicitly rather than inferred, because
   * only the caller knows whether the user pressed Run or Retry.
   */
  const run = useCallback(
    async (text: string, { isRetry = false }: { isRetry?: boolean } = {}) => {
      const requestId = latestRequestRef.current + 1;
      latestRequestRef.current = requestId;
      setState((current) => ({
        phase: 'loading',
        text,
        previous: isRetry && current.phase === 'success' ? current.response : null,
      }));

      try {
        const response = await client.run({ text });
        if (latestRequestRef.current === requestId) {
          setState({ phase: 'success', text, response });
          setCompletedRuns((count) => count + 1);
        }
      } catch (error) {
        if (latestRequestRef.current === requestId) {
          setState({ phase: 'error', text, errorType: toErrorType(error) });
        }
      }
    },
    [client],
  );

  const reset = useCallback(() => {
    latestRequestRef.current += 1;
    setState({ phase: 'idle' });
  }, []);

  return { state, run, reset, completedRuns };
}
