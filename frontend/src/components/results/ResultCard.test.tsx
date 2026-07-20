import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { ResultCard } from './ResultCard';
import { knowledgeSuccess, ticketsSuccess, unsupportedResponse } from '../../mocks/fixtures';
import type { AgentRunResponse, RunStatus } from '../../types/api';

/** jsdom's Blob has no `text()`, so read it the long way. */
function readBlob(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsText(blob);
  });
}

function setClipboard(writeText: ((text: string) => Promise<void>) | undefined) {
  Object.defineProperty(navigator, 'clipboard', {
    value: writeText ? { writeText } : undefined,
    configurable: true,
    writable: true,
  });
}

interface CardOptions {
  response?: AgentRunResponse;
  status?: RunStatus;
  expanded?: boolean;
  onToggleExpanded?: () => void;
  onRetry?: () => void;
  isRunning?: boolean;
  isRetry?: boolean;
  revision?: number;
}

function card(options: CardOptions = {}) {
  return (
    <ResultCard
      response={options.response ?? ticketsSuccess}
      status={options.status ?? 'success'}
      expanded={options.expanded ?? true}
      onToggleExpanded={options.onToggleExpanded ?? vi.fn()}
      onRetry={options.onRetry ?? vi.fn()}
      isRunning={options.isRunning ?? false}
      isRetry={options.isRetry ?? false}
      revision={options.revision ?? 1}
    />
  );
}

function surface() {
  return document.querySelector('.result__surface');
}

afterEach(() => {
  setClipboard(undefined);
  vi.restoreAllMocks();
});

describe('content rendering', () => {
  it('renders response.content verbatim', () => {
    render(card({ response: knowledgeSuccess }));

    expect(document.querySelector('.result__content')?.textContent).toBe(knowledgeSuccess.content);
  });

  it('preserves the space-aligned columns of structured output', () => {
    render(card({ response: ticketsSuccess }));

    const block = document.querySelector('.result__content');
    // The run of leading spaces that aligns the second line must survive.
    expect(block?.textContent).toContain('          Status: open');
    expect(block?.textContent).toBe(ticketsSuccess.content);
  });
});

describe('typography chosen from response.intent', () => {
  it('uses the prose variant for knowledge_qa', () => {
    render(card({ response: knowledgeSuccess }));

    expect(document.querySelector('.result__content')).toHaveAttribute('data-typography', 'prose');
  });

  it('uses the monospace variant for structured intents', () => {
    render(card({ response: ticketsSuccess }));

    expect(document.querySelector('.result__content')).toHaveAttribute('data-typography', 'mono');
  });
});

describe('header', () => {
  it('labels the card from response.intent', () => {
    render(card({ response: ticketsSuccess }));

    expect(screen.getByRole('heading', { name: 'Ticket Assistant' })).toBeInTheDocument();
    expect(screen.getByText('Success')).toBeInTheDocument();
  });

  it('labels an unsupported result without inventing a capability', () => {
    render(card({ response: unsupportedResponse, status: 'unsupported' }));

    expect(screen.getByRole('heading', { name: 'Unsupported request' })).toBeInTheDocument();
  });

  it('gives every action an accessible name and keyboard focus', () => {
    render(card());

    for (const name of ['Copy result', 'Download result', 'Retry request', 'Collapse result']) {
      const button = screen.getByRole('button', { name });
      expect(button).toBeEnabled();
      // A real button, not a div with a handler.
      expect(button.tagName).toBe('BUTTON');
    }
  });
});

