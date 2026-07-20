/**
 * Transport-level tests for the HTTP client.
 *
 * These assert only what the client is responsible for: the two allowed
 * endpoints, the request shape, and the mapping of failures to an error *type*.
 * Nothing here re-checks engine semantics — those live in the Python suites.
 */

import { afterEach, describe, expect, it, vi } from 'vitest';

import {
  AgentApiError,
  API_UNREACHABLE_ERROR,
  REQUEST_CANCELLED_ERROR,
  REQUEST_TIMEOUT_ERROR,
  createHttpClient,
  createMockClient,
  isCancellation,
  isTimeout,
  resolveApiMode,
} from './client';
import type { AgentRunResponse, HealthResponse } from '../types/api';

const healthPayload: HealthResponse = {
  status: 'ok',
  privacy_mode: false,
  offline_mode: false,
  office_llm_enabled: false,
  web_search_effective: true,
};

const runPayload: AgentRunResponse = {
  intent: 'ticket_assistant',
  tool: 'ticket_assistant',
  content: 'Open tickets (2)\n- TCK-101 VPN certificate renewal (high)',
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 3.4,
  execution_mode: 'deterministic',
  observability: null,
};

/** A minimal stand-in for `Response` — only the members the client touches. */
function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

/** A 2xx response whose body is not JSON at all. */
function brokenJsonResponse(): Response {
  return {
    ok: true,
    status: 200,
    json: async () => {
      throw new SyntaxError('Unexpected token');
    },
  } as unknown as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('resolveApiMode', () => {
  it('defaults to the live API', () => {
    expect(resolveApiMode(undefined)).toBe('http');
  });

  it('selects the mock client only for the exact "mock" value', () => {
    expect(resolveApiMode('mock')).toBe('mock');
    expect(resolveApiMode('Mock')).toBe('http');
    expect(resolveApiMode('anything-else')).toBe('http');
  });
});

describe('client modes', () => {
  it('reports which transport backs each client', () => {
    expect(createMockClient({ latencyMs: 0 }).mode).toBe('mock');
    expect(createHttpClient().mode).toBe('http');
  });
});

describe('createHttpClient', () => {
  it('GETs the health endpoint and returns the flags verbatim', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(healthPayload));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createHttpClient().health()).resolves.toEqual(healthPayload);
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/health',
      // Every call carries an abort signal, so it can be stopped or time out.
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('POSTs the request text as JSON and returns the response verbatim', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(runPayload));
    vi.stubGlobal('fetch', fetchMock);

    await expect(createHttpClient().run({ text: 'Show my open tickets' })).resolves.toEqual(
      runPayload,
    );
    expect(fetchMock).toHaveBeenCalledWith('/api/agent/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'Show my open tickets' }),
      signal: expect.any(AbortSignal),
    });
  });

  it('prefixes both paths with an explicit base URL', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(healthPayload));
    vi.stubGlobal('fetch', fetchMock);

    await createHttpClient({ baseUrl: 'http://127.0.0.1:8000' }).health();

    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:8000/api/health',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it("surfaces the adapter's 500 body as the exception type only", async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(jsonResponse({ error: 'RuntimeError' }, 500)),
    );

    await expect(createHttpClient().run({ text: 'anything' })).rejects.toMatchObject({
      name: 'AgentApiError',
      errorType: 'RuntimeError',
    });
  });

  it('maps a validation rejection to a fixed type without echoing the server body', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        jsonResponse({ detail: [{ loc: ['body', 'text'], msg: 'String should have at least 1 character' }] }, 422),
      ),
    );

    await expect(createHttpClient().run({ text: '' })).rejects.toMatchObject({
      errorType: 'RequestValidationError',
    });
  });

  it('maps any other error status to a status-only type', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse('Not Found', 404)));

    await expect(createHttpClient().health()).rejects.toMatchObject({
      errorType: 'HttpError404',
    });
  });

  it('reports a rejected fetch as an unreachable API', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const error = await createHttpClient()
      .health()
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(AgentApiError);
    expect((error as AgentApiError).errorType).toBe(API_UNREACHABLE_ERROR);
  });

  it('reports an unparseable success body without leaking the parser message', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(brokenJsonResponse()));

    await expect(createHttpClient().run({ text: 'anything' })).rejects.toMatchObject({
      errorType: 'InvalidJsonResponse',
    });
  });
});

