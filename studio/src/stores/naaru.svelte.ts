/**
 * Naaru Store — Unified orchestration state management (RFC-083)
 *
 * THE store for all Naaru interaction. All UI interaction goes through here.
 *
 * This replaces fragmented stores:
 * - home.svelte.ts → naaruStore.process()
 * - interface.svelte.ts → naaruStore.process()
 * - Various ad-hoc stores → consolidated here
 *
 * RFC-113: Uses HTTP API instead of Tauri for all communication.
 */

import { apiGet, onEvent, startRun } from '$lib/socket';
import type { AgentEvent } from '$lib/types';

// ═══════════════════════════════════════════════════════════════════════════
// TYPES (match Python exactly - RFC-083)
// ═══════════════════════════════════════════════════════════════════════════

export type ProcessMode = 'auto' | 'chat' | 'agent' | 'interface';
export type PageType = 'home' | 'project' | 'research' | 'planning' | 'conversation';
export type InputMode = 'hero' | 'chat' | 'command' | 'search';
export type RouteType = 'workspace' | 'view' | 'action' | 'conversation' | 'hybrid';

export type NaaruEventType =
	| 'process_start'
	| 'process_complete'
	| 'process_error'
	| 'route_decision'
	| 'composition_ready'
	| 'composition_updated'
	| 'model_start'
	| 'model_thinking'
	| 'model_tokens'
	| 'model_complete'
	| 'task_start'
	| 'task_progress'
	| 'task_complete'
	| 'task_error'
	| 'tool_call'
	| 'tool_result'
	| 'validation_start'
	| 'validation_result'
	| 'learning_extracted'
	| 'learning_persisted';

export interface ConversationMessage {
	role: 'user' | 'assistant';
	content: string;
}

export interface ProcessInput {
	content: string;
	mode?: ProcessMode;
	page_type?: PageType;
	conversation_history?: ConversationMessage[];
	workspace?: string;
	stream?: boolean;
	timeout?: number;
	context?: Record<string, unknown>;
	/** Model provider (RFC-Cloud-Model-Parity) */
	provider?: string;
	/** Model name override */
	model?: string;
}

export interface CompositionSpec {
	page_type: PageType;
	panels: Array<{
		panel_type: string;
		title?: string;
		data?: Record<string, unknown>;
	}>;
	input_mode: InputMode;
	suggested_tools: string[];
	confidence: number;
	source: 'regex' | 'fast_model' | 'large_model';
}

export interface RoutingDecision {
	interaction_type: RouteType;
	confidence: number;
	tier: number;
	lens?: string;
	page_type: PageType;
	tools: string[];
	mood?: string;
	reasoning?: string;
}

export interface NaaruEvent {
	type: NaaruEventType;
	timestamp: string;
	data: Record<string, unknown>;
}

export interface ProcessOutput {
	response: string;
	route_type: RouteType;
	confidence: number;
	composition: CompositionSpec | null;
	tasks_completed: number;
	artifacts: string[];
	events: NaaruEvent[];
	routing: RoutingDecision | null;
}

export interface ConvergenceSlot {
	id: string;
	content: unknown;
	relevance: number;
	source: string;
	ready: boolean;
}

// ═══════════════════════════════════════════════════════════════════════════
// STATE (reactive with Svelte 5 runes)
// ═══════════════════════════════════════════════════════════════════════════

interface NaaruState {
	// Processing state
	isProcessing: boolean;
	error: string | null;

	// Current response
	response: ProcessOutput | null;

	// Streaming content (accumulated)
	streamedContent: string;

	// Convergence mirror (read-only view of Python state)
	convergence: {
		composition: CompositionSpec | null;
		routing: RoutingDecision | null;
		context: unknown | null;
	};

	// Event stream (for real-time UI)
	events: NaaruEvent[];

	// Conversation history (local, sent with each request)
	conversationHistory: Array<{
		role: 'user' | 'assistant';
		content: string;
		timestamp: number;
	}>;
}

function createInitialState(): NaaruState {
	return {
		isProcessing: false,
		error: null,
		response: null,
		streamedContent: '',
		convergence: {
			composition: null,
			routing: null,
			context: null,
		},
		events: [],
		conversationHistory: [],
	};
}

export let naaruState = $state<NaaruState>(createInitialState());

// ═══════════════════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════════════════

/**
 * THE function. All UI interaction goes through here.
 *
 * Uses HTTP API (RFC-113) for all communication with Python backend.
 *
 * @param input - ProcessInput with content and options
 * @returns ProcessOutput with response and metadata
 */
