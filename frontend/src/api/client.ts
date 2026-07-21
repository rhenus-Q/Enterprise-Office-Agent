/**
 * The client boundary between the UI and the Office Agent.
 *
 * Two implementations satisfy one `AgentClient` interface, so no component ever
 * knows which is active:
 *
 * - `createHttpClient` — the normal path. Talks to the Phase 2 FastAPI adapter
 *   through exactly two endpoints, `GET /api/health` and `POST /api/agent/run`.
 * - `createMockClient` — typed fixtures, retained for tests and offline demos.
 *
 * The transport is deliberately dumb: it serializes the request text, parses the
 * response, and surfaces failures as an error *type*. It performs no routing, no
 * formatting, no privacy or fallback interpretation, and no date handling —
 * every one of those belongs to the Python engines.
 */

import {
  ERROR_PROMPT,
  RESPONSES_BY_PROMPT,
  mockHealth,
  resolveMockRunSettings,
  unsupportedResponse,
} from '../mocks/fixtures';
import type { AgentRunRequest, AgentRunResponse, HealthResponse } from '../types/api';

/** Which client backs the workspace. Surfaced in the runtime status bar. */
export type ApiMode = 'mock' | 'http';

/** Per-call transport controls. */
export interface RequestOptions {
  /**
   * Aborts the browser's wait for this call.
   *
   * This stops the *client* only. The adapter's `POST /api/agent/run` handler is
   * a sync FastAPI endpoint running in a threadpool, so a disconnect does not
   * interrupt `answer_office_request()` — work already started on the server
   * runs to completion. Nothing in this layer may claim otherwise.
   */
  signal?: AbortSignal;
}

export interface AgentClient {
  /**
   * Where this client's data comes from. The status bar reports it, so the demo
   * can never silently claim fixtures are live data (or the reverse).
   */
  readonly mode: ApiMode;
  run(request: AgentRunRequest, options?: RequestOptions): Promise<AgentRunResponse>;
  health(options?: RequestOptions): Promise<HealthResponse>;
}

/**
 * A failed request. `errorType` carries the exception *type* name only — the
 * same convention the Phase 2 adapter uses for its 500 body, and the repo's
 * rule that error messages may leak paths or secrets.
 */
export class AgentApiError extends Error {
  readonly errorType: string;

  constructor(errorType: string) {
    super(errorType);
    this.name = 'AgentApiError';
    this.errorType = errorType;
  }
}

/**
 * The three ways a call can fail without the adapter having answered. They are
 * kept distinct because they mean different things to the user: one was their
 * own doing, one is a stalled request, and only the third says anything about
 * whether the API is up.
 */
/** The adapter is not answering at all: not started, wrong port, proxy down. */
export const API_UNREACHABLE_ERROR = 'ApiUnreachableError';
/** The user pressed Stop. */
export const REQUEST_CANCELLED_ERROR = 'RequestCancelledError';
/** No response within the client-side budget. */
export const REQUEST_TIMEOUT_ERROR = 'RequestTimeoutError';

/** Health is a cheap liveness probe, so it fails fast. */
export const DEFAULT_HEALTH_TIMEOUT_MS = 10_000;
/**
 * A Knowledge Q&A run can legitimately take a long time — retrieval, grading,
 * generation, and up to `MAX_RETRIES` regeneration loops — so the run budget is
 * generous. It exists to end a genuinely stalled request, not to bound normal work.
 */
export const DEFAULT_RUN_TIMEOUT_MS = 120_000;

export function isCancellation(error: unknown): boolean {
  return error instanceof AgentApiError && error.errorType === REQUEST_CANCELLED_ERROR;
}

export function isTimeout(error: unknown): boolean {
  return error instanceof AgentApiError && error.errorType === REQUEST_TIMEOUT_ERROR;
}

export interface MockClientOptions {
  /** Simulated latency in ms, so loading states are visible in the demo. */
  latencyMs?: number;
}

const DEFAULT_LATENCY_MS = 300;

