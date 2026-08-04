import react from '@vitejs/plugin-react';
import { defineConfig } from 'vitest/config';

// The default HTTP client uses this development proxy to reach the local
// FastAPI adapter; typed mock mode remains available for offline demos and tests.
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
