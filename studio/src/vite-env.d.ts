/// <reference types="vite/client" />

// Extend Vite's built-in ImportMetaEnv with custom env variables
// Note: DEV, PROD, MODE, SSR, BASE_URL are provided by Vite - don't redeclare them
interface ImportMetaEnv {
  readonly VITE_API_BASE: string;
  readonly VITE_USE_HTTP: string;
}
