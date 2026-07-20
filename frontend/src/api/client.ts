/**
 * The client boundary between the UI and the Office Agent.
 *
 * Phase 1 ships the mock client only. Components depend on the `AgentClient`
 * interface rather than any transport, so Phase 3 adds `createHttpClient` and
 * swaps the implementation without touching a single component.
 */

import { ERROR_PROMPT, RESPONSES_BY_PROMPT, mockHealth, unsupportedResponse } from '../mocks/fixtures';
import type { AgentRunRequest, AgentRunResponse, HealthResponse } from '../types/api';

export interface AgentClient {
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