describe('cancellation and timeout', () => {
  /**
   * A `fetch` that never settles on its own and rejects the way a real one does
   * when its signal aborts — so the client's own signal wiring is what is under
   * test, not a stubbed shortcut.
   */
  function stallingFetch() {
    return vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      // Real `fetch` rejects straight away for a signal that is already
      // aborted, rather than waiting for an event that has been and gone.
      if (init?.signal?.aborted) {
        return Promise.reject(new DOMException('The operation was aborted.', 'AbortError'));
      }
      return new Promise<Response>((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
      });
    });
  }

  it('reports a stopped run as a cancellation, never as an unreachable API', async () => {
    vi.stubGlobal('fetch', stallingFetch());
    const controller = new AbortController();

    const pending = createHttpClient().run({ text: 'anything' }, { signal: controller.signal });
    controller.abort();

    const error = await pending.catch((caught: unknown) => caught);

    expect((error as AgentApiError).errorType).toBe(REQUEST_CANCELLED_ERROR);
    expect((error as AgentApiError).errorType).not.toBe(API_UNREACHABLE_ERROR);
    expect(isCancellation(error)).toBe(true);
    expect(isTimeout(error)).toBe(false);
  });

  it('reports an already-aborted signal as a cancellation', async () => {
    vi.stubGlobal('fetch', stallingFetch());

    await expect(
      createHttpClient().run({ text: 'anything' }, { signal: AbortSignal.abort() }),
    ).rejects.toMatchObject({ errorType: REQUEST_CANCELLED_ERROR });
  });

  it('times out a stalled agent run without calling it unreachable', async () => {
    vi.stubGlobal('fetch', stallingFetch());

    const error = await createHttpClient({ runTimeoutMs: 10 })
      .run({ text: 'anything' })
      .catch((caught: unknown) => caught);

    expect((error as AgentApiError).errorType).toBe(REQUEST_TIMEOUT_ERROR);
    expect((error as AgentApiError).errorType).not.toBe(API_UNREACHABLE_ERROR);
    expect(isTimeout(error)).toBe(true);
    expect(isCancellation(error)).toBe(false);
  });

  it('times out a stalled health check without calling it unreachable', async () => {
    vi.stubGlobal('fetch', stallingFetch());

    const error = await createHttpClient({ healthTimeoutMs: 10 })
      .health()
      .catch((caught: unknown) => caught);

    expect((error as AgentApiError).errorType).toBe(REQUEST_TIMEOUT_ERROR);
    expect((error as AgentApiError).errorType).not.toBe(API_UNREACHABLE_ERROR);
  });

  it('still reports a genuine network failure as an unreachable API', async () => {
    // No abort involved: the distinction must survive alongside the new cases.
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));

    const error = await createHttpClient({ runTimeoutMs: 10_000 })
      .run({ text: 'anything' })
      .catch((caught: unknown) => caught);

    expect((error as AgentApiError).errorType).toBe(API_UNREACHABLE_ERROR);
    expect(isCancellation(error)).toBe(false);
    expect(isTimeout(error)).toBe(false);
  });

  it('lets the mock client be stopped too, so the offline demo behaves the same', async () => {
    const controller = new AbortController();
    const pending = createMockClient({ latencyMs: 50 }).run(
      { text: 'Show my open tickets' },
      { signal: controller.signal },
    );
    controller.abort();

    await expect(pending).rejects.toMatchObject({ errorType: REQUEST_CANCELLED_ERROR });
  });
});
