/**
 * WebSocket client for HTTP bridge (RFC-113).
 *
 * All communication with the Python backend goes through HTTP REST + WebSocket.
 *
 * Features:
 * - Auto-reconnect with exponential backoff
 * - Event buffering for reconnection
 * - Type-safe event handling
 *
 * Usage:
 *   import { onEvent, startRun, cancelRun } from '$lib/socket';
 *
 *   // Subscribe to events
 *   const unsubscribe = onEvent((event) => {
 *     if (event.type === 'task_start') { ... }
 *   });
 *
 *   // Start a run
 *   const { run_id } = await startRun({ goal: 'Build a todo app' });
 *
 *   // Cancel
 *   await cancelRun(run_id);
 */

import type { AgentEvent } from '$lib/types';

// ═══════════════════════════════════════════════════════════════════════════
// CONFIGURATION
// ═══════════════════════════════════════════════════════════════════════════

/** Base URL for API calls. Defaults to Python server (:8080) in dev, same origin in prod. */
const API_BASE =
	import.meta.env.VITE_API_BASE || (import.meta.env.DEV ? 'http://127.0.0.1:8080' : '');

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface RunRequest {
	goal: string;
	workspace?: string;
	project_id?: string; // RFC-117: Explicit project binding
	lens?: string;
	provider?: string;
	model?: string;
	trust?: string;
	timeout?: number;
}

export interface RunResponse {
	run_id: string;
	status: string;
	error?: string;
}

type EventListener = (event: AgentEvent) => void;

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let _ws: WebSocket | null = null;
let _currentRunId: string | null = null;
let _reconnectAttempts = 0;
let _reconnectTimer: ReturnType<typeof setTimeout> | null = null;
const _listeners: Set<EventListener> = new Set();

// Stats for debugging (encapsulated for immutability)
interface SocketStats {
	readonly connected: boolean;
	readonly reconnects: number;
	readonly totalEvents: number;
	readonly droppedEvents: number;
	readonly lastLatency: number;
}

function createSocketStats() {
	let _stats: SocketStats = Object.freeze({
		connected: false,
		reconnects: 0,
		totalEvents: 0,
		droppedEvents: 0,
		lastLatency: 0,
	});

	return {
		get current(): SocketStats {
			return _stats;
		},
		update(partial: Partial<SocketStats>): void {
			_stats = Object.freeze({ ..._stats, ...partial });
		},
	};
}

const _socketStats = createSocketStats();

/** Read-only stats accessor */
export const stats = {
	get connected() { return _socketStats.current.connected; },
	get reconnects() { return _socketStats.current.reconnects; },
	get totalEvents() { return _socketStats.current.totalEvents; },
	get droppedEvents() { return _socketStats.current.droppedEvents; },
	get lastLatency() { return _socketStats.current.lastLatency; },
};

// ═══════════════════════════════════════════════════════════════════════════
// CONNECTION MANAGEMENT
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Connect to WebSocket for a specific run.
 * Called automatically by startRun().
 */
function connectWebSocket(runId: string): void {
	if (_ws && _ws.readyState === WebSocket.OPEN) {
		_ws.close();
	}

	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	const host = API_BASE ? new URL(API_BASE).host : window.location.host;
	const url = `${protocol}//${host}/api/run/${runId}/events`;

	console.log(`[socket] Connecting to ${url}`);
	_ws = new WebSocket(url);
	_currentRunId = runId;

	_ws.onopen = () => {
		console.log('[socket] Connected');
		_socketStats.update({ connected: true });
		_reconnectAttempts = 0;
	};

	_ws.onclose = (event) => {
		console.log(`[socket] Disconnected (code: ${event.code})`);
		_socketStats.update({ connected: false });

		// Don't reconnect if closed normally or run is done
		if (event.code === 1000 || event.code === 4004) {
			_currentRunId = null;
			return;
		}

		// Exponential backoff reconnect
		if (_currentRunId) {
			const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 10000);
			_reconnectAttempts++;
			_socketStats.update({ reconnects: _socketStats.current.reconnects + 1 });

			console.log(`[socket] Reconnecting in ${delay}ms...`);
			_reconnectTimer = setTimeout(() => {
				if (_currentRunId) {
					connectWebSocket(_currentRunId);
				}
			}, delay);
		}
	};

	_ws.onerror = (error) => {
		console.error('[socket] Error:', error);
	};

	_ws.onmessage = (msg) => {
		try {
			const event = JSON.parse(msg.data) as AgentEvent;
			_socketStats.update({ totalEvents: _socketStats.current.totalEvents + 1 });

			// Dispatch to all listeners
			for (const listener of _listeners) {
				try {
					listener(event);
				} catch (e) {
					console.error('[socket] Listener error:', e);
				}
			}

			// Clear run ID on terminal events
			if (event.type === 'complete' || event.type === 'error' || event.type === 'cancelled') {
				_currentRunId = null;
			}
		} catch (e) {
			console.error('[socket] Failed to parse message:', e);
		}
	};
}

