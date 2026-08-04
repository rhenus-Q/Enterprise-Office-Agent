import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { AppShell } from './AppShell';

const MOBILE_QUERY = '(max-width: 860px)';

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

function shell(sidebar = <button className="nav__item">Ticket Assistant</button>) {
  return (
    <AppShell
      banner={<div>Runtime banner</div>}
      sidebar={sidebar}
      main={<button>Main action</button>}
      aside={<p>Execution details</p>}
      onReset={vi.fn()}
    />
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.body.style.overflow = '';
});

describe('mobile capability drawer', () => {
  it('opens from the keyboard, traps focus, closes with Escape, and restores focus', async () => {
    mockViewport(true);
    const user = userEvent.setup();
    render(shell());

    const toggle = screen.getByRole('button', { name: 'Show capabilities' });
    const dialog = document.querySelector('.app__sidebar-dialog');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(toggle).toHaveAttribute('aria-controls', 'capability-sidebar');
    expect(dialog).toHaveAttribute('hidden');

    toggle.focus();
    await user.keyboard('{Enter}');

    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    expect(dialog).not.toHaveAttribute('hidden');
    expect(screen.getByRole('dialog', { name: 'Capabilities' })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Close' })).toHaveFocus());
    expect(document.body.style.overflow).toBe('hidden');

    await user.keyboard('{Shift>}{Tab}{/Shift}');
    expect(screen.getByRole('button', { name: 'Ticket Assistant' })).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect(dialog).toHaveAttribute('hidden');
    await waitFor(() => expect(toggle).toHaveFocus());
    expect(document.body.style.overflow).toBe('');
  });

  it('closes after capability selection and keeps the desktop rail out of a dialog', async () => {
    mockViewport(true);
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const { unmount } = render(
      shell(
        <button className="nav__item" onClick={onSelect}>
          Ticket Assistant
        </button>,
      ),
    );

    const toggle = screen.getByRole('button', { name: 'Show capabilities' });
    await user.click(toggle);
    await user.click(screen.getByRole('button', { name: 'Ticket Assistant' }));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await waitFor(() => expect(toggle).toHaveFocus());

    unmount();
    vi.unstubAllGlobals();
    mockViewport(false);
    render(shell());

    expect(screen.getByRole('navigation', { name: 'Office Agent capabilities' })).toBeInTheDocument();
    expect(screen.queryByRole('dialog', { name: 'Capabilities' })).not.toBeInTheDocument();
  });
});
