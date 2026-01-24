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

// Stats for debugging (plain object, not reactive)
export const stats = {
	connected: false,
	reconnects: 0,
	totalEvents: 0,
	droppedEvents: 0,
	lastLatency: 0,
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
		stats.connected = true;
		_reconnectAttempts = 0;
	};

	_ws.onclose = (event) => {
		console.log(`[socket] Disconnected (code: ${event.code})`);
		stats.connected = false;

		// Don't reconnect if closed normally or run is done
		if (event.code === 1000 || event.code === 4004) {
			_currentRunId = null;
			return;
		}

		// Exponential backoff reconnect
		if (_currentRunId) {
			const delay = Math.min(1000 * Math.pow(2, _reconnectAttempts), 10000);
			_reconnectAttempts++;
			stats.reconnects++;

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
			stats.totalEvents++;

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
	stats.connected = false;
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

	if (result.error) {
		throw new Error(result.error);
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
