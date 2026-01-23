/**
 * Workspace Store — Workspace-aware scanning state management (RFC-103)
 *
 * Manages state for workspace detection, linking, and drift detection:
 * - Detected workspace links
 * - Confirmed source connections
 * - Drift detection results
 * - Toast notification state
 */

import { invoke } from '@tauri-apps/api/core';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export interface WorkspaceLink {
  source: string;
  target: string;
  relationship: string;
  confidence: number;
  evidence: string;
  language: string | null;
  confirmed: boolean;
}

export interface Workspace {
  id: string;
  primary: string;
  topology: string;
  links: WorkspaceLink[];
  created_at: string;
  updated_at: string;
}

export type ToastState = 'hidden' | 'detecting' | 'showing' | 'linking' | 'dismissed';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _projectPath = $state<string | null>(null);
let _workspace = $state<Workspace | null>(null);
let _detectedLinks = $state<WorkspaceLink[]>([]);
let _selectedLinks = $state<Set<string>>(new Set());
let _toastState = $state<ToastState>('hidden');
let _isLoading = $state<boolean>(false);
let _error = $state<string | null>(null);

// Preferences
let _dontShowAgain = $state<boolean>(false);

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function getHighConfidenceLinks(): WorkspaceLink[] {
  return _detectedLinks.filter((l) => l.confidence >= 0.7);
}

function getConfirmedLinks(): WorkspaceLink[] {
  return _workspace?.links.filter((l) => l.confirmed) ?? [];
}

function getSourceRoots(): string[] {
  return getConfirmedLinks().map((l) => l.target);
}

function hasWorkspaceConfig(): boolean {
  return _workspace !== null && _workspace.links.length > 0;
}

function shouldShowToast(): boolean {
  return (
    _toastState === 'showing' &&
    !_dontShowAgain &&
    _detectedLinks.length > 0
  );
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const workspaceStore = {
  // Raw state
  get projectPath() {
    return _projectPath;
  },
  get workspace() {
    return _workspace;
  },
  get detectedLinks() {
    return _detectedLinks;
  },
  get selectedLinks() {
    return _selectedLinks;
  },
  get toastState() {
    return _toastState;
  },
  get isLoading() {
    return _isLoading;
  },
  get error() {
    return _error;
  },

  // Computed
  get highConfidenceLinks() {
    return getHighConfidenceLinks();
  },
  get confirmedLinks() {
    return getConfirmedLinks();
  },
  get sourceRoots() {
    return getSourceRoots();
  },
  get hasWorkspaceConfig() {
    return hasWorkspaceConfig();
  },
  get shouldShowToast() {
    return shouldShowToast();
  },
  get dontShowAgain() {
    return _dontShowAgain;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Initialize workspace detection for a project.
 * Called when a docs project is opened.
 */
export async function initWorkspace(projectPath: string): Promise<void> {
  _projectPath = projectPath;
  _error = null;
  _toastState = 'detecting';
  _isLoading = true;

  try {
    // Check for existing workspace config
    const workspace = await invoke<Workspace | null>('get_workspace', {
      projectPath,
    });

    if (workspace && workspace.links.length > 0) {
      _workspace = workspace;
      _toastState = 'hidden'; // Already configured, no toast needed
      return;
    }

    // No existing config, run detection
    const links = await invoke<WorkspaceLink[]>('detect_workspace_links', {
      projectPath,
    });

    _detectedLinks = links;

    // Pre-select high confidence links
    const selected = new Set<string>();
    for (const link of links) {
      if (link.confidence >= 0.9) {
        selected.add(link.target);
      }
    }
    _selectedLinks = selected;

    // Show toast if we found anything
    if (links.length > 0 && !_dontShowAgain) {
      _toastState = 'showing';
    } else {
      _toastState = 'hidden';
    }
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    _toastState = 'hidden';
    console.error('Workspace detection failed:', e);
  } finally {
    _isLoading = false;
  }
}

/**
 * Toggle selection of a detected link.
 */
export function toggleLinkSelection(target: string): void {
  const newSelected = new Set(_selectedLinks);
  if (newSelected.has(target)) {
    newSelected.delete(target);
  } else {
    newSelected.add(target);
  }
  _selectedLinks = newSelected;
}

/**
 * Select all detected links.
 */
export function selectAllLinks(): void {
  _selectedLinks = new Set(_detectedLinks.map((l) => l.target));
}

/**
 * Deselect all links.
 */
export function deselectAllLinks(): void {
  _selectedLinks = new Set();
}

/**
 * Link selected projects to workspace.
 */
export async function linkSelected(): Promise<void> {
  if (!_projectPath || _selectedLinks.size === 0) {
    return;
  }

  _toastState = 'linking';
  _error = null;

  try {
    // Link each selected project
    for (const target of _selectedLinks) {
      await invoke('link_workspace', {
        projectPath: _projectPath,
        targetPath: target,
      });
    }

    // Reload workspace config
    const workspace = await invoke<Workspace | null>('get_workspace', {
      projectPath: _projectPath,
    });
    _workspace = workspace;

    _toastState = 'hidden';
    _detectedLinks = [];
    _selectedLinks = new Set();
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    _toastState = 'showing'; // Return to showing state on error
    console.error('Linking failed:', e);
  }
}

/**
 * Unlink a source from workspace.
 */
export async function unlinkSource(target: string): Promise<void> {
  if (!_projectPath) {
    return;
  }

  try {
    await invoke('unlink_workspace', {
      projectPath: _projectPath,
      targetPath: target,
    });

    // Reload workspace config
    const workspace = await invoke<Workspace | null>('get_workspace', {
      projectPath: _projectPath,
    });
    _workspace = workspace;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Unlinking failed:', e);
  }
}

/**
 * Dismiss the toast and optionally remember the preference.
 */
export function dismissToast(dontShowAgain: boolean = false): void {
  _toastState = 'dismissed';
  _dontShowAgain = dontShowAgain;

  // Clear after animation
  setTimeout(() => {
    _toastState = 'hidden';
  }, 300);
}

/**
 * Skip workspace linking for this session.
 */
export function skipLinking(): void {
  _toastState = 'hidden';
  _detectedLinks = [];
  _selectedLinks = new Set();
}

/**
 * Reset workspace state (e.g., when closing project).
 */
export function resetWorkspace(): void {
  _projectPath = null;
  _workspace = null;
  _detectedLinks = [];
  _selectedLinks = new Set();
  _toastState = 'hidden';
  _error = null;
}

/**
 * Manually trigger detection (re-scan for related projects).
 */
export async function redetect(): Promise<void> {
  if (!_projectPath) {
    return;
  }

  _isLoading = true;
  _error = null;

  try {
    const links = await invoke<WorkspaceLink[]>('detect_workspace_links', {
      projectPath: _projectPath,
    });
    _detectedLinks = links;

    if (links.length > 0) {
      _toastState = 'showing';
    }
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    console.error('Re-detection failed:', e);
  } finally {
    _isLoading = false;
  }
}

/**
 * Get State DAG with drift detection enabled.
 */
export async function getStateDagWithDrift(): Promise<unknown> {
  if (!_projectPath) {
    throw new Error('No project path set');
  }

  const sourceRoots = getSourceRoots();

  return invoke('get_state_dag_with_sources', {
    projectPath: _projectPath,
    linkPaths: sourceRoots,
  });
}
