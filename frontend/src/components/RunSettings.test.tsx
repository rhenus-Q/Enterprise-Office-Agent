import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { App } from '../App';
import { createMockClient, type AgentClient } from '../api/client';
import { emailSuccess, knowledgeSuccess, mockHealth, ticketsSuccess } from '../mocks/fixtures';
import type { AgentRunResponse, RunSettings } from '../types/api';

function testClient(): AgentClient {
  return createMockClient({ latencyMs: 0 });
}

/** A client that records every request and returns one fixed response. */
function recordingClient(response: AgentRunResponse) {
  const run = vi.fn(async () => response);
  return {
    run,
    client: { mode: 'mock', run, health: async () => mockHealth } as AgentClient,
  };
}

function executionDetails() {
  return within(screen.getByRole('complementary', { name: 'Execution details' }));
}

function settingsGroup() {
  return within(screen.getByRole('region', { name: 'Run settings' }));
}

const STANDARD_OFF = { privacy_mode: 'standard', llm_assist: false, web_search: false } as const;

async function submit(user: ReturnType<typeof userEvent.setup>, prompt: string) {
  await user.clear(screen.getByLabelText('Request'));
  await user.type(screen.getByLabelText('Request'), prompt);
  await user.click(screen.getByRole('button', { name: 'Run request' }));
}

