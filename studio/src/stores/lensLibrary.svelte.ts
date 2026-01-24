/**
 * Lens Library Store — Full lens management (RFC-070)
 * 
 * Extends the basic lens store with library browsing,
 * editing, versioning, and management features.
 */

import { apiGet, apiPost, apiDelete } from '$lib/socket';
import type { 
  LensLibraryEntry, 
  LensDetail, 
  LensVersionInfo,
  ForkResult,
  SaveResult,
} from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

export type LensLibraryView = 'library' | 'detail' | 'editor' | 'versions';

interface LensLibraryState {
  /** All lenses in the library */
  entries: LensLibraryEntry[];
  
  /** Currently selected lens for detail view */
  selectedLens: LensLibraryEntry | null;
  
  /** Full detail of selected lens */
  detail: LensDetail | null;
  
  /** Raw YAML content for editor */
  editorContent: string | null;
  
  /** Version history for selected lens */
  versions: LensVersionInfo[];
  
  /** Filter state */
  filter: {
    source: 'all' | 'builtin' | 'user';
    domain: string | null;
    search: string;
  };
  
  /** Loading states */
  isLoading: boolean;
  isLoadingDetail: boolean;
  isLoadingVersions: boolean;
  isSaving: boolean;
  
  /** Error state */
  error: string | null;
  
  /** UI state */
  view: LensLibraryView;
}

function createInitialState(): LensLibraryState {
  return {
    entries: [],
    selectedLens: null,
    detail: null,
    editorContent: null,
    versions: [],
    filter: {
      source: 'all',
      domain: null,
      search: '',
    },
    isLoading: false,
    isLoadingDetail: false,
    isLoadingVersions: false,
    isSaving: false,
    error: null,
    view: 'library',
  };
}

let _state = $state<LensLibraryState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const lensLibrary = {
  get entries() { return _state.entries; },
  get selectedLens() { return _state.selectedLens; },
  get detail() { return _state.detail; },
  get editorContent() { return _state.editorContent; },
  get versions() { return _state.versions; },
  get filter() { return _state.filter; },
  get isLoading() { return _state.isLoading; },
  get isLoadingDetail() { return _state.isLoadingDetail; },
  get isLoadingVersions() { return _state.isLoadingVersions; },
  get isSaving() { return _state.isSaving; },
  get error() { return _state.error; },
  get view() { return _state.view; },
};

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

/** Filtered entries based on current filter state */
export function getFilteredEntries(): LensLibraryEntry[] {
  let entries = _state.entries;
  
  // Filter by source
  if (_state.filter.source !== 'all') {
    entries = entries.filter(e => e.source === _state.filter.source);
  }
  
  // Filter by domain
  if (_state.filter.domain) {
    entries = entries.filter(e => e.domain === _state.filter.domain);
  }
  
  // Filter by search
  if (_state.filter.search) {
    const q = _state.filter.search.toLowerCase();
    entries = entries.filter(e => 
      e.name.toLowerCase().includes(q) ||
      e.description?.toLowerCase().includes(q) ||
      e.tags.some(t => t.toLowerCase().includes(q))
    );
  }
  
  return entries;
}

/** Get unique domains for filter dropdown */
export function getAvailableDomains(): string[] {
  const domains = new Set<string>();
  for (const entry of _state.entries) {
    if (entry.domain) domains.add(entry.domain);
  }
  return Array.from(domains).sort();
}

/** The global default lens */
export function getDefaultLens(): LensLibraryEntry | null {
  return _state.entries.find(e => e.is_default) ?? null;
}

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Load the full lens library.
 */
export async function loadLibrary(): Promise<void> {
  if (_state.isLoading) return;
  
  _state = { ..._state, isLoading: true, error: null };
  
  try {
    const entries = await apiGet<LensLibraryEntry[]>('/api/lenses/library') ?? [];
    _state = { ..._state, entries, isLoading: false };
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      isLoading: false,
    };
    console.error('Failed to load lens library:', e);
  }
}

/**
 * Select a lens and load its details.
 */
export async function selectLens(entry: LensLibraryEntry): Promise<void> {
  _state = { 
    ..._state, 
    selectedLens: entry, 
    view: 'detail', 
    isLoadingDetail: true,
  };
  
  try {
    // Extract slug from path (e.g., "tech-writer" from "/path/to/tech-writer.lens")
    const slug = entry.path.split('/').pop()?.replace('.lens', '') ?? entry.name;
    const detail = await apiGet<LensDetail>(`/api/lenses/${encodeURIComponent(slug)}`);
    _state = { ..._state, detail: detail ?? null, isLoadingDetail: false };
  } catch (e) {
    console.error('Failed to load lens detail:', e);
    _state = { ..._state, detail: null, isLoadingDetail: false };
  }
}

/**
 * Open the lens editor.
 */
export async function openEditor(entry: LensLibraryEntry): Promise<void> {
  if (!entry.is_editable) return;
  
  _state = {
    ..._state,
    selectedLens: entry,
    view: 'editor',
    isLoadingDetail: true,
  };
  
  try {
    // Get the slug name from path
    const slug = entry.path.split('/').pop()?.replace('.lens', '') ?? entry.name;
    const content = await apiGet<string>(`/api/lenses/${encodeURIComponent(slug)}/content`);
    _state = { ..._state, editorContent: content ?? null, isLoadingDetail: false };
  } catch (e) {
    console.error('Failed to load lens content:', e);
    _state = {
      ..._state,
      editorContent: null,
      error: `Failed to load lens: ${e}`,
      isLoadingDetail: false,
    };
  }
}

