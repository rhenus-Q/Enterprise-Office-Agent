import { fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { App } from './App';
import { createMockClient, type AgentClient } from './api/client';
import { emailSuccess, mockHealth, ticketsSuccess } from './mocks/fixtures';
import type { AgentRunResponse } from './types/api';

/** Zero-latency client so tests never wait on the demo delay. */
function testClient(): AgentClient {
  return createMockClient({ latencyMs: 0 });
}

/** A client that returns one fixed response regardless of the request text. */
function fixedClient(response: AgentRunResponse): AgentClient {
  return {
    mode: 'mock',
    run: async () => response,
    health: async () => mockHealth,
  };
}

/** The rail button for a capability, whose aria-pressed marks the active one. */
function railItem(label: string) {
  return screen.getByRole('button', { name: label });
}

/** The execution-details pane — the result card now carries its own status pill. */
function executionDetails() {
  return within(screen.getByRole('complementary', { name: 'Execution details' }));
}

/** The results column — the rail and the result card share capability labels. */
function resultsRegion() {
  return within(screen.getByRole('region', { name: 'Result' }));
}

async function runPrompt(prompt: string) {
  const user = userEvent.setup();
  render(<App client={testClient()} />);

  await user.type(screen.getByLabelText('Request'), prompt);
  await user.click(screen.getByRole('button', { name: 'Run request' }));
  return user;
}

describe('workspace shell', () => {
  it('renders the three panes and all seven capabilities', async () => {
    render(<App client={testClient()} />);

    expect(screen.getByRole('navigation', { name: 'Office Agent capabilities' })).toBeInTheDocument();
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByRole('complementary', { name: 'Execution details' })).toBeInTheDocument();

    for (const label of [
      'Knowledge Q&A',
      'Email Summary',
      'Calendar Lookup',
      'Ticket Assistant',
      'Daily Briefing',
      'Meeting Agent',
      'Workflow Approval',
    ]) {
      expect(await screen.findByRole('heading', { name: label })).toBeInTheDocument();
    }
  });

  it('presents the runtime status chips accessibly from the health response', async () => {
    render(<App client={testClient()} />);

    const statusList = await screen.findByRole('list', { name: 'Runtime status' });

    // Category labels and their state values are separate, readable text.
    for (const label of [
      'Privacy',
      'Offline restrictions',
      'LLM assist',
      'Web search',
      'Mock environment',
    ]) {
      expect(within(statusList).getByText(label)).toBeInTheDocument();
    }

    expect(mockHealth.web_search_effective).toBe(true);
    expect(within(statusList).getByText('Available')).toBeInTheDocument();
    expect(within(statusList).getByText('Standard')).toBeInTheDocument();
    expect(within(statusList).getAllByText('Off')).toHaveLength(2);

    // Each chip explains itself in text, so meaning never depends on colour.
    expect(within(statusList).getByText(/PRIVACY_MODE is off/)).toBeInTheDocument();
    expect(within(statusList).getByText(/OFFLINE_MODE is off/)).toBeInTheDocument();
    expect(within(statusList).getByText(/Optional LLM assists are off/)).toBeInTheDocument();
    expect(within(statusList).getByText(/web fallback is available/)).toBeInTheDocument();
    expect(within(statusList).getByText(/typed mock fixtures/)).toBeInTheDocument();

    // Informational only — the chips are not controls.
    expect(within(statusList).queryAllByRole('button')).toHaveLength(0);
    expect(within(statusList).queryAllByRole('checkbox')).toHaveLength(0);
  });

  it('starts in the empty state', async () => {
    render(<App client={testClient()} />);
    expect(await screen.findByRole('heading', { name: 'No request yet' })).toBeInTheDocument();
  });

  it('resets a populated workspace when the brand control is activated', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    // Populate: filter to a capability, then run a request.
    await user.click(await screen.findByRole('button', { name: 'Ticket Assistant' }));
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Reset workspace' }));

    // Composer, result, and capability filter are all cleared.
    expect(screen.getByLabelText('Request')).toHaveValue('');
    expect(await screen.findByRole('heading', { name: 'No request yet' })).toBeInTheDocument();
    expect(screen.queryByText(/Open tickets \(2\)/)).not.toBeInTheDocument();

    // Execution details fall back to waiting placeholders.
    expect(screen.getByText(/Run a request to see its intent/)).toBeInTheDocument();
    expect(screen.queryByText('adapter-measured')).not.toBeInTheDocument();

    // The default featured prompts are restored.
    expect(
      screen.getByRole('button', { name: 'Summarize my unread emails' }),
    ).toBeInTheDocument();

    // Runtime status is environment state, so a reset must preserve it.
    const statusList = screen.getByRole('list', { name: 'Runtime status' });
    expect(within(statusList).getByText('Standard')).toBeInTheDocument();
    expect(within(statusList).getByText('Available')).toBeInTheDocument();
  });

  it('shows the tall discovery view when idle in the Show All mode', async () => {
    render(<App client={testClient()} />);

    expect(await screen.findByText(/Grounded answer from the knowledge base/)).toBeInTheDocument();
    expect(screen.getByText('Demo states')).toBeInTheDocument();
  });

  it('stays in the Show All view and compacts it when a result arrives', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    // Starts tall, in the multi-capability view.
    expect(await screen.findByText(/Grounded answer from the knowledge base/)).toBeInTheDocument();

    await user.type(screen.getByLabelText('Request'), 'What is the VPN policy?');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(
      await screen.findByText(/Employees must connect through the AcmeCorp VPN/),
    ).toBeInTheDocument();

    // Same view — still multi-capability — but compact.
    expect(screen.getByRole('button', { name: 'Brief me on my day' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Summarize my unread emails' })).toBeInTheDocument();
    expect(screen.queryByText(/Grounded answer from the knowledge base/)).not.toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();

    // The rail still reports where the request actually routed.
    expect(railItem('Knowledge Q&A')).toHaveAttribute('aria-pressed', 'true');
  });

  it('does not reopen a dismissed panel when a request runs', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    // Focus a capability, then click it again to dismiss the panel.
    await user.click(await screen.findByRole('button', { name: 'Email Summary' }));
    await user.click(railItem('Email Summary'));
    expect(screen.queryByRole('region', { name: 'Example requests' })).not.toBeInTheDocument();

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // Still dismissed, even though the rail reports the route.
    expect(screen.queryByRole('region', { name: 'Example requests' })).not.toBeInTheDocument();
    expect(railItem('Ticket Assistant')).toHaveAttribute('aria-pressed', 'true');
  });

  it('uses the tall view for "Show all" while idle and the compact view after a result', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    // Idle: capability view, then Show all -> tall discovery view.
    await user.click(await screen.findByRole('button', { name: 'Knowledge Q&A' }));
    await user.click(screen.getByRole('button', { name: 'Show all' }));
    expect(screen.getByText(/Grounded answer from the knowledge base/)).toBeInTheDocument();
    expect(screen.getByText('Demo states')).toBeInTheDocument();

    // A capability highlighted but not being browsed still focuses on click.
    await user.click(railItem('Knowledge Q&A'));
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();

    // With a result on screen, Show all is compact.
    await user.click(screen.getByRole('button', { name: 'Show all' }));
    expect(screen.queryByText(/Grounded answer from the knowledge base/)).not.toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Brief me on my day' })).toBeInTheDocument();
  });

  it('switches to the all view when "Show all" is clicked', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    // Filter to one capability, then run a request. After a run the panel is
    // visible only because of the selection — the exact state where clearing the
    // filter used to unmount the panel along with its own "Show all" button.
    await user.click(await screen.findByRole('button', { name: 'Email Summary' }));
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show all' }));

    // The panel survives and now shows the unfiltered featured set, including
    // prompts from other capabilities.
    expect(screen.getByRole('button', { name: 'Brief me on my day' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'What is the VPN policy?' })).toBeInTheDocument();
    // "Show all" belongs to the filtered view, so it is gone once the filter is.
    expect(screen.queryByRole('button', { name: 'Show all' })).not.toBeInTheDocument();
  });

  it('dismisses the examples panel when the browsed capability is clicked again', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.click(await screen.findByRole('button', { name: 'Email Summary' }));
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();

    // Toggling the active rail item off clears the filter and dismisses the
    // panel, which is how it is hidden again once a result is on screen.
    await user.click(screen.getByRole('button', { name: 'Email Summary' }));

    expect(screen.queryByRole('button', { name: 'Brief me on my day' })).not.toBeInTheDocument();
    expect(screen.getByText(/Inbox summary/)).toBeInTheDocument();
  });

  it('updates the rail from response.intent without leaving the Show All view', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // The rail highlights the capability the backend router chose...
    expect(railItem('Ticket Assistant')).toHaveAttribute('aria-pressed', 'true');
    // ...but the browsing mode is untouched: still multi-capability, so the
    // Ticket Assistant-only prompt is not on screen.
    expect(screen.getByRole('button', { name: 'Brief me on my day' })).toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'What tasks are blocked?' }),
    ).not.toBeInTheDocument();
  });

  it('follows response.intent rather than the clicked prompt card metadata', async () => {
    const user = userEvent.setup();
    // This client answers every request with a ticket_assistant response, so the
    // clicked card's own metadata (knowledge_qa) disagrees with the real route.
    render(<App client={fixedClient(ticketsSuccess)} />);

    await user.click(await screen.findByRole('button', { name: 'What is the VPN policy?' }));
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // The response wins: Ticket Assistant, not the card's Knowledge Q&A.
    expect(railItem('Ticket Assistant')).toHaveAttribute('aria-pressed', 'true');
    expect(railItem('Knowledge Q&A')).toHaveAttribute('aria-pressed', 'false');
  });

  it('overrides a prior sidebar selection with the routed capability', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.click(await screen.findByRole('button', { name: 'Email Summary' }));
    expect(railItem('Email Summary')).toHaveAttribute('aria-pressed', 'true');

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // A completed run takes focus away from the user's earlier selection, and
    // because the panel is in capability view it follows to the routed one.
    expect(railItem('Ticket Assistant')).toHaveAttribute('aria-pressed', 'true');
    expect(railItem('Email Summary')).toHaveAttribute('aria-pressed', 'false');
    expect(screen.getByRole('button', { name: 'What tasks are blocked?' })).toBeInTheDocument();
  });

  it('closes the capability panel when the response intent is unknown', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Demo: unsupported request');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText('No matching capability')).toBeInTheDocument();

    // No capability is in focus, so no prompt panel is shown at all.
    expect(screen.queryByRole('region', { name: 'Example requests' })).not.toBeInTheDocument();
    for (const label of ['Knowledge Q&A', 'Email Summary', 'Ticket Assistant']) {
      expect(railItem(label)).toHaveAttribute('aria-pressed', 'false');
    }
  });

  it('keeps the result visible when "Show all" is opened from a capability view', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.click(await screen.findByRole('button', { name: 'Knowledge Q&A' }));
    await user.type(screen.getByLabelText('Request'), 'What is the VPN policy?');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(
      await screen.findByText(/Employees must connect through the AcmeCorp VPN/),
    ).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Show all' }));

    // The answer survives, and the panel above it stays compact — the proxy for
    // "not pushed far below the composer", since jsdom has no real layout.
    expect(screen.getByText(/Employees must connect through the AcmeCorp VPN/)).toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();
    expect(screen.queryByText(/Deterministic inbox digest/)).not.toBeInTheDocument();
  });

  it('fills the composer when a sidebar example is selected', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.click(await screen.findByRole('button', { name: 'Show my open tickets' }));

    expect(screen.getByLabelText('Request')).toHaveValue('Show my open tickets');
  });
});

