import { defineConfig, devices } from '@playwright/test';

/**
 * Real-browser responsive verification for the observability workspace.
 *
 * Chromium only, run against the Vite dev server in typed **mock** mode. Mock
 * mode is set through the web server's environment (`VITE_API_MODE=mock`) rather
 * than an inline shell prefix, so it works identically on Windows, macOS, and
 * Linux — the app then uses the typed fixtures and needs no FastAPI server, no
 * API key, and no network beyond localhost.
 *
 * This suite SUPPLEMENTS the Vitest unit suite (`npm test`); it never replaces
 * it. Reporter is `list` and trace/screenshot/video are off, so a normal run
 * writes no report, screenshots, videos, or traces to commit.
 */
export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    trace: 'off',
    screenshot: 'off',
    video: 'off',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    // Playwright merges this over process.env, so PATH etc. are preserved and
    // only VITE_API_MODE is added. Bind Vite explicitly to IPv4 loopback
    // (`--host 127.0.0.1`) so the readiness probe below matches on every OS —
    // the default `localhost` bind can resolve to IPv6 `::1` on Windows.
    // `--strictPort` keeps the URL deterministic.
    command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
    url: 'http://127.0.0.1:5173',
    env: { VITE_API_MODE: 'mock' },
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
