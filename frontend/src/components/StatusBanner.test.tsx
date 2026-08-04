import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { HealthResponse } from '../types/api';
import { StatusBanner } from './StatusBanner';

const MOBILE_QUERY = '(max-width: 860px)';
const NORMAL_HEALTH: HealthResponse = {
  status: 'ok',
  privacy_mode: false,
  offline_mode: false,
  office_llm_enabled: true,
  web_search_effective: true,
};

function mockViewport(mobile: boolean) {
  vi.stubGlobal(
    'matchMedia',
    vi.fn((query: string) => ({
      matches: query === MOBILE_QUERY ? mobile : false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  );
}

function banner(
  options: Partial<React.ComponentProps<typeof StatusBanner>> = {},
) {
  return (
    <StatusBanner
      health={NORMAL_HEALTH}
      phase="ready"
      timedOut={false}
      apiMode="http"
      isRefreshing={false}
      onRefresh={vi.fn()}
      {...options}
    />
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('desktop runtime status', () => {
  it('retains the complete read-only policy strip and top-level refresh control', () => {
    mockViewport(false);
    render(banner());

    const status = within(screen.getByRole('list', { name: 'Runtime status' }));
    expect(status.getByText('Server policy')).toBeInTheDocument();
    expect(status.getByText('Privacy')).toBeInTheDocument();
    expect(status.getByText('Standard')).toBeInTheDocument();
    expect(status.getByText('Offline restrictions')).toBeInTheDocument();
    expect(status.getByText('LLM assist')).toBeInTheDocument();
    expect(status.getByText('Web search')).toBeInTheDocument();
    expect(status.getByText('Available')).toBeInTheDocument();
    expect(status.getByText('Data source')).toBeInTheDocument();
    expect(status.getByText('Live API')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Refresh runtime status' })).toBeEnabled();
    expect(screen.queryByRole('button', { name: /Server policy:/ })).not.toBeInTheDocument();
  });
});

describe('mobile runtime status', () => {
  it('starts as one truthful summary and expands to every policy and source value', async () => {
    mockViewport(true);
    const user = userEvent.setup();
    render(banner());

    expect(screen.queryByRole('list', { name: 'Runtime status' })).not.toBeInTheDocument();
    const toggle = screen.getByRole('button', {
      name: 'Server policy: Standard. API online. Expand details.',
    });
    expect(within(toggle).getByText('Standard')).toBeVisible();
    expect(within(toggle).queryByText('Live API')).not.toBeInTheDocument();
    expect(toggle.querySelector('.status-mobile__summary-icon svg')).toBeInTheDocument();
    expect(toggle.querySelector('.status-mobile__availability--online')).not.toBeInTheDocument();
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    const panelId = toggle.getAttribute('aria-controls');
    expect(panelId).toBeTruthy();
    const panel = document.getElementById(panelId!);
    expect(panel).toHaveAttribute('hidden');
    expect(screen.queryByRole('button', { name: 'Refresh runtime status' })).not.toBeInTheDocument();

    toggle.focus();
    await user.keyboard('{Enter}');

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(toggle).toHaveAccessibleName(
      'Server policy: Standard. API online. Collapse details.',
    );
    expect(panel).not.toHaveAttribute('hidden');
    expect(panel).toHaveAttribute('aria-labelledby', toggle.id);
    const details = within(panel!);
    for (const text of [
      'Privacy',
      'Standard',
      'Offline restrictions',
      'Off',
      'LLM assist',
      'On',
      'Web search',
      'Available',
      'Data source',
      'Live API',
    ]) {
      expect(details.getByText(text)).toBeInTheDocument();
    }
    expect(details.getByText(/Last checked:/)).toHaveTextContent('just now');
    expect(details.getByText(/PRIVACY_MODE is off/)).toHaveClass('sr-only');
  });

  it('keeps refresh inside the panel and preserves loading and click behavior', async () => {
    mockViewport(true);
    const user = userEvent.setup();
    const onRefresh = vi.fn();
    const { rerender } = render(banner({ onRefresh }));
    const toggle = screen.getByRole('button', { name: /Server policy:/ });

    await user.click(toggle);
    expect(onRefresh).not.toHaveBeenCalled();
    await user.click(screen.getByRole('button', { name: 'Refresh runtime status' }));
    expect(onRefresh).toHaveBeenCalledTimes(1);

    rerender(banner({ onRefresh, isRefreshing: true }));
    expect(screen.getByRole('button', { name: 'Refresh runtime status' })).toBeDisabled();
    expect(screen.getByText('Checking…')).toBeInTheDocument();

    await user.click(toggle);
    expect(onRefresh).toHaveBeenCalledTimes(1);
  });

  it.each([
    {
      name: 'API failure',
      health: null,
      phase: 'unreachable' as const,
      visible: 'API unavailable',
      accessible: 'Server policy unavailable. API unavailable. Expand details.',
      state: 'unavailable',
      iconClass: '.lucide-unplug',
    },
    {
      name: 'offline restrictions',
      health: { ...NORMAL_HEALTH, offline_mode: true, privacy_mode: true },
      phase: 'ready' as const,
      visible: 'Offline',
      accessible:
        'Server policy: Strict. Offline restrictions enabled. API online. Expand details.',
      state: 'offline',
      iconClass: '.lucide-wifi-off',
    },
    {
      name: 'restricted privacy',
      health: { ...NORMAL_HEALTH, privacy_mode: true },
      phase: 'ready' as const,
      visible: 'Strict',
      accessible: 'Server policy: Strict. API online. Expand details.',
      state: 'strict',
      iconClass: '.lucide-shield',
    },
    {
      name: 'normal policy',
      health: NORMAL_HEALTH,
      phase: 'ready' as const,
      visible: 'Standard',
      accessible: 'Server policy: Standard. API online. Expand details.',
      state: 'standard',
      iconClass: '.lucide-shield',
    },
  ])(
    'prioritizes $name in the compact summary',
    ({ health, phase, visible, accessible, state, iconClass }) => {
      mockViewport(true);
      render(banner({ health, phase }));

      const toggle = screen.getByRole('button', { name: accessible });
      expect(within(toggle).getByText(visible)).toBeVisible();
      expect(toggle).toHaveAttribute('data-state', state);
      expect(toggle.querySelector(iconClass)).toBeInTheDocument();
      expect(
        toggle.querySelector('.status-mobile__availability--online'),
      ).not.toBeInTheDocument();
    },
  );

  it('announces the mock runtime without widening the visible policy summary', () => {
    mockViewport(true);
    render(banner({ apiMode: 'mock' }));

    const toggle = screen.getByRole('button', {
      name: 'Server policy: Standard. Mock runtime available. Expand details.',
    });
    expect(within(toggle).getByText('Standard')).toBeVisible();
    expect(within(toggle).queryByText('Fixtures')).not.toBeInTheDocument();
    expect(toggle.querySelector('.status-mobile__availability--online')).not.toBeInTheDocument();
  });
});
