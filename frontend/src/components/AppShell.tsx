import { Menu, X } from 'lucide-react';
import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import { useMediaQuery } from '../hooks/useMediaQuery';

interface AppShellProps {
  banner: ReactNode;
  sidebar: ReactNode;
  main: ReactNode;
  aside: ReactNode;
  onReset: () => void;
}

const MOBILE_LAYOUT_QUERY = '(max-width: 860px)';

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
  const isMobile = useMediaQuery(MOBILE_LAYOUT_QUERY);
  const navToggleRef = useRef<HTMLButtonElement>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const drawerCloseRef = useRef<HTMLButtonElement>(null);

  const closeSidebar = useCallback((restoreFocus = true) => {
    setSidebarOpen(false);
    if (restoreFocus) {
      window.requestAnimationFrame(() => navToggleRef.current?.focus());
    }
  }, []);

  useEffect(() => {
    if (!isMobile || !sidebarOpen) {
      return undefined;
    }

    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    window.requestAnimationFrame(() => drawerCloseRef.current?.focus());

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        closeSidebar();
        return;
      }

      if (event.key !== 'Tab' || !drawerRef.current) {
        return;
      }

      const focusable = Array.from(
        drawerRef.current.querySelectorAll<HTMLElement>(
          'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
        ),
      );

      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      const active = document.activeElement;

      if (event.shiftKey && (active === first || !drawerRef.current.contains(active))) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && (active === last || !drawerRef.current.contains(active))) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [closeSidebar, isMobile, sidebarOpen]);

  useEffect(() => {
    if (!isMobile && sidebarOpen) {
      setSidebarOpen(false);
    }
  }, [isMobile, sidebarOpen]);

  const capabilityNavigation = (
    <nav
      id="capability-sidebar"
      className={isMobile ? 'app__sidebar app__sidebar--drawer' : 'app__sidebar'}
      aria-label="Office Agent capabilities"
      onClick={(event) => {
        if (isMobile && event.target instanceof Element && event.target.closest('.nav__item')) {
          closeSidebar();
        }
      }}
    >
      {sidebar}
    </nav>
  );

  return (
    <div className="app">
      <header className="app__header">
        <div className="app__brand">
          <button
            ref={navToggleRef}
            type="button"
            className="app__nav-toggle"
            aria-expanded={sidebarOpen}
            aria-controls="capability-sidebar"
            onClick={() => (sidebarOpen ? closeSidebar() : setSidebarOpen(true))}
          >
            <Menu size={20} strokeWidth={2.1} aria-hidden="true" />
            <span className="sr-only">
              {sidebarOpen ? 'Hide capabilities' : 'Show capabilities'}
            </span>
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
        {isMobile ? (
          <>
            <div
              className="app__sidebar-backdrop"
              hidden={!sidebarOpen}
              aria-hidden="true"
              onClick={() => closeSidebar()}
            />
            <div
              ref={drawerRef}
              className="app__sidebar-dialog"
              role="dialog"
              aria-modal="true"
              aria-label="Capabilities"
              hidden={!sidebarOpen}
            >
              <div className="app__sidebar-head">
                <span className="app__sidebar-title">Capabilities</span>
                <button
                  ref={drawerCloseRef}
                  type="button"
                  className="app__sidebar-close"
                  onClick={() => closeSidebar()}
                >
                  <X size={18} strokeWidth={2.2} aria-hidden="true" />
                  <span>Close</span>
                </button>
              </div>
              {capabilityNavigation}
            </div>
          </>
        ) : (
          capabilityNavigation
        )}

        <main className="app__main">{main}</main>

        <aside className="app__aside" aria-label="Execution details">
          {aside}
        </aside>
      </div>
    </div>
  );
}