describe('copy', () => {
  it('writes exactly response.content to the clipboard', async () => {
    const user = userEvent.setup();
    const writeText = vi.fn().mockResolvedValue(undefined);
    setClipboard(writeText);

    render(card({ response: knowledgeSuccess }));
    await user.click(screen.getByRole('button', { name: 'Copy result' }));

    expect(writeText).toHaveBeenCalledTimes(1);
    expect(writeText).toHaveBeenCalledWith(knowledgeSuccess.content);
  });

  it('announces the confirmation in a live region', async () => {
    const user = userEvent.setup();
    setClipboard(vi.fn().mockResolvedValue(undefined));

    render(card({ response: knowledgeSuccess }));
    await user.click(screen.getByRole('button', { name: 'Copy result' }));

    const live = await screen.findByRole('status');
    expect(live).toHaveTextContent('Copied');
    expect(live).toHaveAttribute('aria-live', 'polite');
  });

  it('reports a clipboard rejection instead of crashing', async () => {
    const user = userEvent.setup();
    setClipboard(vi.fn().mockRejectedValue(new Error('denied')));

    render(card({ response: knowledgeSuccess }));
    await user.click(screen.getByRole('button', { name: 'Copy result' }));

    expect(await screen.findByText('Copy failed')).toBeInTheDocument();
  });

  it('survives a browser with no clipboard API', async () => {
    const user = userEvent.setup();
    setClipboard(undefined);

    render(card({ response: knowledgeSuccess }));
    await user.click(screen.getByRole('button', { name: 'Copy result' }));

    expect(await screen.findByText('Copy failed')).toBeInTheDocument();
  });
});

describe('download', () => {
  let createObjectURL: ReturnType<typeof vi.fn>;
  let revokeObjectURL: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    createObjectURL = vi.fn().mockReturnValue('blob:mock-url');
    revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });
    // Downloads are not navigations in jsdom; keep the click inert.
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('builds a text file containing exactly response.content', async () => {
    const user = userEvent.setup();
    render(card({ response: ticketsSuccess }));

    await user.click(screen.getByRole('button', { name: 'Download result' }));

    expect(createObjectURL).toHaveBeenCalledTimes(1);
    const blob = createObjectURL.mock.calls[0][0] as Blob;
    expect(blob.type).toContain('text/plain');
    await expect(readBlob(blob)).resolves.toBe(ticketsSuccess.content);
  });

  it('uses a safe .txt filename and revokes the object URL', async () => {
    const user = userEvent.setup();
    const anchors: HTMLAnchorElement[] = [];
    const createElement = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
      const element = createElement(tag);
      if (tag === 'a') {
        anchors.push(element as HTMLAnchorElement);
      }
      return element;
    });

    render(card({ response: ticketsSuccess }));
    await user.click(screen.getByRole('button', { name: 'Download result' }));

    expect(anchors).toHaveLength(1);
    expect(anchors[0].download).toBe('office-agent-ticket_assistant-result.txt');
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});

