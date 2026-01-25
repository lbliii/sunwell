/**
 * Recovery Store — manages recovery state and events (RFC-125)
 *
 * Tracks failed execution recoveries and provides UI state for the
 * Recovery Panel component.
 */

import { agent } from './agent.svelte';
import { api } from '$lib/api';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

/** Status of an artifact in recovery */
export type ArtifactStatus = 'passed' | 'failed' | 'fixed' | 'skipped' | 'waiting';

/** An artifact being tracked for recovery */
export interface RecoveryArtifact {
  readonly path: string;
  readonly status: ArtifactStatus;
  readonly content?: string;
  readonly errors?: readonly string[];
  readonly original_error?: string;
}

/** Summary of a pending recovery (for list view) */
export interface RecoverySummary {
  readonly goalHash: string;
  readonly goalPreview: string;
  readonly passed: number;
  readonly failed: number;
  readonly waiting: number;
  readonly ageStr: string;
  readonly timestamp: string;
}

/** Full recovery state */
export interface RecoveryState {
  readonly goalHash: string;
  readonly goal: string;
  readonly runId: string;
  readonly artifacts: readonly RecoveryArtifact[];
  readonly passedCount: number;
  readonly failedCount: number;
  readonly waitingCount: number;
  readonly failureReason: string;
  readonly errorDetails: readonly string[];
  readonly createdAt: string;
  readonly iterations?: readonly RecoveryIteration[];
}

/** Single iteration in recovery history */
export interface RecoveryIteration {
  readonly iteration: number;
  readonly action: 'auto_fix' | 'manual_edit' | 'skip' | 'retry';
  readonly result: 'improved' | 'fixed' | 'failed' | 'aborted';
  readonly artifactsFixed: number;
  readonly timestamp: string;
}

/** Recovery panel display state */
export type RecoveryPanelState = 'hidden' | 'minimized' | 'expanded';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _pendingRecoveries = $state<RecoverySummary[]>([]);
let _activeRecovery = $state<RecoveryState | null>(null);
let _panelState = $state<RecoveryPanelState>('hidden');
let _isLoading = $state<boolean>(false);
let _autoFixInProgress = $state<boolean>(false);
let _lastError = $state<string | null>(null);

// Cached derived values for O(1) getter access (computed once per state change)
const _passedArtifacts = $derived(
  Object.freeze(_activeRecovery?.artifacts.filter(a => a.status === 'passed') ?? [])
);
const _failedArtifacts = $derived(
  Object.freeze(_activeRecovery?.artifacts.filter(a => a.status === 'failed') ?? [])
);
const _waitingArtifacts = $derived(
  Object.freeze(_activeRecovery?.artifacts.filter(a => a.status === 'waiting') ?? [])
);

// ═══════════════════════════════════════════════════════════════
// TYPE GUARDS
// ═══════════════════════════════════════════════════════════════

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isString(value: unknown): value is string {
  return typeof value === 'string';
}

function isNumber(value: unknown): value is number {
  return typeof value === 'number';
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(isString);
}

function isArtifactStatus(value: unknown): value is ArtifactStatus {
  return isString(value) && ['passed', 'failed', 'fixed', 'skipped', 'waiting'].includes(value);
}

// ═══════════════════════════════════════════════════════════════
// INTERNAL HELPERS
// ═══════════════════════════════════════════════════════════════