/** Sleeps, but gives up as soon as the caller aborts. */
function delay(ms: number, signal?: AbortSignal): Promise<void> {
  if (signal?.aborted) {
    return Promise.reject(new AgentApiError(REQUEST_CANCELLED_ERROR));
  }
  if (ms <= 0) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    function onAbort() {
      window.clearTimeout(timer);
      reject(new AgentApiError(REQUEST_CANCELLED_ERROR));
    }

    const timer = window.setTimeout(() => {
      signal?.removeEventListener('abort', onAbort);
      resolve();
    }, ms);

    signal?.addEventListener('abort', onAbort, { once: true });
  });
}

/**
 * Static, typed mock client.
 *
 * Response selection is an exact-match lookup over the canned demo prompts
 * (see `RESPONSES_BY_PROMPT`) — it deliberately performs no keyword matching,
 * because intent routing belongs to the deterministic Python router and must
 * never be duplicated in the frontend. Unrecognized input returns the genuine
 * unsupported-intent response.
 */
export function createMockClient(options: MockClientOptions = {}): AgentClient {
  const latencyMs = options.latencyMs ?? DEFAULT_LATENCY_MS;

  return {
    mode: 'mock',

    async run(request: AgentRunRequest, options?: RequestOptions): Promise<AgentRunResponse> {
      // Honors the signal so Stop works in the offline demo too.
      await delay(latencyMs, options?.signal);

      const prompt = request.text.trim();

      if (prompt === ERROR_PROMPT) {
        throw new AgentApiError('SimulatedUpstreamError');
      }

      const response = RESPONSES_BY_PROMPT[prompt] ?? unsupportedResponse;

      // The mock stands in for the backend, so it resolves per-run settings the
      // way the adapter does. With no options the response is returned exactly
      // as before, `run_settings` null.
      return request.options
        ? { ...response, run_settings: resolveMockRunSettings(request.options, response.intent) }
        : response;
    },

    async health(options?: RequestOptions): Promise<HealthResponse> {
      await delay(0, options?.signal);
      return mockHealth;
    },
  };
}

/** The only two paths this frontend is allowed to call. */
const HEALTH_PATH = '/api/health';
const RUN_PATH = '/api/agent/run';

export interface HttpClientOptions {
  /**
   * Prefix for the two API paths. Empty by default so requests stay
   * same-origin and the Vite dev proxy forwards `/api` to the adapter.
   */
  baseUrl?: string;
  /** Overrides the health-check budget. Exposed mainly so tests need no fake timers. */
  healthTimeoutMs?: number;
  /** Overrides the agent-run budget. Exposed mainly so tests need no fake timers. */
  runTimeoutMs?: number;
}

/** Why an in-flight call was aborted, when it was aborted by us. */
type AbortCause = 'cancelled' | 'timeout';

interface AbortPlan {
  signal: AbortSignal;
  /** The cause, or `null` when the failure came from the network itself. */
  cause: () => AbortCause | null;
  release: () => void;
}

/**
 * Combine the caller's abort signal with a timeout into one signal, while
 * remembering *why* it fired.
 *
 * Hand-rolled rather than using `AbortSignal.any` + `AbortSignal.timeout`
 * because the cause has to survive into the catch block: `fetch` rejects with an
 * opaque `AbortError` either way, and reporting a timeout as a cancellation (or
 * either one as "API unreachable") would misdescribe what happened.
 */
function planAbort(external: AbortSignal | undefined, timeoutMs: number): AbortPlan {
  const controller = new AbortController();
  let cause: AbortCause | null = null;

  function onExternalAbort() {
    cause = 'cancelled';
    controller.abort();
  }

  const timer = window.setTimeout(() => {
    cause = 'timeout';
    controller.abort();
  }, timeoutMs);

  if (external?.aborted) {
    onExternalAbort();
  } else {
    external?.addEventListener('abort', onExternalAbort, { once: true });
  }

  return {
    signal: controller.signal,
    cause: () => cause,
    release() {
      window.clearTimeout(timer);
      external?.removeEventListener('abort', onExternalAbort);
    },
  };
}