/**
 * Disconnect WebSocket.
 */
export function disconnect(): void {
	if (_reconnectTimer) {
		clearTimeout(_reconnectTimer);
		_reconnectTimer = null;
	}
	if (_ws) {
		_ws.close();
		_ws = null;
	}
	_currentRunId = null;
	_socketStats.update({ connected: false });
}

// ═══════════════════════════════════════════════════════════════════════════
// EVENT SUBSCRIPTION
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Subscribe to agent events.
 *
 * @param listener - Callback for each event
 * @returns Unsubscribe function
 *
 * @example
 * const unsubscribe = onEvent((event) => {
 *   if (event.type === 'task_start') {
 *     console.log('Task started:', event.data);
 *   }
 * });
 *
 * // Later: unsubscribe();
 */
export function onEvent(listener: EventListener): () => void {
	_listeners.add(listener);
	return () => {
		_listeners.delete(listener);
	};
}

// ═══════════════════════════════════════════════════════════════════════════
// API CALLS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Start an agent run.
 *
 * @param request - Run configuration
 * @returns Run response with run_id
 *
 * @example
 * const { run_id } = await startRun({ goal: 'Build a REST API' });
 */
export async function startRun(request: RunRequest): Promise<RunResponse> {
	const response = await fetch(`${API_BASE}/api/run`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json' },
		body: JSON.stringify(request),
	});

	const result = (await response.json()) as RunResponse;

	if (!response.ok) {
		throw new Error(`Failed to start run: ${response.status} ${result.error || 'Unknown error'}`);
	}

	if (result.error) {
		throw new Error(result.error);
	}

	if (!result.run_id) {
		throw new Error('Server returned success but no run_id');
	}

	// Connect WebSocket to stream events
	connectWebSocket(result.run_id);

	return result;
}

/**
 * Cancel a running agent.
 *
 * @param runId - The run ID to cancel
 */
export async function cancelRun(runId: string): Promise<void> {
	await fetch(`${API_BASE}/api/run/${runId}`, {
		method: 'DELETE',
	});
	disconnect();
}

/**
 * Get run status.
 *
 * @param runId - The run ID
 */
