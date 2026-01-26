/**
 * Session Store — Autonomous session management (Mental Models Integration)
 *
 * Manages autonomous sessions stored globally at ~/.sunwell/sessions/.
 * Provides listing, viewing, resuming, and deleting sessions.
 */

import { apiGet, apiPost, apiPatch, apiDelete } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface SessionSummary {
	sessionId: string;
	status: 'running' | 'paused' | 'completed' | 'failed';
	goals: string[];
	startedAt: string;
	stoppedAt: string | null;
	stopReason: string | null;
	opportunitiesTotal: number;
	opportunitiesCompleted: number;
	projectId: string | null;
	workspaceId: string | null;
}

export interface SessionDetail extends SessionSummary {
	checkpointAt: string | null;
	opportunitiesRemaining: number;
	proposalsCreated: number;
	proposalsAutoApplied: number;
	proposalsQueued: number;
	proposalsRejected: number;
	totalRuntimeSeconds: number;
}

interface SessionListResponse {
	sessions: SessionSummary[];
	resumableCount: number;
}

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let _sessions = $state<SessionSummary[]>([]);
let _currentSession = $state<SessionDetail | null>(null);
let _isLoading = $state(false);
let _error = $state<string | null>(null);
let _resumableCount = $state(0);

// ═══════════════════════════════════════════════════════════════════════════
// EXPORTS (read-only reactive state)
// ═══════════════════════════════════════════════════════════════════════════

export const sessionStore = {
	get sessions() {
		return _sessions;
	},
	get currentSession() {
		return _currentSession;
	},
	get isLoading() {
		return _isLoading;
	},
	get error() {
		return _error;
	},
	get resumableCount() {
		return _resumableCount;
	},
	get hasResumable() {
		return _resumableCount > 0;
	},
};

// ═══════════════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Load all sessions.
 */
export async function loadSessions(status?: string): Promise<SessionSummary[]> {
	try {
		_isLoading = true;
		_error = null;

		const params = status ? `?status=${encodeURIComponent(status)}` : '';
		const response = await apiGet<SessionListResponse>(`/api/sessions${params}`);

		_sessions = response.sessions || [];
		_resumableCount = response.resumableCount || 0;

		return _sessions;
	} catch (e) {
		_error = e instanceof Error ? e.message : String(e);
		console.error('Failed to load sessions:', e);
		return [];
	} finally {
		_isLoading = false;
	}
}

/**
 * Get session details.
 */
export async function getSession(sessionId: string): Promise<SessionDetail | null> {
	try {
		_isLoading = true;
		_error = null;

		const session = await apiGet<SessionDetail>(`/api/sessions/${encodeURIComponent(sessionId)}`);
		_currentSession = session;

		return session;
	} catch (e) {
		_error = e instanceof Error ? e.message : String(e);
		console.error('Failed to get session:', e);
		return null;
	} finally {
		_isLoading = false;
	}
}

/**
 * Resume a paused or interrupted session.
 */
export async function resumeSession(sessionId: string): Promise<SessionDetail | null> {
	try {
		_isLoading = true;
		_error = null;

		const session = await apiPost<SessionDetail>(
			`/api/sessions/${encodeURIComponent(sessionId)}/resume`,
			{}
		);

		_currentSession = session;

		// Update list
		_sessions = _sessions.map((s) =>
			s.sessionId === sessionId ? { ...s, status: session.status } : s
		);

		return session;
	} catch (e) {
		_error = e instanceof Error ? e.message : String(e);
		console.error('Failed to resume session:', e);
		return null;
	} finally {
		_isLoading = false;
	}
}

/**
 * Pause a running session.
 */
export async function pauseSession(sessionId: string): Promise<SessionDetail | null> {
	try {
		_isLoading = true;
		_error = null;

		const session = await apiPost<SessionDetail>(
			`/api/sessions/${encodeURIComponent(sessionId)}/pause`,
			{}
		);

		_currentSession = session;

		// Update list
		_sessions = _sessions.map((s) =>
			s.sessionId === sessionId ? { ...s, status: session.status } : s
		);

		return session;
	} catch (e) {
		_error = e instanceof Error ? e.message : String(e);
		console.error('Failed to pause session:', e);
		return null;
	} finally {
		_isLoading = false;
	}
}

/**
 * Delete a session.
 */
export async function deleteSession(sessionId: string): Promise<boolean> {
	try {
		_isLoading = true;
		_error = null;

		await apiDelete<void>(`/api/sessions/${encodeURIComponent(sessionId)}`);

		// Remove from list
		_sessions = _sessions.filter((s) => s.sessionId !== sessionId);

		// Clear current if it was deleted
		if (_currentSession?.sessionId === sessionId) {
			_currentSession = null;
		}

		return true;
	} catch (e) {
		_error = e instanceof Error ? e.message : String(e);
		console.error('Failed to delete session:', e);
		return false;
	} finally {
		_isLoading = false;
	}
}

/**
 * Clear current session selection.
 */
export function clearCurrentSession(): void {
	_currentSession = null;
}

/**
 * Get sessions filtered by status.
 */
export function getSessionsByStatus(
	status: 'running' | 'paused' | 'completed' | 'failed'
): SessionSummary[] {
	return _sessions.filter((s) => s.status === status);
}

/**
 * Get resumable sessions (paused or running/interrupted).
 */
export function getResumableSessions(): SessionSummary[] {
	return _sessions.filter((s) => s.status === 'paused' || s.status === 'running');
}