/** The typed failure for an abort we caused, or `null` if the network failed. */
function abortFailure(plan: AbortPlan): AgentApiError | null {
  const cause = plan.cause();
  if (cause === 'cancelled') {
    return new AgentApiError(REQUEST_CANCELLED_ERROR);
  }
  if (cause === 'timeout') {
    return new AgentApiError(REQUEST_TIMEOUT_ERROR);
  }
  return null;
}

function isErrorBody(value: unknown): value is { error: string } {
  return (
    typeof value === 'object' &&
    value !== null &&
    'error' in value &&
    typeof (value as { error: unknown }).error === 'string' &&
    (value as { error: string }).error.length > 0
  );
}

/**
 * Turn a non-2xx response into an error *type* string.
 *
 * The adapter's 500 body is `{"error": "<ExceptionTypeName>"}`, which is used
 * verbatim. Anything else (notably FastAPI's own 422 validation body) is mapped
 * to a fixed type name rather than surfacing a server-authored message.
 */
async function errorFromResponse(response: Response): Promise<AgentApiError> {
  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    body = null;
  }

  if (isErrorBody(body)) {
    return new AgentApiError(body.error);
  }
  if (response.status === 422) {
    return new AgentApiError('RequestValidationError');
  }
  return new AgentApiError(`HttpError${response.status}`);
}

/**
 * The live client over the Phase 2 adapter.
 *
 * Responses are trusted to match the contract in `types/api.ts` — `tests/api/`
 * asserts the exact JSON field names on the Python side, so re-validating the
 * shape here would only duplicate that contract in a second place.
 */
export function createHttpClient(options: HttpClientOptions = {}): AgentClient {
  const baseUrl = options.baseUrl ?? '';
  const healthTimeoutMs = options.healthTimeoutMs ?? DEFAULT_HEALTH_TIMEOUT_MS;
  const runTimeoutMs = options.runTimeoutMs ?? DEFAULT_RUN_TIMEOUT_MS;

  async function requestJson<T>(
    path: string,
    timeoutMs: number,
    signal: AbortSignal | undefined,
    init?: RequestInit,
  ): Promise<T> {
    const plan = planAbort(signal, timeoutMs);

    try {
      let response: Response;
      try {
        // Looked up at call time so a test can install its own `fetch`.
        response = await fetch(`${baseUrl}${path}`, { ...init, signal: plan.signal });
      } catch {
        // An abort we caused is not evidence about the API's health.
        throw abortFailure(plan) ?? new AgentApiError(API_UNREACHABLE_ERROR);
      }

      if (!response.ok) {
        throw await errorFromResponse(response);
      }

      try {
        return (await response.json()) as T;
      } catch {
        // The body can also be cut short by a stop or a timeout.
        throw abortFailure(plan) ?? new AgentApiError('InvalidJsonResponse');
      }
    } finally {
      plan.release();
    }
  }

  return {
    mode: 'http',

    run(request: AgentRunRequest, options?: RequestOptions): Promise<AgentRunResponse> {
      return requestJson<AgentRunResponse>(RUN_PATH, runTimeoutMs, options?.signal, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
    },

    health(options?: RequestOptions): Promise<HealthResponse> {
      return requestJson<HealthResponse>(HEALTH_PATH, healthTimeoutMs, options?.signal);
    },
  };
}

/**
 * Resolve the client mode from the build environment.
 *
 * `http` is the default: the workspace talks to the real Office Agent unless
 * `VITE_API_MODE=mock` explicitly asks for the fixture demo.
 */
export function resolveApiMode(raw: string | undefined = import.meta.env.VITE_API_MODE): ApiMode {
  return raw === 'mock' ? 'mock' : 'http';
}

/** The client the app uses when none is injected. */
export function createClientFromEnv(): AgentClient {
  return resolveApiMode() === 'mock' ? createMockClient() : createHttpClient();
}
