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

// ═══════════════════════════════════════════════════════════════════════════
// DISCRIMINATED EVENT DATA TYPES
// ═══════════════════════════════════════════════════════════════════════════

/** Event data for model_tokens events */
export interface ModelTokensEventData {
	readonly content: string;
}

/** Event data for task_complete events */
export interface TaskCompleteEventData {
	readonly taskId?: string;
	readonly result?: string;
}

/** Event data for file_written events */
export interface FileWrittenEventData {
	readonly path: string;
}

/** Event data for error events */
export interface ErrorEventData {
	readonly message: string;
	readonly code?: string;
}

/** Event data for route_decision events */
export interface RouteDecisionEventData extends RoutingDecision { }

/** Event data for composition_ready events */
export interface CompositionReadyEventData extends CompositionSpec { }

/** Union of all typed event data */
export type NaaruEventData =
	| ModelTokensEventData
	| TaskCompleteEventData
	| FileWrittenEventData
	| ErrorEventData
	| RouteDecisionEventData
	| CompositionReadyEventData
	| Record<string, unknown>; // Fallback for untyped events

export interface ConversationMessage {
	readonly role: 'user' | 'assistant';
	readonly content: string;
}

export interface ProcessInput {
	readonly content: string;
	readonly mode?: ProcessMode;
	readonly page_type?: PageType;
	readonly conversation_history?: readonly ConversationMessage[];
	readonly workspace?: string;
	readonly stream?: boolean;
	readonly timeout?: number;
	readonly context?: Readonly<Record<string, unknown>>;
	/** Model provider (RFC-Cloud-Model-Parity) */
	readonly provider?: string;
	/** Model name override */
	readonly model?: string;
}

export interface CompositionSpec {
	readonly page_type: PageType;
	readonly panels: readonly {
		readonly panel_type: string;
		readonly title?: string;
		readonly data?: Readonly<Record<string, unknown>>;
	}[];
	readonly input_mode: InputMode;
	readonly suggested_tools: readonly string[];
	readonly confidence: number;
	readonly source: 'regex' | 'fast_model' | 'large_model';
}

export interface RoutingDecision {
	readonly interaction_type: RouteType;
	readonly confidence: number;
	readonly tier: number;
	readonly lens?: string;
	readonly page_type: PageType;
	readonly tools: readonly string[];
	readonly mood?: string;
	readonly reasoning?: string;
}

export interface NaaruEvent {
	readonly type: NaaruEventType;
	readonly timestamp: string;
	readonly data: NaaruEventData;
}

export interface ProcessOutput {
	readonly response: string;
	readonly route_type: RouteType;
	readonly confidence: number;
	readonly composition: CompositionSpec | null;
	readonly tasks_completed: number;
	readonly artifacts: readonly string[];
	readonly events: readonly NaaruEvent[];
	readonly routing: RoutingDecision | null;
}

export interface ConvergenceSlot {
	readonly id: string;
	readonly content: unknown;
	readonly relevance: number;
	readonly source: string;
	readonly ready: boolean;
}

// Type guards for event data
function isCompositionSpec(data: unknown): data is CompositionSpec {
	if (typeof data !== 'object' || data === null) return false;
	const d = data as Record<string, unknown>;
	return typeof d.page_type === 'string' &&
		Array.isArray(d.panels) &&
		typeof d.input_mode === 'string' &&
		Array.isArray(d.suggested_tools) &&
		typeof d.confidence === 'number' &&
		typeof d.source === 'string';
}

function isRoutingDecision(data: unknown): data is RoutingDecision {
	if (typeof data !== 'object' || data === null) return false;
	const d = data as Record<string, unknown>;
	return typeof d.interaction_type === 'string' &&
		typeof d.confidence === 'number' &&
		typeof d.tier === 'number' &&
		typeof d.page_type === 'string' &&
		Array.isArray(d.tools);
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
				// Convert to NaaruEvent format with typed data
				const eventData: NaaruEventData = event.data || {};
				const naaruEvent: NaaruEvent = {
					type: event.type as NaaruEventType,
					timestamp: new Date().toISOString(),
					data: eventData,
				};
				events.push(naaruEvent);
				naaruState.events = [...naaruState.events, naaruEvent];

				// Handle specific event types with type-safe extraction
				if (event.type === 'model_tokens') {
					const content = getTokenContent(eventData);
					if (content) {
						naaruState.streamedContent += content;
						response += content;
					}
				}
				if (event.type === 'task_complete') {
					tasksCompleted++;
				}
				if (event.type === 'file_written') {
					const path = getFilePath(eventData);
					if (path) {
						artifacts.push(path);
					}
				}

				// Resolve on completion
				if (event.type === 'complete' || event.type === 'error' || event.type === 'cancelled') {
					unsubscribe();
					if (event.type === 'error') {
						reject(new Error(getErrorMessage(eventData)));
					} else {
						resolve({
							response: response || getResponseString(eventData),
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
		// Convert to NaaruEvent format with typed data
		const eventData: NaaruEventData = event.data || {};
		const naaruEvent: NaaruEvent = {
			type: event.type as NaaruEventType,
			timestamp: new Date().toISOString(),
			data: eventData,
		};
		naaruState.events = [...naaruState.events, naaruEvent];

		// Update state based on event type with type-safe extraction
		switch (event.type) {
			case 'composition_ready':
				if (isCompositionSpec(eventData)) {
					naaruState.convergence.composition = eventData;
				}
				break;
			case 'route_decision':
				if (isRoutingDecision(eventData)) {
					naaruState.convergence.routing = eventData;
				}
				break;
			case 'model_tokens':
				naaruState.streamedContent += getTokenContent(eventData);
				break;
			case 'error':
				naaruState.error = getErrorMessage(eventData);
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
