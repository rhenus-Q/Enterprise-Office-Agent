/**
 * The workspace wired to the real HTTP client, with `fetch` stubbed at the
 * network boundary.
 *
 * The payloads below are shaped exactly like the Phase 2 adapter's JSON, so
 * these tests exercise the same path the browser takes against a running
 * `uv run uvicorn api.app:create_app --factory` — without any Python process,
 * API key, or Chroma index.
 */

import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createHttpClient } from './api/client';

const HEALTH_OK = {
  status: 'ok',
  privacy_mode: false,
  offline_mode: false,
  office_llm_enabled: false,
  web_search_effective: true,
};

const HEALTH_PRIVATE = {
  status: 'ok',
  privacy_mode: true,
  offline_mode: false,
  office_llm_enabled: false,
  web_search_effective: false,
};

const RUN_SUCCESS = {
  intent: 'ticket_assistant',
  tool: 'ticket_assistant',
  content: 'Open tickets (2)\n- TCK-101 VPN certificate renewal (high, due 2026-07-03)',
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 4.2,
  execution_mode: 'deterministic',
  observability: null,
};

const RUN_DEGRADED = {
  intent: 'email_summary',
  tool: 'email_summary',
  content: 'Inbox summary for 2026-07-01\n- 3 unread messages',
  stop_reason: 'llm_assist_error',
  sources: [],
  run_id: null,
  duration_ms: 9.1,
  execution_mode: 'llm_assist_fallback',
  observability: null,
};

const RUN_UNSUPPORTED = {
  intent: 'unknown',
  tool: null,
  content: "Sorry — the Office Agent can't handle that request yet.",
  stop_reason: '',
  sources: [],
  run_id: null,
  duration_ms: 0.3,
  execution_mode: 'none',
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

interface ApiStub {
  /** Queued health outcomes; the last one repeats once the queue is drained. */
  health: (() => Promise<Response>)[];
  run?: () => Promise<Response>;
}

/**
 * Route stubbed `fetch` calls by path, so a test can fail health and succeed on
 * `/api/agent/run` independently.
 */
function stubApi(stub: ApiStub) {
  const healthOutcomes = [...stub.health];
  const fetchMock = vi.fn((input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith('/api/health')) {
      const next = healthOutcomes.length > 1 ? healthOutcomes.shift()! : healthOutcomes[0];
      return next();
    }
    if (url.endsWith('/api/agent/run')) {
      return (stub.run ?? (() => Promise.resolve(jsonResponse(RUN_SUCCESS))))();
    }
    throw new Error(`Unexpected request to ${url}`);
  });

  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function statusList() {
  return within(screen.getByRole('list', { name: 'Runtime status' }));
}

async function submit(text: string) {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText('Request'), text);
  await user.click(screen.getByRole('button', { name: 'Run request' }));
  return user;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('live API mode', () => {
  it('renders the real runtime flags from GET /api/health', async () => {
    stubApi({ health: [() => Promise.resolve(jsonResponse(HEALTH_PRIVATE))] });
    render(<App client={createHttpClient()} />);

    expect(await screen.findByText('Restricted')).toBeInTheDocument();
    expect(statusList().getByText('Blocked')).toBeInTheDocument();
    // The transport is named honestly: live data, not fixtures.
    expect(statusList().getByText('Live API')).toBeInTheDocument();
    expect(statusList().queryByText('Mock environment')).not.toBeInTheDocument();
  });

  it('runs a request through POST /api/agent/run and renders the response verbatim', async () => {
    const fetchMock = stubApi({ health: [() => Promise.resolve(jsonResponse(HEALTH_OK))] });
    render(<App client={createHttpClient()} />);
    await screen.findByText('Available');

    await submit('Show my open tickets');

    // Engine content, including its data-anchored date, is shown as returned.
    expect(await screen.findByText(/due 2026-07-03/)).toBeInTheDocument();
    expect(fetchMock).toHaveBeenCalledWith(
      '/api/agent/run',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ text: 'Show my open tickets' }),
      }),
    );
  });

  it('shows a degraded banner with the verbatim stop reason from a real-shaped payload', async () => {
    stubApi({
      health: [() => Promise.resolve(jsonResponse(HEALTH_OK))],
      run: () => Promise.resolve(jsonResponse(RUN_DEGRADED)),
    });
    render(<App client={createHttpClient()} />);
    await screen.findByText('Available');

    await submit('Summarize my unread emails');

    expect(await screen.findByText(/Degraded run/)).toBeInTheDocument();
    expect(screen.getAllByText('llm_assist_error').length).toBeGreaterThan(0);
    expect(screen.getByText(/Inbox summary for 2026-07-01/)).toBeInTheDocument();
  });

  it('renders the unsupported notice when the router returns the unknown intent', async () => {
    stubApi({
      health: [() => Promise.resolve(jsonResponse(HEALTH_OK))],
      run: () => Promise.resolve(jsonResponse(RUN_UNSUPPORTED)),
    });
    render(<App client={createHttpClient()} />);
    await screen.findByText('Available');

    await submit('Water the office plants');

    expect(await screen.findByText('No matching capability')).toBeInTheDocument();
  });

  it('surfaces an adapter 500 as the error state, showing the exception type only', async () => {
    stubApi({
      health: [() => Promise.resolve(jsonResponse(HEALTH_OK))],
      run: () => Promise.resolve(jsonResponse({ error: 'RuntimeError' }, 500)),
    });
    render(<App client={createHttpClient()} />);
    await screen.findByText('Available');

    await submit('Show my open tickets');

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Request failed' })).toBeInTheDocument();
    expect(screen.getByText('RuntimeError')).toBeInTheDocument();
  });

  it('reports an unreachable API and keeps the mock demo path discoverable', async () => {
    stubApi({ health: [() => Promise.reject(new TypeError('Failed to fetch'))] });
    render(<App client={createHttpClient()} />);

    expect(await screen.findByText('Unreachable')).toBeInTheDocument();
    // The recovery instructions are text, not colour: how to start the adapter
    // and how to fall back to the fixture demo.
    expect(statusList().getByText(/uvicorn api\.app:create_app --factory/)).toBeInTheDocument();
    expect(statusList().getByText(/VITE_API_MODE=mock/)).toBeInTheDocument();
    // No runtime flags are invented while the API is silent.
    expect(statusList().queryByText('Privacy')).not.toBeInTheDocument();
  });

  it('re-checks health when the refresh control is used', async () => {
    const user = userEvent.setup();
    stubApi({
      health: [
        () => Promise.reject(new TypeError('Failed to fetch')),
        () => Promise.resolve(jsonResponse(HEALTH_OK)),
      ],
    });
    render(<App client={createHttpClient()} />);
    expect(await screen.findByText('Unreachable')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Refresh runtime status' }));

    await waitFor(() => expect(statusList().getByText('Standard')).toBeInTheDocument());
    expect(statusList().getByText('Available')).toBeInTheDocument();
    expect(statusList().queryByText('Unreachable')).not.toBeInTheDocument();
  });
});
