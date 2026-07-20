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

import { ERROR_PROMPT, RESPONSES_BY_PROMPT, mockHealth, unsupportedResponse } from '../mocks/fixtures';
import type { AgentRunRequest, AgentRunResponse, HealthResponse } from '../types/api';

/** Which client backs the workspace. Surfaced in the runtime status bar. */
export type ApiMode = 'mock' | 'http';

export interface AgentClient {
  /**
   * Where this client's data comes from. The status bar reports it, so the demo
   * can never silently claim fixtures are live data (or the reverse).
   */
  readonly mode: ApiMode;
  run(request: AgentRunRequest): Promise<AgentRunResponse>;
  health(): Promise<HealthResponse>;
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

/** The adapter is not answering at all: not started, wrong port, proxy down. */
export const API_UNREACHABLE_ERROR = 'ApiUnreachableError';

export interface MockClientOptions {
  /** Simulated latency in ms, so loading states are visible in the demo. */
  latencyMs?: number;
}

const DEFAULT_LATENCY_MS = 300;

function delay(ms: number): Promise<void> {
  if (ms <= 0) {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    setTimeout(resolve, ms);
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

    async run(request: AgentRunRequest): Promise<AgentRunResponse> {
      await delay(latencyMs);

      const prompt = request.text.trim();

      if (prompt === ERROR_PROMPT) {
        throw new AgentApiError('SimulatedUpstreamError');
      }

      return RESPONSES_BY_PROMPT[prompt] ?? unsupportedResponse;
    },

    async health(): Promise<HealthResponse> {
      await delay(0);
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

  async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
    let response: Response;
    try {
      // Looked up at call time so a test can install its own `fetch`.
      response = await fetch(`${baseUrl}${path}`, init);
    } catch {
      throw new AgentApiError(API_UNREACHABLE_ERROR);
    }

    if (!response.ok) {
      throw await errorFromResponse(response);
    }

    try {
      return (await response.json()) as T;
    } catch {
      throw new AgentApiError('InvalidJsonResponse');
    }
  }

  return {
    mode: 'http',

    run(request: AgentRunRequest): Promise<AgentRunResponse> {
      return requestJson<AgentRunResponse>(RUN_PATH, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });
    },

    health(): Promise<HealthResponse> {
      return requestJson<HealthResponse>(HEALTH_PATH);
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
