/// <reference types="vite/client" />

interface ImportMetaEnv {
  /**
   * Which client backs the workspace: `http` (default — the local FastAPI
   * adapter) or `mock` (typed fixtures, for offline demos).
   */
  readonly VITE_API_MODE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