export async function process(input: ProcessInput): Promise<ProcessOutput> {
	naaruState.isProcessing = true;
	naaruState.error = null;
	naaruState.events = [];
	naaruState.streamedContent = '';

	// Add to conversation history
	naaruState.conversationHistory = [
		...naaruState.conversationHistory,
		{
			role: 'user',
			content: input.content,
			timestamp: Date.now(),
		},
	];

	try {
		// Start agent run via HTTP API (RFC-113)
		await startRun({
			goal: input.content,
			workspace: input.workspace,
			provider: input.provider,
			model: input.model,
		});

		// Wait for completion by collecting events
		const result = await new Promise<ProcessOutput>((resolve, reject) => {
			let response = '';
			let tasksCompleted = 0;
			const artifacts: string[] = [];
			const events: NaaruEvent[] = [];

			const unsubscribe = onEvent((event: AgentEvent) => {
				// Convert to NaaruEvent format
				const naaruEvent: NaaruEvent = {
					type: event.type as NaaruEventType,
					timestamp: new Date().toISOString(),
					data: event.data || {},
				};
				events.push(naaruEvent);
				naaruState.events = [...naaruState.events, naaruEvent];

				// Handle specific event types
				if (event.type === 'model_tokens' && event.data?.content) {
					naaruState.streamedContent += event.data.content as string;
					response += event.data.content as string;
				}
				if (event.type === 'task_complete') {
					tasksCompleted++;
				}
				if (event.type === 'file_written' && event.data?.path) {
					artifacts.push(event.data.path as string);
				}

				// Resolve on completion
				if (event.type === 'complete' || event.type === 'error' || event.type === 'cancelled') {
					unsubscribe();
					if (event.type === 'error') {
						reject(new Error((event.data?.message as string) || 'Agent execution failed'));
					} else {
						resolve({
							response: response || (event.data?.response as string) || '',
							route_type: 'workspace',
							confidence: 0.9,
							composition: null,
							tasks_completed: tasksCompleted,
							artifacts,
							events,
							routing: null,
						});
					}
				}
			});

			// Timeout after configured time
			setTimeout(() => {
				unsubscribe();
				reject(new Error('Request timeout'));
			}, (input.timeout || 300) * 1000);
		});

		naaruState.response = result;

		// Update convergence mirror
		if (result.composition) {
			naaruState.convergence.composition = result.composition;
		}
		if (result.routing) {
			naaruState.convergence.routing = result.routing;
		}

		// Add assistant response to history
		if (result.response) {
			naaruState.conversationHistory = [
				...naaruState.conversationHistory,
				{
					role: 'assistant',
					content: result.response,
					timestamp: Date.now(),
				},
			];
		}

		return result;
	} catch (e) {
		const errorMessage = e instanceof Error ? e.message : String(e);
		naaruState.error = errorMessage;

		// Return error response
		const errorResponse: ProcessOutput = {
			response: `Sorry, I encountered an error: ${errorMessage}`,
			route_type: 'conversation',
			confidence: 0,
			composition: null,
			tasks_completed: 0,
			artifacts: [],
			events: [],
			routing: null,
		};

		naaruState.response = errorResponse;

		naaruState.conversationHistory = [
			...naaruState.conversationHistory,
			{
				role: 'assistant',
				content: errorResponse.response,
				timestamp: Date.now(),
			},
		];

		return errorResponse;
	} finally {
		naaruState.isProcessing = false;
	}
}

/**
 * Subscribe to real-time Naaru events.
 * Call once on app init.
 *
 * RFC-113: Uses WebSocket events instead of Tauri event listener.
 */
export function subscribeToEvents(): () => void {
	const unsubscribe = onEvent((event: AgentEvent) => {
		// Convert to NaaruEvent format
		const naaruEvent: NaaruEvent = {
			type: event.type as NaaruEventType,
			timestamp: new Date().toISOString(),
			data: event.data || {},
		};
		naaruState.events = [...naaruState.events, naaruEvent];

		// Update state based on event type
		switch (event.type) {
			case 'composition_ready':
				naaruState.convergence.composition = event.data as unknown as CompositionSpec;
				break;
			case 'route_decision':
				naaruState.convergence.routing = event.data as unknown as RoutingDecision;
				break;
			case 'model_tokens':
				naaruState.streamedContent += (event.data?.content as string) || '';
				break;
			case 'error':
				naaruState.error = (event.data?.message as string) || 'Unknown error';
				break;
		}
	});

	return unsubscribe;
}

/**
 * Read a specific Convergence slot.
 *
 * RFC-113: Uses HTTP API endpoint instead of Tauri invoke.
 *
 * @param slot - Slot ID like "routing:current" or "composition:current"
 * @returns ConvergenceSlot or null if not found
 */
export async function getConvergenceSlot(slot: string): Promise<ConvergenceSlot | null> {
	try {
		const result = await apiGet<ConvergenceSlot | null>(`/api/convergence/${encodeURIComponent(slot)}`);
		return result;
	} catch {
		return null;
	}
}

/**
 * Cancel current processing.
 *
 * RFC-113: Uses disconnect from socket module.
 */
export async function cancel(): Promise<void> {
	const { disconnect } = await import('$lib/socket');
	disconnect();
	naaruState.isProcessing = false;
}

/**
 * Clear conversation history (new session).
 */
export function clearHistory(): void {
	naaruState.conversationHistory = [];
	naaruState.response = null;
	naaruState.events = [];
	naaruState.streamedContent = '';
	naaruState.convergence = {
		composition: null,
		routing: null,
		context: null,
	};
}

/**
 * Reset to initial state.
 */
export function resetNaaru(): void {
	Object.assign(naaruState, createInitialState());
}

// ═══════════════════════════════════════════════════════════════════════════
// DERIVED STATE (computed values)
// ═══════════════════════════════════════════════════════════════════════════

/**
 * Get the current response text (streamed or final).
 */
export function getResponseText(): string {
	if (naaruState.isProcessing && naaruState.streamedContent) {
		return naaruState.streamedContent;
	}
	return naaruState.response?.response || '';
}

/**
 * Check if we have an active composition.
 */
export function hasComposition(): boolean {
	return naaruState.convergence.composition !== null;
}

/**
 * Get current route type.
 */
export function getRouteType(): RouteType | null {
	return naaruState.response?.route_type || naaruState.convergence.routing?.interaction_type || null;
}

// ═══════════════════════════════════════════════════════════════════════════
// TYPE GUARDS
// ═══════════════════════════════════════════════════════════════════════════

export function isConversationRoute(): boolean {
	return getRouteType() === 'conversation';
}

export function isActionRoute(): boolean {
	return getRouteType() === 'action';
}

export function isViewRoute(): boolean {
	return getRouteType() === 'view';
}

export function isWorkspaceRoute(): boolean {
	return getRouteType() === 'workspace';
}

export function isHybridRoute(): boolean {
	return getRouteType() === 'hybrid';
}
