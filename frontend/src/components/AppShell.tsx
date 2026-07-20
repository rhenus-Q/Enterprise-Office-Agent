import { useState, type ReactNode } from 'react';

interface AppShellProps {
  banner: ReactNode;
  sidebar: ReactNode;
  main: ReactNode;
  aside: ReactNode;
  onReset: () => void;
}

/**
 * The three-pane workspace: a compact capability rail (nav), the request and
 * results column (main), and execution details (aside).
 *
 * Landmarks are semantic so screen readers can jump between panes. On narrow
 * viewports the rail collapses behind a toggle; the toggle itself is hidden by
 * CSS once all three columns fit.
 *
 * The brand area doubles as the "return home" control. The heading wraps the
 * button (rather than the reverse) so the markup stays valid — a button may only
 * contain phrasing content — while the page keeps a real `h1`.
 */
export function AppShell({ banner, sidebar, main, aside, onReset }: AppShellProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <button
            type="button"
            className="app__nav-toggle"
            aria-expanded={sidebarOpen}
            aria-controls="capability-sidebar"
            onClick={() => setSidebarOpen((open) => !open)}
          >
            {sidebarOpen ? 'Hide capabilities' : 'Show capabilities'}
          </button>

          <h1 className="app__brand-heading">
            <button
              type="button"
              className="app__reset"
              aria-label="Reset workspace"
              title="Reset workspace"
              onClick={onReset}
            >
              <span className="app__logo" aria-hidden="true">
                OA
              </span>
              <span className="app__brand-text">
                <span className="app__title">Enterprise Office Agent</span>
                <span className="app__subtitle">Observability workspace</span>
              </span>
            </button>
          </h1>
        </div>
        {banner}
      </header>

      <div className="app__body">
        <nav
          id="capability-sidebar"
          className={sidebarOpen ? 'app__sidebar is-open' : 'app__sidebar'}
          aria-label="Office Agent capabilities"
        >
          {sidebar}
        </nav>

        <main className="app__main">{main}</main>

        <aside className="app__aside" aria-label="Execution details">
          {aside}
        </aside>
      </div>
    </div>
  );
}
