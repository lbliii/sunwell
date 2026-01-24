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
  path: string;
  status: ArtifactStatus;
  content?: string;
  errors?: string[];
  original_error?: string;
}

/** Summary of a pending recovery (for list view) */
export interface RecoverySummary {
  goalHash: string;
  goalPreview: string;
  passed: number;
  failed: number;
  waiting: number;
  ageStr: string;
  timestamp: string;
}

/** Full recovery state */
export interface RecoveryState {
  goalHash: string;
  goal: string;
  runId: string;
  artifacts: RecoveryArtifact[];
  passedCount: number;
  failedCount: number;
  waitingCount: number;
  failureReason: string;
  errorDetails: string[];
  createdAt: string;
  iterations?: RecoveryIteration[];
}

/** Single iteration in recovery history */
export interface RecoveryIteration {
  iteration: number;
  action: 'auto_fix' | 'manual_edit' | 'skip' | 'retry';
  result: 'improved' | 'fixed' | 'failed' | 'aborted';
  artifactsFixed: number;
  timestamp: string;
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

// ═══════════════════════════════════════════════════════════════
// INTERNAL HELPERS
// ═══════════════════════════════════════════════════════════════

function transformApiResponse(data: unknown): RecoveryState {
  const d = data as Record<string, unknown>;
  const artifacts = (d.artifacts as Array<Record<string, unknown>>) ?? [];
  
  return {
    goalHash: d.goal_hash as string,
    goal: d.goal as string,
    runId: d.run_id as string,
    artifacts: artifacts.map(a => ({
      path: a.path as string,
      status: a.status as ArtifactStatus,
      content: a.content as string | undefined,
      errors: a.errors as string[] | undefined,
      original_error: a.original_error as string | undefined,
    })),
    passedCount: d.passed_count as number,
    failedCount: d.failed_count as number,
    waitingCount: d.waiting_count as number,
    failureReason: d.failure_reason as string,
    errorDetails: d.error_details as string[],
    createdAt: d.created_at as string,
    iterations: d.iterations as RecoveryIteration[] | undefined,
  };
}

function transformSummary(data: unknown): RecoverySummary {
  const d = data as Record<string, unknown>;
  return {
    goalHash: d.goal_hash as string,
    goalPreview: d.goal_preview as string,
    passed: d.passed as number,
    failed: d.failed as number,
    waiting: d.waiting as number,
    ageStr: d.age_str as string,
    timestamp: d.timestamp as string,
  };
}

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const recovery = {
  // State getters
  get pendingRecoveries() { return _pendingRecoveries; },
  get activeRecovery() { return _activeRecovery; },
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
  
  get passedArtifacts() {
    return _activeRecovery?.artifacts.filter(a => a.status === 'passed') ?? [];
  },
  
  get failedArtifacts() {
    return _activeRecovery?.artifacts.filter(a => a.status === 'failed') ?? [];
  },
  
  get waitingArtifacts() {
    return _activeRecovery?.artifacts.filter(a => a.status === 'waiting') ?? [];
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
      const data = response as { recoveries: unknown[] };
      _pendingRecoveries = data.recoveries.map(transformSummary);
      
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
    const d = data as Record<string, unknown>;
    
    // Add to pending list
    _pendingRecoveries = [
      {
        goalHash: d.goal_hash as string,
        goalPreview: d.goal_preview as string,
        passed: d.passed as number,
        failed: d.failed as number,
        waiting: d.waiting as number,
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
    const d = data as Record<string, unknown>;
    const goalHash = d.goal_hash as string;
    
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
