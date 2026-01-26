/**
 * Session store tests — verify lifecycle management and API interactions
 *
 * Tests that the session store properly handles loading, resuming,
 * pausing, and deleting sessions with proper error handling.
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import {
	sessionStore,
	loadSessions,
	getSession,
	resumeSession,
	pauseSession,
	deleteSession,
	clearCurrentSession,
	getSessionsByStatus,
	getResumableSessions,
} from './session.svelte';

// Mock the socket module
vi.mock('$lib/socket', () => ({
	apiGet: vi.fn(),
	apiPost: vi.fn(),
	apiPatch: vi.fn(),
	apiDelete: vi.fn(),
}));

// Import mocked functions for configuration
import { apiGet, apiPost, apiDelete } from '$lib/socket';
const mockApiGet = apiGet as ReturnType<typeof vi.fn>;
const mockApiPost = apiPost as ReturnType<typeof vi.fn>;
const mockApiDelete = apiDelete as ReturnType<typeof vi.fn>;

// Helper to create mock session summaries
function createMockSession(overrides: Partial<{
	sessionId: string;
	status: 'running' | 'paused' | 'completed' | 'failed';
	goals: string[];
}> = {}) {
	return {
		sessionId: overrides.sessionId ?? `session-${Math.random().toString(36).slice(2)}`,
		status: overrides.status ?? 'completed',
		goals: overrides.goals ?? ['Build a REST API'],
		startedAt: new Date().toISOString(),
		stoppedAt: null,
		stopReason: null,
		opportunitiesTotal: 10,
		opportunitiesCompleted: 5,
		projectId: 'proj-123',
		workspaceId: null,
	};
}

// Helper to create mock session detail
function createMockDetail(overrides: Partial<{
	sessionId: string;
	status: 'running' | 'paused' | 'completed' | 'failed';
}> = {}) {
	return {
		...createMockSession(overrides),
		checkpointAt: null,
		opportunitiesRemaining: 5,
		proposalsCreated: 3,
		proposalsAutoApplied: 2,
		proposalsQueued: 1,
		proposalsRejected: 0,
		totalRuntimeSeconds: 3600,
	};
}

describe('session store', () => {
	beforeEach(() => {
		vi.clearAllMocks();
		clearCurrentSession();
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// LOAD SESSIONS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('loadSessions', () => {
		it('loads all sessions from API', async () => {
			const mockSessions = [
				createMockSession({ sessionId: 'session-1', status: 'completed' }),
				createMockSession({ sessionId: 'session-2', status: 'paused' }),
				createMockSession({ sessionId: 'session-3', status: 'running' }),
			];
			mockApiGet.mockResolvedValueOnce({
				sessions: mockSessions,
				resumableCount: 2,
			});

			const result = await loadSessions();

			expect(mockApiGet).toHaveBeenCalledWith('/api/sessions');
			expect(result).toHaveLength(3);
			expect(sessionStore.sessions).toHaveLength(3);
			expect(sessionStore.resumableCount).toBe(2);
			expect(sessionStore.hasResumable).toBe(true);
		});

		it('filters by status when provided', async () => {
			mockApiGet.mockResolvedValueOnce({
				sessions: [createMockSession({ status: 'paused' })],
				resumableCount: 1,
			});

			await loadSessions('paused');

			expect(mockApiGet).toHaveBeenCalledWith('/api/sessions?status=paused');
		});

		it('handles empty sessions list', async () => {
			mockApiGet.mockResolvedValueOnce({
				sessions: [],
				resumableCount: 0,
			});

			const result = await loadSessions();

			expect(result).toHaveLength(0);
			expect(sessionStore.sessions).toHaveLength(0);
			expect(sessionStore.hasResumable).toBe(false);
		});

		it('handles API error gracefully', async () => {
			mockApiGet.mockRejectedValueOnce(new Error('Network error'));

			const result = await loadSessions();

			expect(result).toHaveLength(0);
			expect(sessionStore.error).toBe('Network error');
		});

		it('clears error on successful load', async () => {
			// First load fails
			mockApiGet.mockRejectedValueOnce(new Error('Network error'));
			await loadSessions();
			expect(sessionStore.error).toBe('Network error');

			// Second load succeeds
			mockApiGet.mockResolvedValueOnce({ sessions: [], resumableCount: 0 });
			await loadSessions();
			expect(sessionStore.error).toBeNull();
		});

		it('sets isLoading during request', async () => {
			let loadingDuringRequest = false;
			mockApiGet.mockImplementation(async () => {
				loadingDuringRequest = sessionStore.isLoading;
				return { sessions: [], resumableCount: 0 };
			});

			await loadSessions();

			expect(loadingDuringRequest).toBe(true);
			expect(sessionStore.isLoading).toBe(false);
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// GET SESSION
	// ═══════════════════════════════════════════════════════════════════════════

	describe('getSession', () => {
		it('loads session detail and sets current', async () => {
			const mockDetail = createMockDetail({ sessionId: 'session-123' });
			mockApiGet.mockResolvedValueOnce(mockDetail);

			const result = await getSession('session-123');

			expect(mockApiGet).toHaveBeenCalledWith('/api/sessions/session-123');
			expect(result).toEqual(mockDetail);
			expect(sessionStore.currentSession).toEqual(mockDetail);
		});

		it('handles get error gracefully', async () => {
			mockApiGet.mockRejectedValueOnce(new Error('Session not found'));

			const result = await getSession('nonexistent');

			expect(result).toBeNull();
			expect(sessionStore.error).toBe('Session not found');
		});

		it('encodes session ID in URL', async () => {
			mockApiGet.mockResolvedValueOnce(createMockDetail());

			await getSession('session/with/slashes');

			expect(mockApiGet).toHaveBeenCalledWith('/api/sessions/session%2Fwith%2Fslashes');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// RESUME SESSION
	// ═══════════════════════════════════════════════════════════════════════════

	describe('resumeSession', () => {
		it('resumes session and updates state', async () => {
			// Load sessions first
			const pausedSession = createMockSession({ sessionId: 'session-1', status: 'paused' });
			mockApiGet.mockResolvedValueOnce({ sessions: [pausedSession], resumableCount: 1 });
			await loadSessions();

			// Resume
			const resumedDetail = createMockDetail({ sessionId: 'session-1', status: 'running' });
			mockApiPost.mockResolvedValueOnce(resumedDetail);

			const result = await resumeSession('session-1');

			expect(mockApiPost).toHaveBeenCalledWith('/api/sessions/session-1/resume', {});
			expect(result).toEqual(resumedDetail);
			expect(sessionStore.currentSession).toEqual(resumedDetail);

			// Should update session in list
			const sessionInList = sessionStore.sessions.find((s) => s.sessionId === 'session-1');
			expect(sessionInList?.status).toBe('running');
		});

		it('handles resume error gracefully', async () => {
			mockApiPost.mockRejectedValueOnce(new Error('Cannot resume completed session'));

			const result = await resumeSession('completed-session');

			expect(result).toBeNull();
			expect(sessionStore.error).toBe('Cannot resume completed session');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// PAUSE SESSION
	// ═══════════════════════════════════════════════════════════════════════════

	describe('pauseSession', () => {
		it('pauses session and updates state', async () => {
			// Load sessions first
			const runningSession = createMockSession({ sessionId: 'session-1', status: 'running' });
			mockApiGet.mockResolvedValueOnce({ sessions: [runningSession], resumableCount: 1 });
			await loadSessions();

			// Pause
			const pausedDetail = createMockDetail({ sessionId: 'session-1', status: 'paused' });
			mockApiPost.mockResolvedValueOnce(pausedDetail);

			const result = await pauseSession('session-1');

			expect(mockApiPost).toHaveBeenCalledWith('/api/sessions/session-1/pause', {});
			expect(result).toEqual(pausedDetail);
			expect(sessionStore.currentSession).toEqual(pausedDetail);

			// Should update session in list
			const sessionInList = sessionStore.sessions.find((s) => s.sessionId === 'session-1');
			expect(sessionInList?.status).toBe('paused');
		});

		it('handles pause error gracefully', async () => {
			mockApiPost.mockRejectedValueOnce(new Error('Session already paused'));

			const result = await pauseSession('session-1');

			expect(result).toBeNull();
			expect(sessionStore.error).toBe('Session already paused');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// DELETE SESSION
	// ═══════════════════════════════════════════════════════════════════════════

	describe('deleteSession', () => {
		it('deletes session and removes from list', async () => {
			// Load sessions first
			const sessions = [
				createMockSession({ sessionId: 'session-1' }),
				createMockSession({ sessionId: 'session-2' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 0 });
			await loadSessions();

			expect(sessionStore.sessions).toHaveLength(2);

			// Delete
			mockApiDelete.mockResolvedValueOnce(undefined);

			const result = await deleteSession('session-1');

			expect(mockApiDelete).toHaveBeenCalledWith('/api/sessions/session-1');
			expect(result).toBe(true);
			expect(sessionStore.sessions).toHaveLength(1);
			expect(sessionStore.sessions[0].sessionId).toBe('session-2');
		});

		it('clears current session if deleted', async () => {
			// Get session first
			const detail = createMockDetail({ sessionId: 'session-1' });
			mockApiGet.mockResolvedValueOnce(detail);
			await getSession('session-1');

			expect(sessionStore.currentSession).not.toBeNull();

			// Delete
			mockApiDelete.mockResolvedValueOnce(undefined);
			await deleteSession('session-1');

			expect(sessionStore.currentSession).toBeNull();
		});

		it('does not clear current session if different session deleted', async () => {
			// Load sessions and get one
			const sessions = [
				createMockSession({ sessionId: 'session-1' }),
				createMockSession({ sessionId: 'session-2' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 0 });
			await loadSessions();

			const detail = createMockDetail({ sessionId: 'session-1' });
			mockApiGet.mockResolvedValueOnce(detail);
			await getSession('session-1');

			// Delete different session
			mockApiDelete.mockResolvedValueOnce(undefined);
			await deleteSession('session-2');

			expect(sessionStore.currentSession?.sessionId).toBe('session-1');
		});

		it('handles delete error gracefully', async () => {
			mockApiDelete.mockRejectedValueOnce(new Error('Cannot delete running session'));

			const result = await deleteSession('running-session');

			expect(result).toBe(false);
			expect(sessionStore.error).toBe('Cannot delete running session');
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// HELPER FUNCTIONS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('clearCurrentSession', () => {
		it('clears current session', async () => {
			const detail = createMockDetail();
			mockApiGet.mockResolvedValueOnce(detail);
			await getSession('session-1');

			expect(sessionStore.currentSession).not.toBeNull();

			clearCurrentSession();

			expect(sessionStore.currentSession).toBeNull();
		});
	});

	describe('getSessionsByStatus', () => {
		it('filters sessions by status', async () => {
			const sessions = [
				createMockSession({ sessionId: 'session-1', status: 'completed' }),
				createMockSession({ sessionId: 'session-2', status: 'paused' }),
				createMockSession({ sessionId: 'session-3', status: 'completed' }),
				createMockSession({ sessionId: 'session-4', status: 'running' }),
				createMockSession({ sessionId: 'session-5', status: 'failed' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 2 });
			await loadSessions();

			const completed = getSessionsByStatus('completed');
			const paused = getSessionsByStatus('paused');
			const running = getSessionsByStatus('running');
			const failed = getSessionsByStatus('failed');

			expect(completed).toHaveLength(2);
			expect(paused).toHaveLength(1);
			expect(running).toHaveLength(1);
			expect(failed).toHaveLength(1);
		});

		it('returns empty array for no matches', async () => {
			const sessions = [
				createMockSession({ status: 'completed' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 0 });
			await loadSessions();

			const running = getSessionsByStatus('running');

			expect(running).toHaveLength(0);
		});
	});

	describe('getResumableSessions', () => {
		it('returns paused and running sessions', async () => {
			const sessions = [
				createMockSession({ sessionId: 'session-1', status: 'completed' }),
				createMockSession({ sessionId: 'session-2', status: 'paused' }),
				createMockSession({ sessionId: 'session-3', status: 'running' }),
				createMockSession({ sessionId: 'session-4', status: 'failed' }),
				createMockSession({ sessionId: 'session-5', status: 'paused' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 3 });
			await loadSessions();

			const resumable = getResumableSessions();

			expect(resumable).toHaveLength(3);
			expect(resumable.every((s) => s.status === 'paused' || s.status === 'running')).toBe(true);
		});

		it('returns empty array when no resumable sessions', async () => {
			const sessions = [
				createMockSession({ status: 'completed' }),
				createMockSession({ status: 'failed' }),
			];
			mockApiGet.mockResolvedValueOnce({ sessions, resumableCount: 0 });
			await loadSessions();

			const resumable = getResumableSessions();

			expect(resumable).toHaveLength(0);
		});
	});

	// ═══════════════════════════════════════════════════════════════════════════
	// CONCURRENT OPERATIONS
	// ═══════════════════════════════════════════════════════════════════════════

	describe('concurrent operations', () => {
		it('handles multiple operations sequentially', async () => {
			// Load
			mockApiGet.mockResolvedValueOnce({
				sessions: [createMockSession({ sessionId: 'session-1', status: 'running' })],
				resumableCount: 1,
			});
			await loadSessions();

			// Pause
			mockApiPost.mockResolvedValueOnce(createMockDetail({ sessionId: 'session-1', status: 'paused' }));
			await pauseSession('session-1');

			// Resume
			mockApiPost.mockResolvedValueOnce(createMockDetail({ sessionId: 'session-1', status: 'running' }));
			await resumeSession('session-1');

			// Final state should be running
			const sessionInList = sessionStore.sessions.find((s) => s.sessionId === 'session-1');
			expect(sessionInList?.status).toBe('running');
		});
	});
});
