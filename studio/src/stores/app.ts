/**
 * App Store — global application state
 */

import { writable, derived } from 'svelte/store';
import type { Route } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

export const currentRoute = writable<Route>('home');
export const isInitialized = writable(false);
export const version = writable('0.1.0');

// ═══════════════════════════════════════════════════════════════
// NAVIGATION
// ═══════════════════════════════════════════════════════════════

/**
 * Navigate to a route.
 */
export function navigate(route: Route): void {
  currentRoute.set(route);
}

/**
 * Go back to home.
 */
export function goHome(): void {
  currentRoute.set('home');
}

/**
 * Go to project view.
 */
export function goToProject(): void {
  currentRoute.set('project');
}

/**
 * Go to preview view.
 */
export function goToPreview(): void {
  currentRoute.set('preview');
}

// ═══════════════════════════════════════════════════════════════
// DERIVED
// ═══════════════════════════════════════════════════════════════

export const isHome = derived(currentRoute, $r => $r === 'home');
export const isProject = derived(currentRoute, $r => $r === 'project');
export const isPreview = derived(currentRoute, $r => $r === 'preview');