function transformApiResponse(data: unknown): RecoveryState {
  if (!isRecord(data)) {
    throw new Error('Invalid recovery response: expected object');
  }

  const artifacts = Array.isArray(data.artifacts) ? data.artifacts : [];

  return {
    goalHash: isString(data.goal_hash) ? data.goal_hash : '',
    goal: isString(data.goal) ? data.goal : '',
    runId: isString(data.run_id) ? data.run_id : '',
    artifacts: artifacts.filter(isRecord).map(a => ({
      path: isString(a.path) ? a.path : '',
      status: isArtifactStatus(a.status) ? a.status : 'waiting',
      content: isString(a.content) ? a.content : undefined,
      errors: isStringArray(a.errors) ? a.errors : undefined,
      original_error: isString(a.original_error) ? a.original_error : undefined,
    })),
    passedCount: isNumber(data.passed_count) ? data.passed_count : 0,
    failedCount: isNumber(data.failed_count) ? data.failed_count : 0,
    waitingCount: isNumber(data.waiting_count) ? data.waiting_count : 0,
    failureReason: isString(data.failure_reason) ? data.failure_reason : '',
    errorDetails: isStringArray(data.error_details) ? data.error_details : [],
    createdAt: isString(data.created_at) ? data.created_at : '',
    iterations: Array.isArray(data.iterations) ? data.iterations as RecoveryIteration[] : undefined,
  };
}

