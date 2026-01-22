/**
 * Home Components Index (RFC-080)
 * 
 * Re-exports Home-specific components and universal blocks/surfaces.
 */

// Home-specific components
export { default as ActionToast } from './ActionToast.svelte';

// Re-export universal block components for convenience
export { default as BlockSurface } from '../BlockSurface.svelte';
export * from '../blocks';
