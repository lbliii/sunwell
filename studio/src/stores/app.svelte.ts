/**
 * App Store — global application state (Svelte 5 runes)
 */

import { Route } from '$lib/constants';
import type { Route as RouteType } from '$lib/constants';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _route = $state<RouteType>(Route.HOME);
let _isInitialized = $state(false);
let _params = $state<Record<string, unknown>>({});

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const app = {
  get route() { return _route; },
  get isInitialized() { return _isInitialized; },
  get version() { return '0.1.0'; },
  get params() { return _params; },
  get isHome() { return _route === Route.HOME; },
  get isProject() { return _route === Route.PROJECT; },
  get isPreview() { return _route === Route.PREVIEW; },
  get isPlanning() { return _route === Route.PLANNING; },
  get isLibrary() { return _route === Route.LIBRARY; },
  get isInterface() { return _route === Route.INTERFACE; },
  get isWriter() { return _route === Route.WRITER; },
  get isDemo() { return _route === Route.DEMO; },
  get isProjects() { return _route === Route.PROJECTS; },
  get isEvaluation() { return _route === Route.EVALUATION; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export function navigate(route: RouteType, params?: Record<string, unknown>): void {
  _route = route;
  _params = params ?? {};
}

export function goHome(): void {
  _route = Route.HOME;
}

export function goToProject(): void {
  _route = Route.PROJECT;
}

export function goToPreview(): void {
  _route = Route.PREVIEW;
}

export function goToPlanning(): void {
  _route = Route.PLANNING;
}

export function goToLibrary(): void {
  _route = Route.LIBRARY;
}

export function goToInterface(): void {
  _route = Route.INTERFACE;
}

export function goToWriter(filePath?: string, lens?: string): void {
  _route = Route.WRITER;
  _params = { filePath, lens };
}

export function goToDemo(): void {
  _route = Route.DEMO;
}

export function goToProjects(): void {
  _route = Route.PROJECTS;
}

export function goToEvaluation(): void {
  _route = Route.EVALUATION;
}

export function setInitialized(value = true): void {
  _isInitialized = value;
}
