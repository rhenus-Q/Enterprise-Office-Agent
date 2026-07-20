/**
 * Presentation-only classification helpers.
 *
 * These decide how a response is *displayed*. They never reinterpret engine
 * semantics: `stop_reason` values are transported and shown verbatim, and the
 * human caveat text always comes from the engine (via `observability.caveat` or
 * the response `content`), never from a lookup table here.
 */

import type { AgentRunResponse, ExecutionMode, RunStatus } from '../types/api';

/**
 * Classify a returned response for display (spec §8.4).
 *
 * `unknown` is checked first: an unsupported request finishes normally (empty
 * `stop_reason`), so it would otherwise be indistinguishable from success.
 */
export function classifyRunStatus(response: AgentRunResponse): RunStatus {
  if (response.intent === 'unknown') {
    return 'unsupported';
  }
  if (response.stop_reason === '') {
    return 'success';
  }
  return 'degraded';
}

export const RUN_STATUS_LABELS: Record<RunStatus, string> = {
  success: 'Success',
  degraded: 'Degraded',
  unsupported: 'Unsupported',
  error: 'Error',
};

/**
 * Human labels for the adapter-derived execution mode. These name the execution
 * path the adapter classified; they are not engine telemetry and must always be
 * presented as adapter-derived.
 */
export const EXECUTION_MODE_LABELS: Record<ExecutionMode, string> = {
  none: 'No tool invoked',
  deterministic: 'Deterministic (no LLM)',
  llm_assisted: 'LLM-assisted',
  llm_assist_fallback: 'LLM assist failed — deterministic fallback',
  rag_llm: 'Enterprise RAG (LLM)',
  rag_blocked_offline: 'Blocked by OFFLINE_MODE (no LLM call)',
};

/** Format an adapter-measured duration for display. */
export function formatDurationMs(durationMs: number): string {
  if (durationMs < 1000) {
    return `${durationMs.toFixed(1)} ms`;
  }
  return `${(durationMs / 1000).toFixed(2)} s`;
}
