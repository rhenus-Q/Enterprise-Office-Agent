import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The `/api` dev proxy is declared now but inert in Phase 1: the UI runs entirely
// on the typed mock client until Phase 3 introduces the HTTP client. Keeping the
// proxy here means Phase 3 is a client swap, not a build-config change.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: false,
    // Vitest owns the unit suite under src/ only. The Playwright responsive suite
    // lives in e2e/ and is run by `npm run test:responsive`, never by Vitest —
    // its `@playwright/test` `test`/`expect` are incompatible with Vitest's.
    include: ['src/**/*.{test,spec}.{ts,tsx}'],
  },
});
