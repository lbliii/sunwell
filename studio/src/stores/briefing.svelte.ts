/**
 * Briefing Store — manages rolling handoff notes state (RFC-071)
 *
 * RFC-113: Migrated from Tauri invoke to HTTP API.
 *
 * The briefing provides instant orientation at session start:
 * - What we're trying to accomplish (mission)
 * - Where we are (status, progress)
 * - What to do next (next_action)
 * - What to avoid (hazards)
 * - Where to look (hot_files)
 */

import type { Briefing, BriefingStatus } from '$lib/types';
import { apiGet, apiPost } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

let _briefing = $state<Briefing | null>(null);
let _isLoading = $state(false);
let _error = $state<string | null>(null);

// ═══════════════════════════════════════════════════════════════
// EXPORTS
// ═══════════════════════════════════════════════════════════════

export const briefing = {
  get current() { return _briefing; },
  get isLoading() { return _isLoading; },
  get error() { return _error; },
  // Computed
  get hasBriefing() { return _briefing !== null; },
  get status(): BriefingStatus | null { return _briefing?.status ?? null; },
  get isBlocked() { return _briefing?.status === 'blocked'; },
  get isComplete() { return _briefing?.status === 'complete'; },
  get isInProgress() { return _briefing?.status === 'in_progress'; },
  get hasHazards() { return (_briefing?.hazards.length ?? 0) > 0; },
  get hasBlockers() { return (_briefing?.blockers.length ?? 0) > 0; },
  get hasDispatchHints() {
    return (_briefing?.predictedSkills?.length ?? 0) > 0 ||
           _briefing?.suggestedLens != null;
  },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

export async function loadBriefing(projectPath: string): Promise<Briefing | null> {
  if (_isLoading) return _briefing;

  try {
    _isLoading = true;
    _error = null;
    const result = await apiGet<{ briefing: Briefing | null }>(`/api/briefing?path=${encodeURIComponent(projectPath)}`);
    _briefing = result.briefing;
    return _briefing;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    _briefing = null;
    return null;
  } finally {
    _isLoading = false;
  }
}

export async function hasBriefing(projectPath: string): Promise<boolean> {
  try {
    const result = await apiGet<{ exists: boolean }>(`/api/briefing/exists?path=${encodeURIComponent(projectPath)}`);
    return result.exists;
  } catch {
    return false;
  }
}

export async function clearBriefing(projectPath: string): Promise<boolean> {
  try {
    const result = await apiPost<{ success: boolean }>('/api/briefing/clear', { path: projectPath });
    if (result.success) {
      _briefing = null;
    }
    return result.success;
  } catch (e) {
    _error = e instanceof Error ? e.message : String(e);
    return false;
  }
}

export function resetBriefing(): void {
  _briefing = null;
  _error = null;
}

// ═══════════════════════════════════════════════════════════════
// HELPERS
// ═══════════════════════════════════════════════════════════════

export function getStatusColor(status: BriefingStatus): string {
  const colors: Record<BriefingStatus, string> = {
    not_started: 'var(--color-text-muted)',
    in_progress: 'var(--color-accent)',
    blocked: 'var(--color-error)',
    complete: 'var(--color-success)',
  };
  return colors[status];
}

export function getStatusEmoji(status: BriefingStatus): string {
  const emojis: Record<BriefingStatus, string> = {
    not_started: '○',
    in_progress: '◐',
    blocked: '⊘',
    complete: '●',
  };
  return emojis[status];
}

export function getStatusLabel(status: BriefingStatus): string {
  const labels: Record<BriefingStatus, string> = {
    not_started: 'Not Started',
    in_progress: 'In Progress',
    blocked: 'Blocked',
    complete: 'Complete',
  };
  return labels[status];
}

export function formatRelativeTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
