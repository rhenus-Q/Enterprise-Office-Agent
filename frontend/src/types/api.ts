/**
 * Typed frontend mirror of the Phase 2 API contract (spec §8.2 / §8.3).
 *
 * This file is the single source of truth the mocks, components, and tests must
 * satisfy. Every field name here matches the planned Pydantic models exactly, so
 * Phase 3 can swap the mock client for the HTTP client without touching types.
 *
 * Honesty rules encoded here:
 * - `duration_ms` is ADAPTER-MEASURED (wall clock around the engine call), not
 *   engine telemetry.
 * - `execution_mode` is ADAPTER-DERIVED (a presentation classification), not a
 *   field any engine reports.
 * - `observability` is populated for Knowledge Q&A only, and only from real
 *   `enterprise_rag` AnswerResult metadata. It is never fabricated for the
 *   deterministic capabilities.
 */

/** Routed intents produced by the deterministic Office Agent router. */
export type Intent =
  | 'knowledge_qa'
  | 'email_summary'
  | 'calendar_lookup'
  | 'ticket_assistant'
  | 'daily_briefing'
  | 'meeting_agent'
  | 'workflow_approval'
  | 'unknown';

/** Every capability that maps to a tool (i.e. every intent except `unknown`). */
export type CapabilityIntent = Exclude<Intent, 'unknown'>;

/**
 * `stop_reason` values. The empty string means a normal finish.
 *
 * The first eleven come from `enterprise_rag/graph/consts.py`; `llm_assist_error`
 * is the office-only value from `office_agent/llm_assist/config.py`.
 */
export type StopReason =
  | ''
  | 'web_search_disabled'
  | 'web_fallback_disabled'
  | 'max_retries_not_grounded'
  | 'max_retries_not_useful'
  | 'budget_exhausted'
  | 'offline_mode'
  | 'retrieval_error'
  | 'web_search_error'
  | 'generation_error'
  | 'tool_error'
  | 'llm_assist_error';

/** Adapter-derived execution classification (spec §8.2 matrix). */
export type ExecutionMode =
  | 'none'
  | 'deterministic'
  | 'llm_assisted'
  | 'llm_assist_fallback'
  | 'rag_llm'
  | 'rag_blocked_offline';

/** One graph step's wall-clock timing, aligned 1:1 with the Python NodeTiming. */
export interface NodeTiming {
  node: string;
  duration_ms: number;
}

/**
 * Knowledge Q&A observability — genuinely available `AnswerResult` metadata only.
 *
 * `tracked_llm_calls` is the budgeted operational counter, NOT total LLM usage,
 * so the UI must label it "tracked".
 */
export interface KnowledgeObservability {
  run_id: string | null;
  node_path: string[];
  node_timings_ms: NodeTiming[];
  total_duration_ms: number;
  retries: number;
  tracked_llm_calls: number;
  web_search_count: number;
  web_result_grading_count: number;
  web_search_enabled: boolean;
  web_fallback_policy: string;
  caveat: string;
}

/** Per-request privacy level. `strict` restricts this run only. */
export type RunPrivacyMode = 'standard' | 'strict';

/**
 * What the user selected in the Run Settings controls.
 *
 * These are *requests*. The backend resolves them against server policy, which
 * always wins — a request can make a run stricter, never more permissive.
 */
export interface RunOptions {
  privacy_mode: RunPrivacyMode;
  llm_assist: boolean;
  web_search: boolean;
}

/** One coherent set of settings — used for both requested and effective. */
export interface RunSettingsValues {
  privacy_mode: RunPrivacyMode;
  llm_assist: boolean;
  web_search: boolean;
}

/**
 * Whether each optional path applies to the routed capability.
 *
 * `false` means "not applicable to this capability" and must be displayed as
 * such — never as though the setting had been used.
 */
export interface RunSettingsApplicability {
  llm_assist: boolean;
  web_search: boolean;
}

/**
 * Typed reasons why `requested` and `effective` differ. Stable identifiers that
 * the UI maps to text — the frontend never invents its own explanation.
 */
export type RunConstraint =
  | 'server_offline_mode'
  | 'server_privacy_mode'
  | 'request_privacy_strict'
  | 'server_llm_assist_disabled'
  | 'server_web_search_disabled'
  | 'llm_assist_not_applicable'
  | 'web_search_not_applicable';

/**
 * The backend's authoritative account of one run's settings.
 *
 * `effective` is computed by the backend and displayed verbatim. The frontend
 * must never re-derive it, and must never infer it from badge text or rendered
 * DOM content.
 */
export interface RunSettings {
  requested: RunSettingsValues;
  effective: RunSettingsValues;
  applicability: RunSettingsApplicability;
  constraints: RunConstraint[];
}

export interface AgentRunRequest {
  text: string;
  /** Omitted entirely when the caller has no per-run settings to send. */
  options?: RunOptions;
}

export interface AgentRunResponse {
  intent: Intent;
  tool: string | null;
  content: string;
  stop_reason: StopReason;
  sources: string[];
  run_id: string | null;
  duration_ms: number;
  execution_mode: ExecutionMode;
  observability: KnowledgeObservability | null;
  /** Null when the request carried no `options`. */
  run_settings: RunSettings | null;
}

export interface HealthResponse {
  status: 'ok';
  privacy_mode: boolean;
  offline_mode: boolean;
  office_llm_enabled: boolean;
  /** Effective, mode-aware web-search state — never a raw config echo. */
  web_search_effective: boolean;
}

/** Presentation-only run classification (spec §8.4). */
export type RunStatus = 'success' | 'degraded' | 'unsupported' | 'error';

/**
 * Exact request-text bound enforced by the Phase 2 Pydantic model
 * (`min_length=1`, `max_length=4000`). Mirrored here so the composer cannot
 * submit input the API would reject with a 422.
 */
export const MAX_REQUEST_TEXT_LENGTH = 4000;
