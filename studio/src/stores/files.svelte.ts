/**
 * Project Files Store — manages file tree state with event-driven refresh (Svelte 5 runes)
 * 
 * Consolidates file loading logic that was previously scattered across components.
 * Uses the same pattern as dag.svelte.ts - event-driven with debounced reload.
 * 
 * Usage:
 *   import { files, setFilesProjectPath, reloadFiles } from './files.svelte';
 *   
 *   // In component:
 *   $effect(() => { setFilesProjectPath(project.current?.path ?? null); });
 *   
 *   // Access reactive state:
 *   {#if files.isLoading}...{/if}
 *   {#each files.entries as file}...{/each}
 */

import { invoke } from '@tauri-apps/api/core';
import { debounce } from '$lib/debounce';
import type { FileEntry } from '$lib/types';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _entries = $state<FileEntry[]>([]);
let _isLoading = $state(false);
let _error = $state<string | null>(null);
let _projectPath = $state<string | null>(null);
let _lastLoadTime = $state<number | null>(null);

// ═══════════════════════════════════════════════════════════════
// DERIVED HELPERS
// ═══════════════════════════════════════════════════════════════

/** Flatten file tree to array of files (excluding directories) */
function flattenFiles(entries: FileEntry[]): FileEntry[] {
  const result: FileEntry[] = [];
  for (const entry of entries) {
    if (entry.is_dir && entry.children) {
      result.push(...flattenFiles(entry.children));
    } else if (!entry.is_dir) {
      result.push(entry);
    }
  }
  return result;
}

