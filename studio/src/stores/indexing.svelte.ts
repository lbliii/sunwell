/**
 * Indexing Store — Reactive state for codebase indexing (RFC-108)
 *
 * Uses HTTP REST API to communicate with Python backend.
 */

import type {
  IndexResult,
  IndexSettings,
  IndexStatus,
} from '$lib/indexing-contract';
import {
  DEFAULT_INDEX_SETTINGS,
  getStatusIcon,
  getStatusLabel,
  isIndexBuilding,
  isIndexUsable,
} from '$lib/indexing-contract';
import { apiGet, apiPost, onEvent } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _status = $state<IndexStatus>({ state: 'no_index' });
let _settings = $state<IndexSettings>(DEFAULT_INDEX_SETTINGS);
let _lastResult = $state<IndexResult | null>(null);
let _unsubscribe: (() => void) | null = null;

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
  get status() {
    return _status;
  },
  get settings() {
    return _settings;
  },
  get lastResult() {
    return _lastResult;
  },
  get isReady() {
    return computedIsReady();
  },
  get isBuilding() {
    return computedIsBuilding();
  },
  get isDegraded() {
    return computedIsDegraded();
  },
  get statusLabel() {
    return computedStatusLabel();
  },
  get statusIcon() {
    return computedStatusIcon();
  },
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

  // Subscribe to indexing status events via WebSocket
  _unsubscribe = onEvent((event) => {
    if (event.type === 'index_status') {
      _status = event.data as unknown as IndexStatus;
    }
  });

  // Start the indexing service if auto-index enabled
  if (_settings.autoIndex) {
    try {
      await apiPost('/api/indexing/start', { workspace_path: workspacePath });
    } catch (e) {
      console.warn('[indexing] Failed to start indexing service:', e);
    }
  }
}

/**
 * Query the index.
 */
export async function queryIndex(text: string, topK: number = 10): Promise<IndexResult> {
  try {
    const result = await apiPost<IndexResult>('/api/indexing/query', {
      text,
      top_k: topK,
    });
    _lastResult = result;
    return result;
  } catch (e) {
    console.error('[indexing] Query failed:', e);
    return { chunks: [], totalChunksSearched: 0, fallbackUsed: true, queryTimeMs: 0 };
  }
}

/**
 * Force rebuild the index.
 */
export async function rebuildIndex(): Promise<void> {
  try {
    await apiPost('/api/indexing/rebuild');
  } catch (e) {
    console.error('[indexing] Rebuild failed:', e);
  }
}

/**
 * Update settings.
 */
export async function updateSettings(settings: Partial<IndexSettings>): Promise<void> {
  _settings = { ..._settings, ...settings };

  try {
    await apiPost('/api/indexing/settings', _settings);
  } catch (e) {
    console.error('[indexing] Failed to update settings:', e);
  }
}

/**
 * Stop indexing service.
 */
export async function stopIndexing(): Promise<void> {
  if (_unsubscribe) {
    _unsubscribe();
    _unsubscribe = null;
  }

  try {
    await apiPost('/api/indexing/stop');
  } catch (e) {
    console.warn('[indexing] Failed to stop service:', e);
  }

  _status = { state: 'no_index' };
}

/**
 * Get current status (for initial load).
 */
export async function refreshStatus(): Promise<void> {
  try {
    _status = await apiGet<IndexStatus>('/api/indexing/status');
  } catch (e) {
    console.warn('[indexing] Failed to get status:', e);
  }
}