/**
 * Save lens changes with version tracking.
 */
export async function saveLens(
  content: string,
  message?: string,
  bump: 'major' | 'minor' | 'patch' = 'patch',
): Promise<SaveResult | null> {
  const selectedLens = _state.selectedLens;
  if (!selectedLens?.is_editable) return null;
  
  _state = { ..._state, isSaving: true, error: null };
  
  try {
    const slug = selectedLens.path
      .split('/').pop()?.replace('.lens', '') ?? selectedLens.name;
    
    const result = await apiPost<SaveResult>('/api/lenses/save', {
      name: slug,
      content,
      message: message ?? null,
      bump,
    });
    
    if (result.success) {
      // Refresh library to get updated version
      await loadLibrary();
      _state = { ..._state, editorContent: content, isSaving: false };
    } else {
      _state = { ..._state, error: result.message, isSaving: false };
    }
    
    return result;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      isSaving: false,
    };
    console.error('Failed to save lens:', e);
    return null;
  }
}

/**
 * Fork a lens to create an editable copy.
 */
export async function forkLens(
  sourceName: string,
  newName: string,
  message?: string,
): Promise<ForkResult | null> {
  _state = { ..._state, isSaving: true, error: null };
  
  try {
    const result = await apiPost<ForkResult>('/api/lenses/fork', {
      sourceName,
      newName,
      message: message ?? null,
    });
    
    if (result.success) {
      // Refresh library to show new lens
      await loadLibrary();
    } else {
      _state = { ..._state, error: result.message };
    }
    
    _state = { ..._state, isSaving: false };
    return result;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
      isSaving: false,
    };
    console.error('Failed to fork lens:', e);
    return null;
  }
}

/**
 * Delete a user lens.
 */
export async function deleteLens(name: string): Promise<boolean> {
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    await apiDelete(`/api/lenses/${encodeURIComponent(slug)}`);
    
    // Refresh library
    await loadLibrary();
    
    // Clear selection if deleted lens was selected
    if (_state.selectedLens?.name === name) {
      _state = {
        ..._state,
        selectedLens: null,
        view: 'library',
      };
    }
    
    return true;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
    console.error('Failed to delete lens:', e);
    return false;
  }
}

/**
 * Load version history for a lens.
 */
export async function loadVersions(name: string): Promise<void> {
  _state = { ..._state, isLoadingVersions: true };
  
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    const versions = await apiGet<LensVersionInfo[]>(`/api/lenses/${encodeURIComponent(slug)}/versions`) ?? [];
    _state = { ..._state, versions, view: 'versions', isLoadingVersions: false };
  } catch (e) {
    console.error('Failed to load versions:', e);
    _state = { ..._state, versions: [], isLoadingVersions: false };
  }
}

/**
 * Rollback a lens to a previous version.
 */
export async function rollbackLens(name: string, version: string): Promise<boolean> {
  try {
    const slug = name.toLowerCase().replace(/\s+/g, '-');
    await apiPost('/api/lenses/rollback', { name: slug, version });
    
    // Refresh data
    await loadLibrary();
    await loadVersions(name);
    
    return true;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
    console.error('Failed to rollback lens:', e);
    return false;
  }
}

/**
 * Set the global default lens.
 */
export async function setDefaultLens(name: string | null): Promise<boolean> {
  try {
    await apiPost('/api/lenses/set-default', { name });
    
    // Update local state
    _state = {
      ..._state,
      entries: _state.entries.map(e => ({
        ...e,
        is_default: e.name === name,
      })),
    };
    
    return true;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
    console.error('Failed to set default lens:', e);
    return false;
  }
}

/**
 * Update filter state.
 */
export function setFilter(filter: Partial<LensLibraryState['filter']>): void {
  _state = {
    ..._state,
    filter: { ..._state.filter, ...filter },
  };
}

/**
 * Navigate back to library list view.
 */
export function backToList(): void {
  _state = {
    ..._state,
    view: 'library',
    selectedLens: null,
    detail: null,
    editorContent: null,
    versions: [],
  };
}

/**
 * Clear error state.
 */
export function clearError(): void {
  _state = { ..._state, error: null };
}

/**
 * Reset library state.
 */
export function resetLibrary(): void {
  _state = createInitialState();
}

// =============================================================================
// RFC-100: Export and Usage Tracking
// =============================================================================

interface ExportResult {
  success: boolean;
  path: string;
  message: string;
}

/**
 * Export a lens to a file.
 */
export async function exportLens(
  name: string,
  outputPath?: string,
  format: 'yaml' | 'json' = 'yaml',
): Promise<ExportResult | null> {
  try {
    const result = await apiPost<ExportResult>('/api/lenses/export', {
      name,
      outputPath: outputPath ?? null,
      format,
    });
    return result;
  } catch (e) {
    _state = {
      ..._state,
      error: e instanceof Error ? e.message : String(e),
    };
    console.error('Failed to export lens:', e);
    return null;
  }
}

/**
 * Record lens activation for usage tracking.
 * Called when a lens is selected or activated.
 */
export async function recordLensUsage(name: string): Promise<void> {
  try {
    await apiPost('/api/lenses/usage', { name });
  } catch (e) {
    // Non-critical - don't fail if usage tracking fails
    console.warn('Failed to record lens usage:', e);
  }
}