describe('run states', () => {
  it('shows the loading state while a request is in flight', async () => {
    const user = userEvent.setup();
    let resolveRun!: (response: AgentRunResponse) => void;
    const pendingClient: AgentClient = {
      mode: 'mock',
      run: () =>
        new Promise<AgentRunResponse>((resolve) => {
          resolveRun = resolve;
        }),
      health: async () => mockHealth,
    };

    render(<App client={pendingClient} />);
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));

    expect(await screen.findByRole('heading', { name: 'Running…' })).toBeInTheDocument();
    // The loading card echoes the request but never guesses where it routed.
    expect(resultsRegion().getByText('Summarize my unread emails')).toBeInTheDocument();

    resolveRun(emailSuccess);

    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();
  });

  it('replaces the previous result with the neutral loading state for a new request', async () => {
    const user = userEvent.setup();
    let resolveSecond!: (response: AgentRunResponse) => void;
    let calls = 0;
    const client: AgentClient = {
      mode: 'mock',
      run: () => {
        calls += 1;
        if (calls === 1) {
          return Promise.resolve(ticketsSuccess);
        }
        return new Promise<AgentRunResponse>((resolve) => {
          resolveSecond = resolve;
        });
      },
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // A different question — not a retry of the ticket result.
    await user.clear(screen.getByLabelText('Request'));
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));

    // The stale card is gone rather than being relabelled as refreshing.
    expect(screen.queryByText(/Open tickets \(2\)/)).not.toBeInTheDocument();
    expect(resultsRegion().queryByRole('heading', { name: 'Ticket Assistant' })).not.toBeInTheDocument();
    expect(screen.queryByText('Refreshing…')).not.toBeInTheDocument();
    // ...replaced by the capability-neutral loading card echoing the new request.
    expect(screen.getByRole('heading', { name: 'Running…' })).toBeInTheDocument();
    expect(resultsRegion().getByText('Summarize my unread emails')).toBeInTheDocument();

    resolveSecond(emailSuccess);
    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();
  });

  it('renders a successful deterministic run with its execution details', async () => {
    await runPrompt('Summarize my unread emails');

    // Engine content is rendered verbatim, including its data-anchored dates.
    expect(await screen.findByText(/Received: 2026-07-01T09:00:00/)).toBeInTheDocument();

    expect(executionDetails().getByText('Success')).toBeInTheDocument();
    // Intent and tool are both `email_summary`, so more than one code element matches.
    expect(screen.getAllByText('email_summary', { selector: 'code' }).length).toBeGreaterThan(0);
    expect(screen.getByText('adapter-measured')).toBeInTheDocument();
    expect(screen.getByText('adapter-derived')).toBeInTheDocument();
    expect(screen.getByText('Deterministic (no LLM)')).toBeInTheDocument();
  });

  it('states honestly that a deterministic capability exposes no timeline', async () => {
    await runPrompt('Summarize my unread emails');

    expect(
      await screen.findByText(/does not expose an execution timeline/),
    ).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Graph execution' })).not.toBeInTheDocument();
  });

  it('renders the Knowledge Q&A timeline from real observability metadata', async () => {
    await runPrompt('What is the VPN policy?');

    expect(await screen.findByRole('heading', { name: 'Graph execution' })).toBeInTheDocument();
    expect(screen.getByText('retrieve')).toBeInTheDocument();
    expect(screen.getByText('grade_documents')).toBeInTheDocument();
    expect(screen.getByText('generate')).toBeInTheDocument();

    expect(screen.getByText('Tracked LLM calls')).toBeInTheDocument();
    expect(screen.getByText(/budgeted counter, not total LLM usage/)).toBeInTheDocument();
    expect(screen.getByText('Total graph duration')).toBeInTheDocument();

    // Provenance is shown as structured metadata in the execution panel.
    expect(
      screen.getByText('AcmeCorp VPN Access Policy (acmecorp_vpn_policy.md)'),
    ).toBeInTheDocument();
  });

  it('shows the degraded notice with the verbatim stop reason and engine caveat', async () => {
    await runPrompt('Demo: knowledge with web search disabled');

    expect(await screen.findByText(/Degraded run/)).toBeInTheDocument();
    expect(screen.getAllByText('web_search_disabled').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Web search is disabled/).length).toBeGreaterThan(0);
    expect(executionDetails().getByText('Degraded')).toBeInTheDocument();
  });

  it('shows the unsupported notice for an unroutable request', async () => {
    await runPrompt('Demo: unsupported request');

    expect(await screen.findByText('No matching capability')).toBeInTheDocument();
    expect(executionDetails().getByText('Unsupported')).toBeInTheDocument();
    expect(screen.getByText(/Sorry — the Office Agent can't handle that request/)).toBeInTheDocument();
    expect(screen.getByText('— no tool invoked')).toBeInTheDocument();
  });

  it('starts expanded and collapses to the header only', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Collapse result' })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Collapse result' }));

    // Only the transcript goes; header, actions, and the aside all stay.
    expect(screen.queryByText(/Open tickets \(2\)/)).not.toBeInTheDocument();
    expect(resultsRegion().getByRole('heading', { name: 'Ticket Assistant' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy result' })).toBeInTheDocument();
    expect(executionDetails().getByText('Success')).toBeInTheDocument();
    expect(executionDetails().getByText('adapter-measured')).toBeInTheDocument();
  });

  it('restores the cached result on expand without a new request', async () => {
    const user = userEvent.setup();
    const run = vi.fn().mockResolvedValue(ticketsSuccess);
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Collapse result' }));
    await user.click(screen.getByRole('button', { name: 'Expand result' }));

    expect(screen.getByText(/Open tickets \(2\)/)).toBeInTheDocument();
    expect(run).toHaveBeenCalledTimes(1);
  });

  it('re-expands Show All when the result collapses, and compacts it again on expand', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Collapse result' }));
    expect(screen.getByText(/Grounded answer from the knowledge base/)).toBeInTheDocument();
    expect(screen.getByText('Demo states')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Expand result' }));
    expect(screen.queryByText(/Grounded answer from the knowledge base/)).not.toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();
  });

  it('leaves the capability prompt view unchanged across collapse and expand', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.click(await screen.findByRole('button', { name: 'Ticket Assistant' }));
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    const capabilityPrompt = { name: 'What tasks are blocked?' };
    expect(screen.getByRole('button', capabilityPrompt)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Collapse result' }));
    expect(screen.getByRole('button', capabilityPrompt)).toBeInTheDocument();
    expect(screen.queryByText('Demo states')).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Expand result' }));
    expect(screen.getByRole('button', capabilityPrompt)).toBeInTheDocument();
  });

  it('expands a collapsed result when a new request runs', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Collapse result' }));

    await user.clear(screen.getByLabelText('Request'));
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));

    expect(await screen.findByText(/Inbox summary/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Collapse result' })).toBeInTheDocument();
  });

  it('expands a collapsed result when Retry runs', async () => {
    const user = userEvent.setup();
    render(<App client={testClient()} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Collapse result' }));
    expect(screen.queryByText(/Open tickets \(2\)/)).not.toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));

    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
  });

  it('retries the original request text through the shared run machinery', async () => {
    const user = userEvent.setup();
    const run = vi.fn().mockResolvedValue(ticketsSuccess);
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));

    await waitFor(() => expect(run).toHaveBeenCalledTimes(2));
    // The original request text, not anything read back out of the content.
    expect(run).toHaveBeenNthCalledWith(
      2,
      { text: 'Show my open tickets' },
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });

  it('keeps the previous result on screen while a retry is in flight', async () => {
    const user = userEvent.setup();
    let resolveRetry!: (response: AgentRunResponse) => void;
    let calls = 0;
    const client: AgentClient = {
      mode: 'mock',
      run: () => {
        calls += 1;
        if (calls === 1) {
          return Promise.resolve(ticketsSuccess);
        }
        return new Promise<AgentRunResponse>((resolve) => {
          resolveRetry = resolve;
        });
      },
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));

    // The result stays put instead of collapsing to an empty loading card, and
    // the actions are locked so the request cannot be fired twice.
    expect(screen.getByText(/Open tickets \(2\)/)).toBeInTheDocument();
    // Retry has become this card's Stop; the composer does not add a second one.
    expect(screen.getByRole('button', { name: 'Stop waiting for this request' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: 'Retry request' })).not.toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Running…' })).not.toBeInTheDocument();
    // Visibly in progress: the old answer is dimmed and progress is announced.
    expect(document.querySelector('.result__surface')).toHaveClass('is-refreshing');
    expect(screen.getByRole('status')).toHaveTextContent('Refreshing…');
    // The previous verdict is withheld while it is being superseded.
    expect(resultsRegion().queryByText('Success')).not.toBeInTheDocument();

    resolveRetry(ticketsSuccess);
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Retry request' })).toBeEnabled(),
    );
  });

  it('confirms completion and restores the status pill after a retry', async () => {
    const user = userEvent.setup();
    const run = vi.fn().mockResolvedValue(ticketsSuccess);
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));

    // An identical response is otherwise invisible, so completion is confirmed.
    expect(await screen.findByText('Updated', {}, { timeout: 2000 })).toBeInTheDocument();
    expect(document.querySelector('.result__surface')).not.toHaveClass('is-refreshing');
    expect(resultsRegion().getByText('Success')).toBeInTheDocument();
    expect(screen.getByText(/Open tickets \(2\)/)).toBeInTheDocument();
  });

  it('stops a new request and lands on the neutral stopped state', async () => {
    const user = userEvent.setup();
    const client: AgentClient = {
      mode: 'mock',
      // Never settles on its own: only Stop can end this run.
      run: () => new Promise<AgentRunResponse>(() => {}),
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByRole('heading', { name: 'Running…' })).toBeInTheDocument();

    // Stop replaces Run in the same position.
    expect(screen.queryByRole('button', { name: 'Run request' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));

    expect(await screen.findByRole('heading', { name: 'Stopped waiting' })).toBeInTheDocument();
    expect(resultsRegion().getByText('Summarize my unread emails')).toBeInTheDocument();
    // Honest about its reach: the browser stopped waiting, the server did not stop.
    expect(screen.getByText(/Work that had already started on the server/)).toBeInTheDocument();
    // The run is over, so the composer is usable again.
    expect(screen.getByRole('button', { name: 'Run request' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Running…' })).not.toBeInTheDocument();
  });

  it('stops a retry and restores the result it was refreshing', async () => {
    const user = userEvent.setup();
    let calls = 0;
    const client: AgentClient = {
      mode: 'mock',
      run: () => {
        calls += 1;
        if (calls === 1) {
          return Promise.resolve(ticketsSuccess);
        }
        return new Promise<AgentRunResponse>(() => {});
      },
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));
    expect(document.querySelector('.result__surface')).toHaveClass('is-refreshing');

    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));

    // Back to exactly the result it started from — no stopped card, and no
    // "Updated" confirmation, because nothing was updated.
    expect(screen.getByText(/Open tickets \(2\)/)).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Stopped waiting' })).not.toBeInTheDocument();
    expect(screen.queryByText('Updated')).not.toBeInTheDocument();
    expect(document.querySelector('.result__surface')).not.toHaveClass('is-refreshing');
    expect(resultsRegion().getByText('Success')).toBeInTheDocument();
    // Retry has reclaimed the slot Stop just vacated, so it is disarmed until a
    // deliberate new gesture (covered by its own test below).
    expect(screen.getByRole('button', { name: 'Retry request' })).toBeDisabled();
    expect(executionDetails().getByText('Success')).toBeInTheDocument();
  });

  it('does not restart the run when Stop is clicked twice in the same spot', async () => {
    // The bug this guards: Stop and Run share one position, so the frame after
    // Stop is pressed an armed Run sits under the pointer. A second click there
    // used to cancel-and-restart, which read on screen as "Stop does nothing"
    // while the network showed a cancelled request followed by a fresh one.
    const user = userEvent.setup();
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'What is the VPN policy?');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    await user.click(await screen.findByRole('button', { name: 'Stop waiting for this request' }));

    // The replacement occupies the same slot but is inert.
    const replacement = screen.getByRole('button', { name: 'Run request' });
    expect(replacement).toBeDisabled();

    await user.click(replacement);

    expect(run).toHaveBeenCalledTimes(1);
    expect(screen.getByRole('heading', { name: 'Stopped waiting' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Running…' })).not.toBeInTheDocument();
  });

  it('re-arms the composer as soon as the request text is touched', async () => {
    const user = userEvent.setup();
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'What is the VPN policy?');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    await user.click(await screen.findByRole('button', { name: 'Stop waiting for this request' }));
    expect(screen.getByRole('button', { name: 'Run request' })).toBeDisabled();

    // Deliberate new intent — no timer involved.
    await user.type(screen.getByLabelText('Request'), '?');

    expect(screen.getByRole('button', { name: 'Run request' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(run).toHaveBeenCalledTimes(2);
  });

  it('leaves the stopped card its own armed way to run the request again', async () => {
    const user = userEvent.setup();
    const run = vi.fn(() => new Promise<AgentRunResponse>(() => {}));
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'What is the VPN policy?');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    await user.click(await screen.findByRole('button', { name: 'Stop waiting for this request' }));

    // A different position entirely, so it is safe to arm immediately.
    await user.click(screen.getByRole('button', { name: 'Run it again' }));

    expect(run).toHaveBeenCalledTimes(2);
    expect(await screen.findByRole('heading', { name: 'Running…' })).toBeInTheDocument();
  });

  it('does not restart a retry when the card Stop is clicked twice', async () => {
    const user = userEvent.setup();
    let calls = 0;
    const run = vi.fn(() => {
      calls += 1;
      return calls === 1
        ? Promise.resolve(ticketsSuccess)
        : new Promise<AgentRunResponse>(() => {});
    });
    render(<App client={{ mode: 'mock', run, health: async () => mockHealth }} />);

    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Retry request' }));
    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));

    // Retry reclaims the slot Stop vacated, so it is disarmed too.
    const retry = screen.getByRole('button', { name: 'Retry request' });
    expect(retry).toBeDisabled();

    await user.click(retry);

    expect(run).toHaveBeenCalledTimes(2);
    expect(screen.getByText(/Open tickets \(2\)/)).toBeInTheDocument();

    // Moving the pointer off the action row is the deliberate gesture that
    // re-arms it — no timer, so it cannot be out-raced by a fast second click.
    fireEvent.pointerLeave(document.querySelector('.result__actions') as Element);

    expect(screen.getByRole('button', { name: 'Retry request' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Retry request' }));
    expect(run).toHaveBeenCalledTimes(3);
  });

  it('ignores a response that arrives after the run was stopped', async () => {
    const user = userEvent.setup();
    let resolveRun!: (response: AgentRunResponse) => void;
    const client: AgentClient = {
      mode: 'mock',
      run: () =>
        new Promise<AgentRunResponse>((resolve) => {
          resolveRun = resolve;
        }),
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Summarize my unread emails');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    await user.click(await screen.findByRole('button', { name: 'Stop waiting for this request' }));
    expect(await screen.findByRole('heading', { name: 'Stopped waiting' })).toBeInTheDocument();

    // A client that ignores its abort signal still must not repaint the UI.
    resolveRun(emailSuccess);

    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Stopped waiting' })).toBeInTheDocument(),
    );
    expect(screen.queryByText(/Inbox summary/)).not.toBeInTheDocument();
  });

  it('aborts the previous request when a replacement is started', async () => {
    const user = userEvent.setup();
    const signals: AbortSignal[] = [];
    let resolveSecond!: (response: AgentRunResponse) => void;
    const client: AgentClient = {
      mode: 'mock',
      run: (_request, options) => {
        if (options?.signal) {
          signals.push(options.signal);
        }
        if (signals.length === 1) {
          return new Promise<AgentRunResponse>(() => {});
        }
        return new Promise<AgentRunResponse>((resolve) => {
          resolveSecond = resolve;
        });
      },
      health: async () => mockHealth,
    };

    render(<App client={client} />);
    await user.type(screen.getByLabelText('Request'), 'Show my open tickets');
    await user.click(screen.getByRole('button', { name: 'Run request' }));
    await screen.findByRole('button', { name: 'Stop waiting for this request' });

    await user.click(screen.getByRole('button', { name: 'Stop waiting for this request' }));
    await user.click(screen.getByRole('button', { name: 'Run it again' }));

    expect(signals).toHaveLength(2);
    expect(signals[0].aborted).toBe(true);
    expect(signals[1].aborted).toBe(false);

    resolveSecond(ticketsSuccess);
    expect(await screen.findByText(/Open tickets \(2\)/)).toBeInTheDocument();
  });

  it('shows the error state with the error type only', async () => {
    await runPrompt('Demo: simulated API error');

    expect(await screen.findByRole('alert')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Request failed' })).toBeInTheDocument();
    expect(screen.getByText('SimulatedUpstreamError')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry request' })).toBeInTheDocument();
    expect(
      screen.getByText(/failed before any execution details were returned/),
    ).toBeInTheDocument();
  });
});