/** Count total files in tree */
function countFiles(entries: FileEntry[]): number {
  return flattenFiles(entries).length;
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const files = {
  /** File tree entries */
  get entries() { return _entries; },
  
  /** Whether files are currently loading */
  get isLoading() { return _isLoading; },
  
  /** Error message if load failed */
  get error() { return _error; },
  
  /** Current project path being tracked */
  get projectPath() { return _projectPath; },
  
  /** Timestamp of last successful load */
  get lastLoadTime() { return _lastLoadTime; },
  
  // Computed helpers
  /** Total file count (flattened) */
  get count() { return countFiles(_entries); },
  
  /** Flattened array of all files */
  get flat() { return flattenFiles(_entries); },
  
  /** Check if files are loaded and available */
  get hasFiles() { return _entries.length > 0; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Set the project path to track.
 * Triggers immediate load if path is new.
 */
export function setFilesProjectPath(path: string | null): void {
  if (path === _projectPath) return;
  
  _projectPath = path;
  _entries = [];
  _error = null;
  
  if (path) {
    reloadFilesInternal();
  }
}

/**
 * Internal reload function - fetches files from backend.
 */
async function reloadFilesInternal(): Promise<void> {
  if (!_projectPath) return;
  if (_isLoading) return; // Prevent concurrent loads
  
  _isLoading = true;
  _error = null;
  
  try {
    const result = await invoke<FileEntry[]>('list_project_files', {
      path: _projectPath,
      maxDepth: 4,
    });
    
    _entries = result;
    _lastLoadTime = Date.now();
  } catch (e) {
    console.error('Failed to load project files:', e);
    _error = e instanceof Error ? e.message : String(e);
    _entries = [];
  } finally {
    _isLoading = false;
  }
}

/**
 * Debounced file reload (300ms) to handle rapid events.
 * Called by agent event handlers when tasks complete.
 */
export const reloadFiles = debounce(reloadFilesInternal, 300);

/**
 * Immediate file reload for manual refresh.
 */
export const reloadFilesImmediate = reloadFilesInternal;

/**
 * Force reload even if already loading (cancels debounce, waits, reloads).
 * Useful for user-initiated refresh.
 */
export async function forceReloadFiles(): Promise<void> {
  // Cancel any pending debounced calls
  reloadFiles.cancel?.();
  
  // Wait briefly for any in-flight request
  if (_isLoading) {
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  
  // Force reload
  await reloadFilesInternal();
}

/**
 * Clear files state (used when switching projects).
 */
export function clearFiles(): void {
  _entries = [];
  _error = null;
  _projectPath = null;
  _lastLoadTime = null;
}

// ═══════════════════════════════════════════════════════════════
// FILE UTILITIES
// ═══════════════════════════════════════════════════════════════

/** File categorization types */
export type FileCategory = 'source' | 'tests' | 'config' | 'docs' | 'assets' | 'other';

export interface CategorizedFile {
  entry: FileEntry;
  category: FileCategory;
  icon: string;
}

/**
 * Categorize a file by its name/path.
 */
export function categorizeFile(entry: FileEntry): CategorizedFile {
  const name = entry.name.toLowerCase();
  const path = entry.path.toLowerCase();
  
  // Tests
  if (name.startsWith('test_') || name.endsWith('_test.py') || 
      name.endsWith('.test.ts') || name.endsWith('.test.js') ||
      name.endsWith('.spec.ts') || name.endsWith('.spec.js') ||
      path.includes('/tests/') || path.includes('/test/')) {
    return { entry, category: 'tests', icon: '🧪' };
  }
  
  // Config files
  if (['pyproject.toml', 'package.json', 'cargo.toml', 'requirements.txt', 
       'setup.py', 'setup.cfg', '.env', '.gitignore', 'tsconfig.json',
       'vite.config.ts', 'tailwind.config.js', 'docker-compose.yml', 'dockerfile'].includes(name) ||
      name.endsWith('.yaml') || name.endsWith('.yml') || name.endsWith('.toml')) {
    return { entry, category: 'config', icon: '⚙️' };
  }
  
  // Documentation
  if (name.endsWith('.md') || name.endsWith('.rst') || name.endsWith('.txt') ||
      path.includes('/docs/')) {
    return { entry, category: 'docs', icon: '📄' };
  }
  
  // Assets
  if (name.endsWith('.css') || name.endsWith('.scss') || name.endsWith('.svg') ||
      name.endsWith('.png') || name.endsWith('.jpg') || name.endsWith('.ico')) {
    return { entry, category: 'assets', icon: '🎨' };
  }
  
  // Source code
  if (name.endsWith('.py') || name.endsWith('.ts') || name.endsWith('.js') ||
      name.endsWith('.tsx') || name.endsWith('.jsx') || name.endsWith('.rs') ||
      name.endsWith('.go') || name.endsWith('.svelte') || name.endsWith('.vue') ||
      name.endsWith('.html')) {
    return { entry, category: 'source', icon: '📝' };
  }
  
  return { entry, category: 'other', icon: '📁' };
}

/**
 * Get files grouped by category.
 */
export function getCategorizedFiles(): Record<FileCategory, CategorizedFile[]> {
  const groups: Record<FileCategory, CategorizedFile[]> = {
    source: [], tests: [], config: [], docs: [], assets: [], other: []
  };
  
  for (const entry of flattenFiles(_entries)) {
    const categorized = categorizeFile(entry);
    groups[categorized.category].push(categorized);
  }
  
  return groups;
}

/**
 * Find a "hero" file (main source file) for preview.
 * Priority: main.py, app.py, index.ts, etc.
 */
export function findHeroFile(): FileEntry | null {
  const flat = flattenFiles(_entries);
  const sourceFiles = flat.filter(f => {
    const ext = f.name.split('.').pop()?.toLowerCase();
    return ['py', 'ts', 'tsx', 'js', 'jsx', 'rs', 'go', 'svelte'].includes(ext ?? '');
  });
  
  if (sourceFiles.length === 0) return null;
  
  // Priority order
  const priorities = ['main.py', 'app.py', 'index.ts', 'index.tsx', 'main.ts', 'main.tsx', 'mod.rs', 'lib.rs', 'main.go'];
  for (const name of priorities) {
    const found = sourceFiles.find(f => f.name === name);
    if (found) return found;
  }
  
  return sourceFiles[0] ?? null;
}

/**
 * Detect project type based on files.
 */
export function detectProjectType(): 'webapp' | 'python-app' | 'rust' | 'go' | 'generic' {
  const flat = flattenFiles(_entries);
  const names = new Set(flat.map(f => f.name.toLowerCase()));
  
  // Web app indicators
  if (names.has('index.html') || names.has('app.tsx') || names.has('app.vue') || 
      [...names].some(n => n.endsWith('.svelte'))) {
    return 'webapp';
  }
  
  // Python app
  if (names.has('main.py') || names.has('app.py') || names.has('__main__.py')) {
    return 'python-app';
  }
  
  // Rust
  if (names.has('cargo.toml')) {
    return 'rust';
  }
  
  // Go
  if (names.has('go.mod') || names.has('main.go')) {
    return 'go';
  }
  
  return 'generic';
}