describe('collapse and expand', () => {
  it('hides only the transcript when collapsed', () => {
    const { rerender } = render(card({ expanded: true }));
    expect(document.querySelector('.result__content')).toBeInTheDocument();

    rerender(card({ expanded: false }));

    expect(document.querySelector('.result__content')).not.toBeInTheDocument();
    // Header and every action survive.
    expect(screen.getByRole('heading', { name: 'Ticket Assistant' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Copy result' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download result' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Retry request' })).toBeInTheDocument();
  });

  it('labels the toggle for its current state', async () => {
    const user = userEvent.setup();
    const onToggleExpanded = vi.fn();
    render(card({ expanded: true, onToggleExpanded }));

    const collapse = screen.getByRole('button', { name: 'Collapse result' });
    expect(collapse).toHaveAttribute('aria-expanded', 'true');

    await user.click(collapse);
    expect(onToggleExpanded).toHaveBeenCalledTimes(1);
  });

  it('offers an expand affordance while collapsed', () => {
    render(card({ expanded: false }));

    expect(screen.getByRole('button', { name: 'Expand result' })).toHaveAttribute(
      'aria-expanded',
      'false',
    );
  });
});

describe('refresh feedback', () => {
  it('dims the transcript, shows progress, and announces it while running', () => {
    render(card({ isRunning: true, isRetry: true }));

    expect(surface()).toHaveClass('is-refreshing');
    expect(document.querySelector('.result__progress')).toBeInTheDocument();
    // The old answer is still readable, not cleared.
    expect(document.querySelector('.result__content')?.textContent).toBe(ticketsSuccess.content);
    expect(screen.getByRole('status')).toHaveTextContent('Refreshing');
    expect(screen.getByRole('button', { name: 'Retry request' })).toBeDisabled();
  });

  it('dims the same transcript node rather than hiding or replacing it', () => {
    const { rerender } = render(card({ isRunning: false, revision: 1 }));
    const before = surface();

    rerender(card({ isRunning: true, isRetry: true, revision: 1 }));

    // Stale-while-revalidate: the node, its size, and its text all persist; only
    // the dimming class changes.
    expect(surface()).toBe(before);
    expect(surface()).toHaveClass('is-refreshing');
    expect(surface()).not.toHaveAttribute('hidden');
    expect(document.querySelector('.result__content')?.textContent).toBe(ticketsSuccess.content);
  });

  it('holds the refreshing state after a retry resolves instantly', () => {
    const { rerender } = render(card({ isRunning: true, isRetry: true, revision: 1 }));

    // The request is already done, but the minimum visible window is not.
    rerender(card({ isRunning: false, isRetry: true, revision: 2 }));

    expect(surface()).toHaveClass('is-refreshing');
    expect(screen.getByRole('status')).toHaveTextContent('Refreshing');
    expect(screen.queryByText('Updated')).not.toBeInTheDocument();
  });

  it('ends with an Updated chip and a completion pulse', async () => {
    const { rerender } = render(card({ isRunning: true, isRetry: true, revision: 1 }));
    rerender(card({ isRunning: false, isRetry: true, revision: 2 }));

    const chip = await screen.findByText('Updated', {}, { timeout: 2000 });

    expect(chip).toHaveClass('result__updated');
    expect(screen.getByRole('status')).toHaveTextContent('Updated');
    expect(surface()).not.toHaveClass('is-refreshing');
    expect(document.querySelector('.result__progress')).not.toBeInTheDocument();
    // The completion pulse, not the fly-in used for a brand new result.
    expect(surface()).toHaveAttribute('data-entry', 'updated');
    expect(surface()).toHaveAttribute('data-revision', '2');
  });

  it('does not hold or confirm for a fresh request', async () => {
    const { rerender } = render(card({ isRunning: true, isRetry: false, revision: 1 }));
    rerender(card({ isRunning: false, isRetry: false, revision: 2 }));

    await waitFor(() => expect(surface()).not.toHaveClass('is-refreshing'));

    expect(screen.queryByText('Updated')).not.toBeInTheDocument();
    expect(surface()).toHaveAttribute('data-entry', 'new');
  });

  it('remounts the transcript when the run counter advances', () => {
    const { rerender } = render(card({ revision: 1 }));
    const first = surface();

    // Same response object, same content, same run_id — only the counter moves.
    rerender(card({ revision: 2 }));

    expect(surface()).not.toBe(first);
    expect(surface()).toHaveAttribute('data-revision', '2');
  });
});

describe('reduced motion', () => {
  // jsdom cannot evaluate media queries, so the testable guard is that motion is
  // expressed only in CSS. Inline styles or Web Animations would bypass the
  // prefers-reduced-motion rule; nothing here uses either.
  it('drives all motion from CSS, leaving reduced motion in control', () => {
    render(card());
    const element = surface() as HTMLElement;

    expect(element.getAttribute('style')).toBeNull();
    expect(element.style.transform).toBe('');
    expect(element.style.animation).toBe('');
  });

  it('keeps the feedback that reduced motion must not remove', () => {
    render(card({ isRunning: true, isRetry: true }));

    // Dimming, progress indication, and the announcement are all non-decorative.
    expect(surface()).toHaveClass('is-refreshing');
    expect(document.querySelector('.result__progress')).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Refreshing');
  });
});

describe('retry', () => {
  it('calls the shared run handler', async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(card({ onRetry }));

    await user.click(screen.getByRole('button', { name: 'Retry request' }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it('disables every content action while a request is running', () => {
    render(card({ isRunning: true, isRetry: true }));

    expect(screen.getByRole('button', { name: 'Retry request' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Copy result' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Download result' })).toBeDisabled();
  });
});
