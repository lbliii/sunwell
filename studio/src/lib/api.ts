/**
 * Unified API layer (RFC-113).
 *
 * This module provides a consistent API that uses HTTP/WebSocket communication
 * with the Python backend server.
 *
 * Usage:
 *   import { runGoal, onAgentEvent, stopAgent } from '$lib/api';
 *
 *   const unsubscribe = onAgentEvent((event) => { ... });
 *   await runGoal('Build a REST API');
 *   await stopAgent();
 */

import type { AgentEvent } from '$lib/types';
import { startRun, disconnect, onEvent } from '$lib/socket';

// ═══════════════════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════════════════

export interface RunGoalOptions {
	goal: string;
	projectPath?: string;
	projectId?: string; // RFC-117: Explicit project binding
	lens?: string | null;
	autoLens?: boolean;
	provider?: string | null;
}

export interface RunGoalResult {
	success: boolean;
	message: string;
	workspace_path: string;
}

type AgentEventListener = (event: AgentEvent) => void;

// ═══════════════════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════════════════

let _listeners: Set<AgentEventListener> = new Set();
let _unsubscribe: (() => void) | null = null;

// ═══════════════════════════════════════════════════════════════════════════
// API FUNCTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Run a goal with the agent.
 *
 * @param options - Goal and configuration
 * @returns Result with workspace path
 */
export async function runGoal(options: RunGoalOptions): Promise<RunGoalResult> {
	// Setup event forwarding if listeners are registered
	if (_listeners.size > 0 && !_unsubscribe) {
		_unsubscribe = onEvent((event) => {
			for (const listener of _listeners) {
				listener(event);
			}
		});
	}

	try {
		await startRun({
			goal: options.goal,
			workspace: options.projectPath,
			project_id: options.projectId,
			lens: options.lens ?? undefined,
			provider: options.provider ?? undefined,
		});

		return {
			success: true,
			message: 'Run started',
			workspace_path: options.projectPath || '.',
		};
	} catch (e) {
		return {
			success: false,
			message: e instanceof Error ? e.message : String(e),
			workspace_path: '',
		};
	}
}

/**
 * Stop the currently running agent.
 */
export async function stopAgent(): Promise<void> {
	disconnect();
}

/**
 * Subscribe to agent events.
 *
 * @param listener - Callback for each event
 * @returns Unsubscribe function
 */
export function onAgentEvent(listener: AgentEventListener): () => void {
	_listeners.add(listener);

	// Setup WebSocket event forwarding
	if (!_unsubscribe) {
		_unsubscribe = onEvent((event) => {
			for (const l of _listeners) {
				l(event);
			}
		});
	}

	return () => {
		_listeners.delete(listener);
		if (_listeners.size === 0 && _unsubscribe) {
			_unsubscribe();
			_unsubscribe = null;
		}
	};
}

/**
 * Check which backend is in use.
 */
export function getBackend(): 'http' {
	return 'http';
}

// ═══════════════════════════════════════════════════════════════════════════
// RE-EXPORTS FOR CONVENIENCE
// ═══════════════════════════════════════════════════════════════════════════

// Re-export socket functions for direct use when needed
export {
	getMemory,
	checkpointMemory,
	listLenses,
	getLens,
	getProject,
	analyzeProject,
	listProjectFiles,
	openFinder,
	openTerminal,
	openEditor,
	healthCheck,
} from '$lib/socket';