describe('run settings controls', () => {
  // 1. Server policy stays read-only.
  it('keeps the top status badges read-only, not interactive controls', async () => {
    render(<App client={testClient()} />);
    await screen.findByText('Available');

    const status = within(screen.getByRole('list', { name: 'Runtime status' }));

    // No checkbox, radio, or switch anywhere in the badge strip.
    expect(status.queryAllByRole('checkbox')).toHaveLength(0);
    expect(status.queryAllByRole('radio')).toHaveLength(0);
    expect(status.queryAllByRole('switch')).toHaveLength(0);
  });

  it('describes the badges as read-only server policy', async () => {
    render(<App client={testClient()} />);
    await screen.findByText('Available');

    expect(
      screen.getByTitle('Read-only server policy configured by the API runtime.'),
    ).toBeInTheDocument();
  });

  // 2. The run settings themselves are interactive.
  it('renders interactive privacy, assist, and web-search controls', async () => {
    render(<App client={testClient()} />);

    const group = settingsGroup();
    expect(group.getByRole('radio', { name: 'Standard' })).toBeEnabled();
    expect(group.getByRole('radio', { name: 'Strict' })).toBeEnabled();
    expect(group.getAllByRole('checkbox')).toHaveLength(2);
  });

  it('states where each setting applies', async () => {
    render(<App client={testClient()} />);

    const group = settingsGroup();
    expect(group.getByText('Email Summary and Daily Briefing')).toBeInTheDocument();
    expect(group.getByText('Knowledge Q&A')).toBeInTheDocument();
    expect(group.getByText('external-service-capable runs')).toBeInTheDocument();
  });

  // 3. The selection travels with the run.
  it('sends the selected settings with the request', async () => {
    const user = userEvent.setup();
    const { run, client } = recordingClient(emailSuccess);
    render(<App client={client} />);

    await user.click(settingsGroup().getByRole('radio', { name: 'Strict' }));
    await user.click(settingsGroup().getByRole('checkbox', { name: 'LLM Assist' }));
    await submit(user, 'Summarize my unread emails');

    await waitFor(() => expect(run).toHaveBeenCalledTimes(1));
    expect(run).toHaveBeenCalledWith(
      {
        text: 'Summarize my unread emails',
        options: { privacy_mode: 'strict', llm_assist: true, web_search: false },
      },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  // 4. The snapshot is taken at submit time.
  it('snapshots the settings at submission so later edits cannot change the run', async () => {
    const user = userEvent.setup();
    let resolve: ((value: AgentRunResponse) => void) | undefined;
    const run = vi.fn(() => new Promise<AgentRunResponse>((r) => (resolve = r)));
    const client = { mode: 'mock', run, health: async () => mockHealth } as unknown as AgentClient;

    render(<App client={client} />);
    await submit(user, 'Summarize my unread emails');
    await waitFor(() => expect(run).toHaveBeenCalledTimes(1));

    // The request already went out with the defaults; the controls are locked
    // during the run, and the captured call must not change retroactively.
    resolve?.(emailSuccess);
    await screen.findByText(/Inbox summary/);

    expect(run).toHaveBeenCalledWith(
      { text: 'Summarize my unread emails', options: STANDARD_OFF },
      expect.anything(),
    );
  });

  // 5. Controls lock during a run and come back afterwards.
  it('disables the controls while a run is active and restores them after', async () => {
    const user = userEvent.setup();
    let resolve: ((value: AgentRunResponse) => void) | undefined;
    const run = vi.fn(() => new Promise<AgentRunResponse>((r) => (resolve = r)));
    const client = { mode: 'mock', run, health: async () => mockHealth } as unknown as AgentClient;

    render(<App client={client} />);
    await submit(user, 'Summarize my unread emails');

    await waitFor(() =>
      expect(settingsGroup().getByRole('radio', { name: 'Strict' })).toBeDisabled(),
    );

    resolve?.(emailSuccess);
    await screen.findByText(/Inbox summary/);

    expect(settingsGroup().getByRole('radio', { name: 'Strict' })).toBeEnabled();
  });

  it('restores the controls after a stopped run', async () => {
    const user = userEvent.setup();
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    const client = { mode: 'mock', run, health: async () => mockHealth } as unknown as AgentClient;

    render(<App client={client} />);
    await submit(user, 'Summarize my unread emails');
    await waitFor(() =>
      expect(settingsGroup().getByRole('radio', { name: 'Strict' })).toBeDisabled(),
    );

    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));

    expect(settingsGroup().getByRole('radio', { name: 'Strict' })).toBeEnabled();
  });

  // 6/7. Retry reproduces; a new Run re-snapshots.
  it('reuses the original settings on retry, even after the controls changed', async () => {
    const user = userEvent.setup();
    const { run, client } = recordingClient(ticketsSuccess);
    render(<App client={client} />);

    await user.click(settingsGroup().getByRole('radio', { name: 'Strict' }));
    await submit(user, 'Show my open tickets');
    await screen.findByText(/Open tickets/);

    // Change the controls *after* the run, then retry.
    await user.click(settingsGroup().getByRole('radio', { name: 'Standard' }));
    await user.click(screen.getByRole('button', { name: 'Retry request' }));

    await waitFor(() => expect(run).toHaveBeenCalledTimes(2));
    expect(run).toHaveBeenNthCalledWith(
      2,
      {
        text: 'Show my open tickets',
        options: { privacy_mode: 'strict', llm_assist: false, web_search: false },
      },
      expect.anything(),
    );
  });

  // Reset clears the workspace but keeps Run Settings as a persistent preference.
  it('preserves the selected run settings across a workspace reset', async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(ticketsSuccess);
    render(<App client={client} />);

    // Change two settings, then produce a result to clear.
    await user.click(settingsGroup().getByRole('radio', { name: 'Strict' }));
    await user.click(settingsGroup().getByRole('checkbox', { name: 'LLM Assist' }));
    await submit(user, 'Show my open tickets');
    await screen.findByText(/Open tickets/);

    await user.click(screen.getByRole('button', { name: 'Reset workspace' }));

    // The workspace is cleared: the result is gone and the composer is empty.
    expect(screen.queryByText(/Open tickets/)).not.toBeInTheDocument();
    expect(screen.getByLabelText('Request')).toHaveValue('');

    // The selected run settings survive the reset unchanged.
    expect(settingsGroup().getByRole('radio', { name: 'Strict' })).toBeChecked();
    expect(settingsGroup().getByRole('checkbox', { name: 'LLM Assist' })).toBeChecked();
  });

  it('uses the changed settings for a new run', async () => {
    const user = userEvent.setup();
    const { run, client } = recordingClient(ticketsSuccess);
    render(<App client={client} />);

    await submit(user, 'Show my open tickets');
    await screen.findByText(/Open tickets/);

    await user.click(settingsGroup().getByRole('radio', { name: 'Strict' }));
    await submit(user, 'Show my open tickets');

    await waitFor(() => expect(run).toHaveBeenCalledTimes(2));
    expect(run).toHaveBeenNthCalledWith(1, expect.objectContaining({ options: STANDARD_OFF }), expect.anything());
    expect(run).toHaveBeenNthCalledWith(
      2,
      expect.objectContaining({
        options: { privacy_mode: 'strict', llm_assist: false, web_search: false },
      }),
      expect.anything(),
    );
  });
});

