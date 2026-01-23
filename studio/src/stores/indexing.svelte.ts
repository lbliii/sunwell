/**
 * Indexing Store — Reactive state for codebase indexing (RFC-108)
 */

import { invoke } from '@tauri-apps/api/core';
import { listen, type UnlistenFn } from '@tauri-apps/api/event';
import type {
  IndexChunk,
  IndexQuery,
  IndexResult,
  IndexSettings,
  IndexStatus,
  IndexState,
} from '$lib/indexing-contract';
import {
  DEFAULT_INDEX_SETTINGS,
  getStatusIcon,
  getStatusLabel,
  isIndexBuilding,
  isIndexUsable,
} from '$lib/indexing-contract';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _status = $state<IndexStatus>({ state: 'no_index' });
let _settings = $state<IndexSettings>(DEFAULT_INDEX_SETTINGS);
let _lastResult = $state<IndexResult | null>(null);
let _unsubscribe: UnlistenFn | null = null;

// ═══════════════════════════════════════════════════════════════
// COMPUTED
// ═══════════════════════════════════════════════════════════════

function computedIsReady(): boolean {
  return isIndexUsable(_status);
}

function computedIsBuilding(): boolean {
  return isIndexBuilding(_status);
}

function computedIsDegraded(): boolean {
  return _status.state === 'degraded';
}

function computedStatusLabel(): string {
  return getStatusLabel(_status);
}

function computedStatusIcon(): string {
  return getStatusIcon(_status);
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const indexingStore = {
  get status() { return _status; },
  get settings() { return _settings; },
  get lastResult() { return _lastResult; },
  get isReady() { return computedIsReady(); },
  get isBuilding() { return computedIsBuilding(); },
  get isDegraded() { return computedIsDegraded(); },
  get statusLabel() { return computedStatusLabel(); },
  get statusIcon() { return computedStatusIcon(); },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Initialize indexing for a workspace.
 * Call this when a project is opened.
 */
export async function initIndexing(workspacePath: string): Promise<void> {
  // Subscribe to status events
  if (_unsubscribe) {
    _unsubscribe();
  }
  
  _unsubscribe = await listen<IndexStatus>('index-status', (event) => {
    _status = event.payload;
  });
  
  // Start the service
  if (_settings.autoIndex) {
    await invoke('start_indexing_service', { workspacePath });
  }
}

/**
 * Query the index.
 */
export async function queryIndex(
  text: string, 
  topK: number = 10
): Promise<IndexResult> {
  const result = await invoke<IndexResult>('query_index', { 
    query: { text, topK } 
  });
  _lastResult = result;
  return result;
}

/**
 * Force rebuild the index.
 */
export async function rebuildIndex(): Promise<void> {
  await invoke('rebuild_index');
}

/**
 * Update settings.
 */
export async function updateSettings(settings: Partial<IndexSettings>): Promise<void> {
  _settings = { ..._settings, ...settings };
  await invoke('set_index_settings', { settings: _settings });
}

/**
 * Stop indexing service.
 */
export async function stopIndexing(): Promise<void> {
  if (_unsubscribe) {
    _unsubscribe();
    _unsubscribe = null;
  }
  await invoke('stop_indexing_service');
  _status = { state: 'no_index' };
}

/**
 * Get current status (for initial load).
 */
export async function refreshStatus(): Promise<void> {
  _status = await invoke<IndexStatus>('get_index_status');
}
