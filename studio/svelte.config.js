import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
  preprocess: vitePreprocess(),
  compilerOptions: {
    runes: true,
  },
  kit: {
    // SPA mode: all routes handled client-side
    adapter: adapter({
      fallback: 'index.html',
      strict: false,
    }),
    alias: {
      '$lib': 'src/lib',
      '$stores': 'src/lib/stores',
      '$components': 'src/lib/components',
    },
    prerender: {
      entries: [],
    },
  },
};