describe('execution details: requested vs effective settings', () => {
  function withSettings(response: AgentRunResponse, run_settings: RunSettings): AgentRunResponse {
    return { ...response, run_settings };
  }

  // 8. Both columns are shown, from the backend payload.
  it('shows the requested and effective settings the backend reported', async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(
      withSettings(emailSuccess, {
        requested: { privacy_mode: 'standard', llm_assist: true, web_search: false },
        effective: { privacy_mode: 'standard', llm_assist: true, web_search: false },
        applicability: { llm_assist: true, web_search: false },
        constraints: [],
      }),
    );
    render(<App client={client} />);

    await submit(user, 'Summarize my unread emails');
    await screen.findByText(/Inbox summary/);

    const details = executionDetails();
    expect(details.getByText('Requested')).toBeInTheDocument();
    expect(details.getByText('Effective')).toBeInTheDocument();
  });

  // 9. Overrides and not-applicable are explained honestly.
  it('explains a server override and marks a non-applicable setting', async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(
      withSettings(emailSuccess, {
        requested: { privacy_mode: 'standard', llm_assist: true, web_search: true },
        effective: { privacy_mode: 'strict', llm_assist: false, web_search: false },
        applicability: { llm_assist: true, web_search: false },
        constraints: ['server_privacy_mode', 'web_search_not_applicable'],
      }),
    );
    render(<App client={client} />);

    await submit(user, 'Summarize my unread emails');
    await screen.findByText(/Inbox summary/);

    const details = executionDetails();
    expect(details.getByText('Server privacy mode overrode this request.')).toBeInTheDocument();
    expect(details.getByText('Web Search does not apply to this capability.')).toBeInTheDocument();
    expect(details.getByText('Not applicable')).toBeInTheDocument();
  });

  it('does not claim effective settings for a stopped run', async () => {
    const user = userEvent.setup();
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    const client = { mode: 'mock', run, health: async () => mockHealth } as unknown as AgentClient;

    render(<App client={client} />);
    await submit(user, 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));

    const details = executionDetails();
    // The requested snapshot is still shown, but effective is honestly unknown.
    expect(details.getByText('Requested')).toBeInTheDocument();
    expect(details.getByText(/no completed response was received/)).toBeInTheDocument();
  });

  it('says the backend reported nothing for a completed run with null settings', async () => {
    const user = userEvent.setup();
    const { client } = recordingClient({ ...ticketsSuccess, run_settings: null });
    render(<App client={client} />);

    await submit(user, 'Show my open tickets');
    await screen.findByText(/Open tickets/);

    // A settled response with no run_settings must not read as "still waiting".
    expect(executionDetails().getByText('Requested')).toBeInTheDocument();
    expect(
      executionDetails().getByText('The backend did not report effective settings for this run.'),
    ).toBeInTheDocument();
    expect(
      executionDetails().queryByText(/Waiting for the backend to report/),
    ).not.toBeInTheDocument();
  });

  it('says it is waiting while a run is still in flight', async () => {
    const user = userEvent.setup();
    // Never resolves, so the run stays active and no settings are reported yet.
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    const client = { mode: 'mock', run, health: async () => mockHealth } as unknown as AgentClient;

    render(<App client={client} />);
    await submit(user, 'Show my open tickets');

    const details = executionDetails();
    await waitFor(() =>
      expect(
        details.getByText(
          'Waiting for the backend to report which settings actually govern this run.',
        ),
      ).toBeInTheDocument(),
    );
    expect(
      details.queryByText('The backend did not report effective settings for this run.'),
    ).not.toBeInTheDocument();
  });

  // 11. The Phase 4 observability view still works alongside the new section.
  it('still renders the Knowledge Q&A timeline and observability fields', async () => {
    const user = userEvent.setup();
    const { client } = recordingClient(knowledgeSuccess);
    render(<App client={client} />);

    await submit(user, 'What is the VPN policy?');

    const details = executionDetails();
    expect(await details.findByRole('heading', { name: 'Graph execution' })).toBeInTheDocument();
    expect(details.getByText('retrieve')).toBeInTheDocument();
    expect(details.getByText('Tracked LLM calls')).toBeInTheDocument();
  });
});
