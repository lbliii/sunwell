import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vite';
import { resolve } from 'path';

// https://vitejs.dev/config/
// Note: Aliases are configured in svelte.config.js kit.alias for the app,
// but test configuration needs explicit aliases below.
export default defineConfig({
  plugins: [sveltekit()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
  },
  resolve: {
    alias: {
      // These are needed for tests (SvelteKit aliases don't apply to vitest)
      '$lib': resolve(__dirname, './src/lib'),
      '$stores': resolve(__dirname, './src/lib/stores'),
      '$components': resolve(__dirname, './src/lib/components'),
    },
  },
  test: {
    include: ['src/**/*.{test,spec}.{js,ts}'],
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    alias: {
      // Duplicate aliases for vitest (it doesn't always use resolve.alias)
      '$lib': resolve(__dirname, './src/lib'),
      '$stores': resolve(__dirname, './src/lib/stores'),
      '$components': resolve(__dirname, './src/lib/components'),
    },
  },
});
