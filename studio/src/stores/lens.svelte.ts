/**
 * Lens Store — Expertise Management (RFC-064)
 * 
 * Manages lens state: available lenses, selection, and project defaults.
 */

import { listLenses, getLens, apiGet, apiPost } from '$lib/socket';
import type { LensSummary, LensDetail, ProjectLensConfig, LensSelection } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface LensState {
  /** All available lenses */
  available: LensSummary[];
  
  /** Currently selected lens for next run */
  selection: LensSelection;
  
  /** Active lens during execution (from agent events) */
  activeLens: string | null;
  
  /** Lens detail being previewed */
  previewLens: LensDetail | null;
  
  /** Loading states */
  isLoading: boolean;
  isLoadingDetail: boolean;
  
  /** Error state */
  error: string | null;
}

function createLensState(): LensState {
  return {
    available: [],
    selection: { lens: null, autoSelect: true },
    activeLens: null,
    previewLens: null,
    isLoading: false,
    isLoadingDetail: false,
    error: null,
  };
}

let _state = $state<LensState>(createLensState());

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const lens = {
  get available() { return _state.available; },
  get selection() { return _state.selection; },
  get activeLens() { return _state.activeLens; },
  get previewLens() { return _state.previewLens; },
  get isLoading() { return _state.isLoading; },
  get isLoadingDetail() { return _state.isLoadingDetail; },
  get error() { return _state.error; },
  
  // Computed
  get hasLenses() { return _state.available.length > 0; },
  get selectedLensSummary(): LensSummary | undefined {
    if (!_state.selection.lens) return undefined;
    return _state.available.find(l => l.name === _state.selection.lens);
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load all available lenses.
 */
export async function loadLenses(): Promise<void> {
  _state = { ..._state, isLoading: true, error: null };
  
  try {
    const rawLenses = await listLenses();
    // Map API response to LensSummary with defaults for missing fields
    const lenses: LensSummary[] = rawLenses.map(l => {
      const partial = l as unknown as Partial<LensSummary>;
      return {
        name: l.name,
        description: l.description || null,
        // Default values for fields not returned by simple API
        domain: partial.domain ?? null,
        version: partial.version ?? '1.0.0',
        path: partial.path ?? l.id,
        heuristics_count: partial.heuristics_count ?? 0,
        skills_count: partial.skills_count ?? 0,
      };
    });
    _state = { ..._state, available: lenses, isLoading: false };
  } catch (e) {
    _state = { 
      ..._state, 
      error: e instanceof Error ? e.message : String(e),
      isLoading: false,
    };
    console.error('Failed to load lenses:', e);
  }
}

/**
 * Load details for a specific lens.
 */
export async function loadLensDetail(name: string): Promise<void> {
  // Prevent concurrent loads
  if (_state.isLoadingDetail) return;
  
  _state = { ..._state, isLoadingDetail: true };
  
  try {
    const rawDetail = await getLens(name);
    const partial = rawDetail as unknown as Partial<LensDetail>;
    // Map API response to LensDetail with defaults for missing fields
    const detail: LensDetail = {
      name: rawDetail.name,
      skills: rawDetail.skills || [],
      // Default values for fields not returned by simple API
      domain: partial.domain ?? null,
      version: partial.version ?? '1.0.0',
      description: partial.description ?? null,
      author: partial.author ?? null,
      heuristics: partial.heuristics ?? [],
      communication_style: partial.communication_style ?? null,
    };
    _state = { ..._state, previewLens: detail, isLoadingDetail: false };
  } catch (e) {
    console.error('Failed to load lens detail:', e);
    _state = { ..._state, previewLens: null, isLoadingDetail: false };
  }
}

/**
 * Clear lens preview.
 */
export function clearLensPreview(): void {
  _state = { ..._state, previewLens: null };
}

/**
 * Select a lens for the next run.
 */
export function selectLens(lensName: string | null, autoSelect: boolean = false): void {
  _state = {
    ..._state,
    selection: {
      lens: lensName,
      autoSelect: autoSelect || lensName === null,
    },
  };
}

/**
 * Set the active lens (called from agent events).
 */
export function setActiveLens(name: string | null): void {
  _state = { ..._state, activeLens: name };
}

/**
 * Load project lens config.
 */
export async function loadProjectLensConfig(projectPath: string): Promise<ProjectLensConfig> {
  try {
    const result = await apiGet<ProjectLensConfig>(`/api/lenses/config?path=${encodeURIComponent(projectPath)}`);
    return result ?? { default_lens: null, auto_select: true };
  } catch (e) {
    console.error('Failed to load project lens config:', e);
    return { default_lens: null, auto_select: true };
  }
}

/**
 * Save project lens config.
 */
export async function saveProjectLensConfig(
  projectPath: string,
  lensName: string | null,
  autoSelect: boolean,
): Promise<void> {
  try {
    await apiPost('/api/lenses/config', {
      path: projectPath,
      lensName,
      autoSelect,
    });
  } catch (e) {
    console.error('Failed to save project lens config:', e);
  }
}

/**
 * Get lens by domain (for auto-suggestions).
 */
export function getLensByDomain(domain: string): LensSummary | undefined {
  return _state.available.find(l => l.domain === domain);
}

/**
 * Reset lens state.
 */
export function resetLensState(): void {
  _state = {
    ..._state,
    selection: { lens: null, autoSelect: true },
    activeLens: null,
    previewLens: null,
  };
}

/**
 * Get lenses grouped by domain.
 */
export function getLensesByDomain(): Map<string, LensSummary[]> {
  const grouped = new Map<string, LensSummary[]>();
  
  for (const l of _state.available) {
    const domain = l.domain || 'general';
    const existing = grouped.get(domain) || [];
    grouped.set(domain, [...existing, l]);
  }
  
  return grouped;
}

/**
 * Get domain icon for a lens.
 */
export function getDomainIcon(domain: string | null): string {
  const icons: Record<string, string> = {
    'software': '💻',
    'code': '💻',
    'documentation': '📝',
    'review': '🔍',
    'test': '🧪',
    'general': '🔮',
  };
  return icons[domain || 'general'] || '🔮';
}