function transformSummary(data: unknown): RecoverySummary {
  if (!isRecord(data)) {
    throw new Error('Invalid recovery summary: expected object');
  }

  return {
    goalHash: isString(data.goal_hash) ? data.goal_hash : '',
    goalPreview: isString(data.goal_preview) ? data.goal_preview : '',
    passed: isNumber(data.passed) ? data.passed : 0,
    failed: isNumber(data.failed) ? data.failed : 0,
    waiting: isNumber(data.waiting) ? data.waiting : 0,
    ageStr: isString(data.age_str) ? data.age_str : '',
    timestamp: isString(data.timestamp) ? data.timestamp : '',
  };
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const recovery = {
  // State getters (return frozen copies to prevent external mutation)
  get pendingRecoveries(): readonly RecoverySummary[] { return Object.freeze([..._pendingRecoveries]); },
  get activeRecovery(): Readonly<RecoveryState> | null { return _activeRecovery ? Object.freeze({ ..._activeRecovery }) : null; },
  get panelState() { return _panelState; },
  get isLoading() { return _isLoading; },
  get autoFixInProgress() { return _autoFixInProgress; },
  get lastError() { return _lastError; },

  // Derived state
  get hasPendingRecoveries() {
    return _pendingRecoveries.length > 0;
  },

  get totalPending() {
    return _pendingRecoveries.length;
  },

  /** Returns cached frozen array (computed once per state change) */
  get passedArtifacts(): readonly RecoveryArtifact[] {
    return _passedArtifacts;
  },

  /** Returns cached frozen array (computed once per state change) */
  get failedArtifacts(): readonly RecoveryArtifact[] {
    return _failedArtifacts;
  },

  /** Returns cached frozen array (computed once per state change) */
  get waitingArtifacts(): readonly RecoveryArtifact[] {
    return _waitingArtifacts;
  },

  // ═══════════════════════════════════════════════════════════════
  // PANEL CONTROLS
  // ═══════════════════════════════════════════════════════════════

  showPanel() {
    _panelState = 'expanded';
  },

  hidePanel() {
    _panelState = 'hidden';
  },

  minimizePanel() {
    _panelState = 'minimized';
  },

  togglePanel() {
    if (_panelState === 'expanded') {
      _panelState = 'minimized';
    } else {
      _panelState = 'expanded';
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // DATA OPERATIONS
  // ═══════════════════════════════════════════════════════════════

  /**
   * Fetch list of pending recoveries from server
   */
  async fetchPendingRecoveries() {
    _isLoading = true;
    _lastError = null;

    try {
      const response = await api.get('/api/recovery/pending');
      if (!isRecord(response) || !Array.isArray(response.recoveries)) {
        throw new Error('Invalid response format');
      }
      _pendingRecoveries = response.recoveries.map(transformSummary);

      // Auto-show panel if there are pending recoveries
      if (_pendingRecoveries.length > 0 && _panelState === 'hidden') {
        _panelState = 'minimized';
      }
    } catch (error) {
      _lastError = error instanceof Error ? error.message : 'Failed to fetch recoveries';
      console.error('Failed to fetch pending recoveries:', error);
    } finally {
      _isLoading = false;
    }
  },

  /**
   * Load a specific recovery for review
   */
  async loadRecovery(goalHash: string) {
    _isLoading = true;
    _lastError = null;

    try {
      const response = await api.get(`/api/recovery/${goalHash}`);
      _activeRecovery = transformApiResponse(response);
      _panelState = 'expanded';
    } catch (error) {
      _lastError = error instanceof Error ? error.message : 'Failed to load recovery';
      console.error('Failed to load recovery:', error);
    } finally {
      _isLoading = false;
    }
  },

  /**
   * Clear the active recovery (go back to list view)
   */
  clearActiveRecovery() {
    _activeRecovery = null;
  },

  // ═══════════════════════════════════════════════════════════════
  // RECOVERY ACTIONS
  // ═══════════════════════════════════════════════════════════════

  /**
   * Trigger auto-fix for a recovery
   */
  async autoFix(goalHash: string, hint?: string) {
    if (_autoFixInProgress) return;

    _autoFixInProgress = true;
    _lastError = null;

    try {
      await api.post(`/api/recovery/${goalHash}/auto-fix`, { hint });
      // Agent will emit events — we'll track progress via agent store
    } catch (error) {
      _lastError = error instanceof Error ? error.message : 'Auto-fix failed';
      console.error('Auto-fix failed:', error);
    } finally {
      _autoFixInProgress = false;
    }
  },

  /**
   * Skip failed artifacts and write only passed ones
   */
  async skipFailed(goalHash: string) {
    _isLoading = true;
    _lastError = null;

    try {
      await api.post(`/api/recovery/${goalHash}/skip`);
      // Refresh pending list
      await this.fetchPendingRecoveries();
      _activeRecovery = null;
    } catch (error) {
      _lastError = error instanceof Error ? error.message : 'Skip operation failed';
      console.error('Skip failed:', error);
    } finally {
      _isLoading = false;
    }
  },

  /**
   * Abort a recovery entirely
   */
  async abortRecovery(goalHash: string) {
    _isLoading = true;
    _lastError = null;

    try {
      await api.delete(`/api/recovery/${goalHash}`);
      await this.fetchPendingRecoveries();
      _activeRecovery = null;
    } catch (error) {
      _lastError = error instanceof Error ? error.message : 'Abort failed';
      console.error('Abort failed:', error);
    } finally {
      _isLoading = false;
    }
  },

  // ═══════════════════════════════════════════════════════════════
  // EVENT HANDLERS (called by agent store on event)
  // ═══════════════════════════════════════════════════════════════

  /**
   * Handle recovery_saved event from agent
   */
  handleRecoverySaved(data: unknown) {
    if (!isRecord(data)) return;

    // Add to pending list
    _pendingRecoveries = [
      {
        goalHash: isString(data.goal_hash) ? data.goal_hash : '',
        goalPreview: isString(data.goal_preview) ? data.goal_preview : '',
        passed: isNumber(data.passed) ? data.passed : 0,
        failed: isNumber(data.failed) ? data.failed : 0,
        waiting: isNumber(data.waiting) ? data.waiting : 0,
        ageStr: 'just now',
        timestamp: new Date().toISOString(),
      },
      ..._pendingRecoveries,
    ];

    // Show panel
    _panelState = 'minimized';
  },

  /**
   * Handle recovery_resolved event from agent
   */
  handleRecoveryResolved(data: unknown) {
    if (!isRecord(data)) return;
    const goalHash = isString(data.goal_hash) ? data.goal_hash : '';

    // Remove from pending list
    _pendingRecoveries = _pendingRecoveries.filter(r => r.goalHash !== goalHash);

    // Clear active if it matches
    if (_activeRecovery?.goalHash === goalHash) {
      _activeRecovery = null;
    }

    // Hide panel if no more pending
    if (_pendingRecoveries.length === 0) {
      _panelState = 'hidden';
    }
  },

  /**
   * Reset all state
   */
  reset() {
    _pendingRecoveries = [];
    _activeRecovery = null;
    _panelState = 'hidden';
    _isLoading = false;
    _autoFixInProgress = false;
    _lastError = null;
  },
};