export async function getRunStatus(runId: string): Promise<RunResponse> {
	const response = await fetch(`${API_BASE}/api/run/${runId}`);
	return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// REST API HELPERS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Generic fetch wrapper for REST endpoints.
 */
export async function apiGet<T>(path: string): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`);
	return response.json();
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, {
		method: 'POST',
		headers: body ? { 'Content-Type': 'application/json' } : {},
		body: body ? JSON.stringify(body) : undefined,
	});
	return response.json();
}

export async function apiDelete<T>(path: string): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, { method: 'DELETE' });
	return response.json();
}

export async function apiPut<T>(path: string, body?: unknown): Promise<T> {
	const response = await fetch(`${API_BASE}${path}`, {
		method: 'PUT',
		headers: body ? { 'Content-Type': 'application/json' } : {},
		body: body ? JSON.stringify(body) : undefined,
	});
	return response.json();
}

// ═══════════════════════════════════════════════════════════════════════════
// SPECIFIC API ENDPOINTS
// ═══════════════════════════════════════════════════════════════════════════

/** Get memory (Simulacrum) */
export const getMemory = () => apiGet<{ learnings: unknown[]; dead_ends: unknown[] }>('/api/memory');

/** Save memory checkpoint */
export const checkpointMemory = () => apiPost<{ status: string }>('/api/memory/checkpoint');

/** List lenses */
export const listLenses = () => apiGet<Array<{ id: string; name: string; description: string }>>('/api/lenses');

/** Get lens details */
export const getLens = (id: string) => apiGet<{ id: string; name: string; skills: string[] }>(`/api/lenses/${id}`);

/** Get current project */
export const getProject = () => apiGet<{ path: string; name: string }>('/api/project');

/** Analyze project */
export const analyzeProject = (path: string) => apiPost<unknown>('/api/project/analyze', { path });

/** List project files */
export const listProjectFiles = (path?: string, maxDepth = 3) =>
	apiGet<{ files: unknown[] }>(`/api/project/files?path=${encodeURIComponent(path || '')}&max_depth=${maxDepth}`);

/** Open in Finder/Explorer */
export const openFinder = (path: string) => apiPost<{ status: string }>('/api/shell/open-finder', { path });

/** Open terminal */
export const openTerminal = (path: string) => apiPost<{ status: string }>('/api/shell/open-terminal', { path });

/** Open in editor */
export const openEditor = (path: string) => apiPost<{ status: string }>('/api/shell/open-editor', { path });

/** Health check */
export const healthCheck = () => apiGet<{ status: string; active_runs: number }>('/api/health');

// ═══════════════════════════════════════════════════════════════════════════
// GLOBAL EVENT STREAM (RFC-119)
// ═══════════════════════════════════════════════════════════════════════════

/** Run info with source tracking */
export interface RunInfo {
	run_id: string;
	goal: string;
	status: string;
	source: 'cli' | 'studio' | 'api';
	started_at: string;
	completed_at: string | null;
	event_count: number;
}

/** Global event with source metadata */
export interface GlobalEvent {
	v: number;
	run_id: string;
	type: string;
	data: Record<string, unknown>;
	timestamp: string;
	source: 'cli' | 'studio' | 'api';
	project_id: string | null;
}

type GlobalEventListener = (event: GlobalEvent) => void;

let _globalWs: WebSocket | null = null;
let _globalReconnectTimer: ReturnType<typeof setTimeout> | null = null;
let _globalReconnectAttempts = 0;
const _globalListeners: Set<GlobalEventListener> = new Set();

/** Global event stream stats (encapsulated for immutability) */
interface GlobalSocketStats {
	readonly connected: boolean;
	readonly reconnects: number;
	readonly totalEvents: number;
}

function createGlobalSocketStats() {
	let _stats: GlobalSocketStats = Object.freeze({
		connected: false,
		reconnects: 0,
		totalEvents: 0,
	});

	return {
		get current(): GlobalSocketStats {
			return _stats;
		},
		update(partial: Partial<GlobalSocketStats>): void {
			_stats = Object.freeze({ ..._stats, ...partial });
		},
	};
}

const _globalSocketStats = createGlobalSocketStats();

/** Read-only global stats accessor */
export const globalStats = {
	get connected() { return _globalSocketStats.current.connected; },
	get reconnects() { return _globalSocketStats.current.reconnects; },
	get totalEvents() { return _globalSocketStats.current.totalEvents; },
};

/**
 * Subscribe to ALL events across CLI and Studio.
 * 
 * @param projectId - Optional project filter
 * @returns Cleanup function to close connection
 * 
 * @example
 * const cleanup = subscribeToGlobalEvents();
 * onGlobalEvent((event) => {
 *   console.log('Event from', event.source, ':', event.type);
 * });
 */
export function subscribeToGlobalEvents(projectId?: string): () => void {
	// Close existing connection
	if (_globalWs) {
		_globalWs.close();
		_globalWs = null;
	}

	const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
	const host = API_BASE ? new URL(API_BASE).host : window.location.host;
	const params = projectId ? `?project_id=${encodeURIComponent(projectId)}` : '';
	const url = `${protocol}//${host}/api/events${params}`;

	console.log(`[socket] Connecting to global event stream: ${url}`);
	_globalWs = new WebSocket(url);

	_globalWs.onopen = () => {
		console.log('[socket] Global event stream connected');
		_globalSocketStats.update({ connected: true });
		_globalReconnectAttempts = 0;
	};

	_globalWs.onclose = (event) => {
		console.log(`[socket] Global event stream disconnected (code: ${event.code})`);
		_globalSocketStats.update({ connected: false });

		// Auto-reconnect unless explicitly closed
		if (event.code !== 1000) {
			const delay = Math.min(1000 * Math.pow(2, _globalReconnectAttempts), 10000);
			_globalReconnectAttempts++;
			_globalSocketStats.update({ reconnects: _globalSocketStats.current.reconnects + 1 });

			console.log(`[socket] Global stream reconnecting in ${delay}ms...`);
			_globalReconnectTimer = setTimeout(() => {
				subscribeToGlobalEvents(projectId);
			}, delay);
		}
	};

	_globalWs.onerror = (error) => {
		console.error('[socket] Global event stream error:', error);
	};

	_globalWs.onmessage = (msg) => {
		try {
			const event = JSON.parse(msg.data) as GlobalEvent;
			_globalSocketStats.update({ totalEvents: _globalSocketStats.current.totalEvents + 1 });

			// Dispatch to all listeners
			for (const listener of _globalListeners) {
				try {
					listener(event);
				} catch (e) {
					console.error('[socket] Global listener error:', e);
				}
			}
		} catch (e) {
			console.error('[socket] Failed to parse global event:', e);
		}
	};

	// Return cleanup function
	return () => {
		if (_globalReconnectTimer) {
			clearTimeout(_globalReconnectTimer);
			_globalReconnectTimer = null;
		}
		if (_globalWs) {
			_globalWs.close();
			_globalWs = null;
		}
		_globalSocketStats.update({ connected: false });
	};
}

