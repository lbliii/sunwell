/**
 * App Store — global application state (Svelte 5 runes)
 *
 * Navigation integrated with SvelteKit's file-based routing.
 * Uses goto() for navigation and replaceState() for non-history updates.
 *
 * URL Format: /{route}?{params}
 */

import { goto, replaceState } from '$app/navigation';
import { page } from '$app/stores';
import { get } from 'svelte/store';
import { Route } from '$lib/constants';
import type { Route as RouteType } from '$lib/constants';

// ═══════════════════════════════════════════════════════════════
// ROUTE MAPPING
// ═══════════════════════════════════════════════════════════════

/** Routes that don't require project context */
const GLOBAL_ROUTES: Set<RouteType> = new Set([
  Route.HOME,
  Route.PROJECTS,
  Route.DEMO,
  Route.GALLERY,
]);

/** Map Route constants to URL paths */
const ROUTE_PATHS: Record<RouteType, string> = {
  [Route.HOME]: '/',
  [Route.PROJECT]: '/project',
  [Route.PROJECTS]: '/projects',
  [Route.PREVIEW]: '/preview',
  [Route.PLANNING]: '/planning',
  [Route.LIBRARY]: '/library',
  [Route.INTERFACE]: '/interface',
  [Route.WRITER]: '/writer',
  [Route.DEMO]: '/demo',
  [Route.GALLERY]: '/gallery',
  [Route.EVALUATION]: '/evaluation',
  [Route.OBSERVATORY]: '/observatory',
};

/** Reverse mapping: path → Route constant */
const PATH_ROUTES: Record<string, RouteType> = {
  '/': Route.HOME,
  '/project': Route.PROJECT,
  '/projects': Route.PROJECTS,
  '/preview': Route.PREVIEW,
  '/planning': Route.PLANNING,
  '/library': Route.LIBRARY,
  '/interface': Route.INTERFACE,
  '/writer': Route.WRITER,
  '/demo': Route.DEMO,
  '/gallery': Route.GALLERY,
  '/evaluation': Route.EVALUATION,
  '/observatory': Route.OBSERVATORY,
};

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _isInitialized = $state(false);
let _projectSlug = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

/** Get current route from SvelteKit page store */
function getCurrentRoute(): RouteType {
  const pathname = get(page)?.url?.pathname ?? '/';
  return PATH_ROUTES[pathname] ?? Route.HOME;
}

/** Get current params from SvelteKit page store */
function getCurrentParams(): Record<string, string> {
  const searchParams = get(page)?.url?.searchParams;
  if (!searchParams) return {};
  const params: Record<string, string> = {};
  searchParams.forEach((value, key) => {
    params[key] = value;
  });
  return params;
}

/** Build URL with path and optional query params */
function buildUrl(route: RouteType, params?: Record<string, string>): string {
  const path = ROUTE_PATHS[route] ?? '/';
  if (!params || Object.keys(params).length === 0) {
    return path;
  }
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, value);
    }
  }
  return `${path}?${searchParams.toString()}`;
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const app = {
  get route() { return getCurrentRoute(); },
  get isInitialized() { return _isInitialized; },
  get version() { return '0.1.0'; },
  get params() { return getCurrentParams(); },
  get projectSlug() { return _projectSlug; },
  get isHome() { return getCurrentRoute() === Route.HOME; },
  get isProject() { return getCurrentRoute() === Route.PROJECT; },
  get isPreview() { return getCurrentRoute() === Route.PREVIEW; },
  get isPlanning() { return getCurrentRoute() === Route.PLANNING; },
  get isLibrary() { return getCurrentRoute() === Route.LIBRARY; },
  get isInterface() { return getCurrentRoute() === Route.INTERFACE; },
  get isWriter() { return getCurrentRoute() === Route.WRITER; },
  get isDemo() { return getCurrentRoute() === Route.DEMO; },
  get isProjects() { return getCurrentRoute() === Route.PROJECTS; },
  get isEvaluation() { return getCurrentRoute() === Route.EVALUATION; },
  get isObservatory() { return getCurrentRoute() === Route.OBSERVATORY; },
  get hasProjectContext() { return _projectSlug !== null; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Navigate to a route using SvelteKit's goto().
 *
 * @param route - Target route
 * @param params - Optional URL params
 * @param projectSlug - Project slug (undefined = preserve current, null = clear)
 */
export function navigate(
  route: RouteType,
  params?: Record<string, string>,
  projectSlug?: string | null
): void {
  // Update project slug state
  if (projectSlug !== undefined) {
    _projectSlug = projectSlug;
  } else if (GLOBAL_ROUTES.has(route)) {
    _projectSlug = null;
  }

  const url = buildUrl(route, params);
  goto(url);
}

/**
 * Update URL params without creating history entry.
 * Use for tab changes, filters, and other UI state that shouldn't spam history.
 *
 * @param updates - Params to update (null values remove the param)
 */
export function updateParams(updates: Record<string, string | null>): void {
  const currentParams = getCurrentParams();
  const merged: Record<string, string> = { ...currentParams };

  for (const [key, value] of Object.entries(updates)) {
    if (value === null || value === '') {
      delete merged[key];
    } else {
      merged[key] = value;
    }
  }

  const url = buildUrl(getCurrentRoute(), merged);
  replaceState(url, {});
}

/**
 * Set the project slug directly (used by ProjectGate after resolving).
 *
 * @param slug - Project slug to set
 */
export function setProjectSlug(slug: string | null): void {
  _projectSlug = slug;
}

export function goHome(): void {
  navigate(Route.HOME, undefined, null); // Explicitly clear project context
}

export function goToProject(params?: Record<string, string>, projectSlug?: string): void {
  navigate(Route.PROJECT, params, projectSlug);
}

export function goToPreview(projectSlug?: string): void {
  navigate(Route.PREVIEW, undefined, projectSlug);
}

export function goToPlanning(params?: Record<string, string>, projectSlug?: string): void {
  navigate(Route.PLANNING, params, projectSlug);
}

export function goToLibrary(params?: Record<string, string>, projectSlug?: string): void {
  navigate(Route.LIBRARY, params, projectSlug);
}

export function goToInterface(projectSlug?: string): void {
  navigate(Route.INTERFACE, undefined, projectSlug);
}

export function goToWriter(filePath?: string, lens?: string, projectSlug?: string): void {
  const params: Record<string, string> = {};
  if (filePath) params.file = filePath;
  if (lens) params.lens = lens;
  navigate(Route.WRITER, Object.keys(params).length > 0 ? params : undefined, projectSlug);
}

export function goToDemo(): void {
  navigate(Route.DEMO, undefined, null); // Global route - no project context
}

export function goToProjects(): void {
  navigate(Route.PROJECTS, undefined, null); // Global route - no project context
}

export function goToEvaluation(params?: Record<string, string>, projectSlug?: string): void {
  navigate(Route.EVALUATION, params, projectSlug);
}

export function goToObservatory(params?: Record<string, string>, projectSlug?: string): void {
  navigate(Route.OBSERVATORY, params, projectSlug);
}

/**
 * Switch to a different project (RFC-133 Phase 2).
 * Navigates to the project's home view and updates URL with new slug.
 *
 * @param slug - Project slug to switch to
 * @param route - Optional route to navigate to (defaults to PROJECT)
 */
export function switchProject(slug: string, route: RouteType = Route.PROJECT): void {
  navigate(route, undefined, slug);
}

export function setInitialized(value = true): void {
  _isInitialized = value;
}