/**
 * Add listener for global events.
 * 
 * @param listener - Callback for each global event
 * @returns Unsubscribe function
 */
export function onGlobalEvent(listener: GlobalEventListener): () => void {
	_globalListeners.add(listener);
	return () => _globalListeners.delete(listener);
}

/**
 * Disconnect global event stream.
 */
export function disconnectGlobal(): void {
	if (_globalReconnectTimer) {
		clearTimeout(_globalReconnectTimer);
		_globalReconnectTimer = null;
	}
	if (_globalWs) {
		_globalWs.close();
		_globalWs = null;
	}
	_globalSocketStats.update({ connected: false });
}

/**
 * List all runs from server.
 * 
 * @param projectId - Optional project filter
 * @param limit - Max runs to return (default: 20)
 */
export const listRuns = (projectId?: string, limit = 20) => {
	const params = new URLSearchParams();
	if (projectId) params.set('project_id', projectId);
	params.set('limit', String(limit));
	return apiGet<{ runs: RunInfo[] }>(`/api/runs?${params.toString()}`);
};

// ═══════════════════════════════════════════════════════════════════════════
// OBSERVATORY API (RFC-112)
// ═══════════════════════════════════════════════════════════════════════════

/** Observatory snapshot data for a run */
export interface ObservatoryData {
	run_id: string;
	resonance_iterations: Array<{
		round: number;
		current_score?: number;
		new_score?: number;
		improved?: boolean;
		improvements_identified?: string;
		reason?: string;
	}>;
	prism_candidates: Array<{
		id: string;
		artifact_count: number;
		score?: number;
		variance_config?: {
			prompt_style?: string;
			temperature?: number;
			constraint?: string;
		};
	}>;
	selected_candidate: {
		id: string;
		artifact_count: number;
		score?: number;
		selection_reason?: string;
	} | null;
	tasks: Array<{
		id: string;
		description: string;
		status: string;
		progress: number;
	}>;
	learnings: string[];
	convergence_iterations: Array<{
		iteration: number;
		all_passed: boolean;
		total_errors: number;
		gate_results: Array<{
			gate: string;
			passed: boolean;
			errors: number;
		}>;
	}>;
	convergence_status: string | null;
}

/**
 * Get Observatory visualization data for a run.
 * 
 * @param runId - The run ID
 */
export const getObservatoryData = (runId: string) => {
	return apiGet<ObservatoryData>(`/api/observatory/data/${runId}`);
};

/**
 * Get all events for a run (for replay).
 * 
 * @param runId - The run ID
 */
export const getRunEvents = (runId: string) => {
	return apiGet<{ run_id: string; events: Array<Record<string, unknown>> }>(`/api/run/${runId}/events`);
};
