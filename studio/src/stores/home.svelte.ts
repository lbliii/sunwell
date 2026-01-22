/**
 * Home Store — Unified Home Surface state management (RFC-080)
 *
 * Manages the state for the unified input routing on Home.
 * Routes through existing InteractionRouter (RFC-075) and renders blocks.
 */

import { invoke } from '@tauri-apps/api/core';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type RouteType = 'workspace' | 'view' | 'action' | 'conversation' | 'hybrid';
export type PageType = 'home' | 'project' | 'research' | 'planning' | 'conversation';
export type InputMode = 'hero' | 'chat' | 'command' | 'search';

/**
 * Speculative composition from fast Tier 0/1 analysis.
 * Used to render UI skeleton before full content is ready.
 */
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

export interface ViewResponse {
	route: 'view';
	view_type: string;
	view_data: Record<string, unknown>;
	response?: string;
}

export interface ActionResponse {
	route: 'action';
	action_type: string;
	success: boolean;
	response: string;
	data?: Record<string, unknown>;
}

export interface AuxiliaryPanel {
	panel_type: string;
	title?: string;
	data?: Record<string, unknown>;
}

export interface ConversationResponse {
	route: 'conversation';
	response: string;
	conversation_mode?: 'informational' | 'empathetic' | 'collaborative';
	auxiliary_panels?: AuxiliaryPanel[];
	suggested_tools?: string[];
}

export interface WorkspaceResponse {
	route: 'workspace';
	layout_id: string;
	response?: string;
	workspace_spec?: {
		primary: string;
		secondary: string[];
		contextual: string[];
		arrangement: string;
		seed_content?: Record<string, unknown>;
	};
}

export interface HybridResponse {
	route: 'hybrid';
	action_type: string;
	success: boolean;
	response: string;
	view_type: string;
	view_data: Record<string, unknown>;
}

export type HomeResponse =
	| ViewResponse
	| ActionResponse
	| ConversationResponse
	| WorkspaceResponse
	| HybridResponse;

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface HomeState {
	/** Current response being displayed */
	response: HomeResponse | null;

	/** Is routing in progress */
	isProcessing: boolean;

	/** Error state */
	error: string | null;

	/** Conversation history for follow-ups */
	conversationHistory: Array<{
		role: 'user' | 'assistant';
		content: string;
		timestamp: number;
	}>;

	/** Data directory for providers */
	dataDir: string | null;

	// ═══════════════════════════════════════════════════════════
	// SPECULATIVE UI (RFC-082)
	// ═══════════════════════════════════════════════════════════

	/**
	 * Speculative composition from fast analysis (Tier 0/1).
	 * Rendered as skeleton while waiting for full content.
	 */
	speculativeComposition: CompositionSpec | null;

	/**
	 * Is the speculative composition being computed?
	 * Very brief - only 0-200ms for Tier 0/1.
	 */
	isCompositing: boolean;
}

function createInitialState(): HomeState {
	return {
		response: null,
		isProcessing: false,
		error: null,
		conversationHistory: [],
		dataDir: null,
		speculativeComposition: null,
		isCompositing: false,
	};
}

export let homeState = $state<HomeState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Get speculative composition from fast Tier 0/1 analysis.
 * This runs in ~100-200ms and provides layout before content is ready.
 */
export async function getSpeculativeComposition(input: string): Promise<CompositionSpec | null> {
	homeState.isCompositing = true;
	try {
		const result = await invoke<CompositionSpec | null>('predict_composition', {
			input,
			currentPage: homeState.speculativeComposition?.page_type || 'home',
		});
		if (result && result.confidence >= 0.7) {
			homeState.speculativeComposition = result;
		}
		return result;
	} catch {
		// Tier 0/1 failure is non-fatal - we'll get layout from Tier 2
		return null;
	} finally {
		homeState.isCompositing = false;
	}
}

/**
 * Route user input through the InteractionRouter (RFC-075).
 *
 * Uses speculative rendering (RFC-082):
 * 1. Immediately start fast composition (Tier 0/1) - ~100ms
 * 2. In parallel, start full content generation (Tier 2) - ~2-5s
 * 3. Render skeleton with speculative layout
 * 4. Stream content into skeleton as it arrives
 */
export async function routeInput(input: string): Promise<HomeResponse> {
	homeState.isProcessing = true;
	homeState.error = null;

	// Add to conversation history
	homeState.conversationHistory = [
		...homeState.conversationHistory,
		{
			role: 'user',
			content: input,
			timestamp: Date.now(),
		},
	];

	// Prepare history for backend (convert to simple format)
	const history = homeState.conversationHistory.map((msg) => ({
		role: msg.role,
		content: msg.content,
	}));

	// ═══════════════════════════════════════════════════════════
	// PARALLEL EXECUTION (RFC-082)
	// ═══════════════════════════════════════════════════════════

	// Start both in parallel:
	// - Fast composition (Tier 0/1): ~100-200ms
	// - Full content (Tier 2): ~2-5s
	const compositionPromise = getSpeculativeComposition(input);
	const contentPromise = invoke<Record<string, unknown>>('process_goal', {
		goal: input,
		dataDir: homeState.dataDir,
		history: history.length > 1 ? history.slice(0, -1) : undefined,
	});

	try {
		// Wait for fast composition first (renders skeleton immediately)
		await compositionPromise;

		// Then wait for full content
		const result = await contentPromise;

		// Map backend response to HomeResponse type
		const response = mapBackendResponse(result);
		homeState.response = response;

		// Clear speculative composition once we have real response
		// (Keep it if response matches, clear if it was wrong)
		if (homeState.speculativeComposition) {
			const specPage = homeState.speculativeComposition.page_type;
			const actualPage = response.route === 'conversation' ? 'conversation' : response.route;
			if (specPage !== actualPage) {
				// Speculative was wrong - large model overrides
				homeState.speculativeComposition = null;
			}
		}

		// Add assistant response to history
		if (response.route === 'conversation' || response.route === 'view') {
			const responseText =
				response.route === 'conversation' ? response.response : response.response || '';
			if (responseText) {
				homeState.conversationHistory = [
					...homeState.conversationHistory,
					{
						role: 'assistant',
						content: responseText,
						timestamp: Date.now(),
					},
				];
			}
		}

		return response;
	} catch (e) {
		const errorMessage = e instanceof Error ? e.message : String(e);
		homeState.error = errorMessage;
		console.error('Home routing failed:', e);

		// Return error as conversation
		const errorResponse: ConversationResponse = {
			route: 'conversation',
			response: `Sorry, I encountered an error: ${errorMessage}`,
			conversation_mode: 'informational',
		};
		homeState.response = errorResponse;
		homeState.speculativeComposition = null;

		homeState.conversationHistory = [
			...homeState.conversationHistory,
			{
				role: 'assistant',
				content: errorResponse.response,
				timestamp: Date.now(),
			},
		];

		return errorResponse;
	} finally {
		homeState.isProcessing = false;
	}
}

/**
 * Map backend response to frontend HomeResponse type.
 */
function mapBackendResponse(result: Record<string, unknown>): HomeResponse {
	const type = result.type as string;

	switch (type) {
		case 'workspace':
			return {
				route: 'workspace',
				layout_id: (result.layout_id as string) || 'default',
				response: result.response as string | undefined,
				workspace_spec: result.workspace_spec as WorkspaceResponse['workspace_spec'],
			};

		case 'view':
			return {
				route: 'view',
				view_type: (result.view_type as string) || 'generic',
				view_data: (result.data as Record<string, unknown>) || {},
				response: result.response as string | undefined,
			};

		case 'action':
			return {
				route: 'action',
				action_type: (result.action_type as string) || 'unknown',
				success: (result.success as boolean) ?? true,
				response: (result.response as string) || 'Action completed.',
				data: result.data as Record<string, unknown> | undefined,
			};

		case 'hybrid':
			return {
				route: 'hybrid',
				action_type: (result.action_type as string) || 'unknown',
				success: (result.success as boolean) ?? true,
				response: (result.response as string) || 'Action completed.',
				view_type: (result.view_type as string) || 'generic',
				view_data: (result.data as Record<string, unknown>) || {},
			};

		case 'conversation':
		default:
			return {
				route: 'conversation',
				response: (result.response as string) || "I'm here to help.",
				conversation_mode: result.mode as ConversationResponse['conversation_mode'],
				auxiliary_panels: result.auxiliary_panels as AuxiliaryPanel[] | undefined,
				suggested_tools: result.suggested_tools as string[] | undefined,
			};
	}
}

/**
 * Execute a block action (e.g., complete habit, open project).
 */
export async function executeBlockAction(
	actionId: string,
	itemId?: string
): Promise<{ success: boolean; message: string }> {
	try {
		const result = await invoke<{ success: boolean; message: string }>('execute_block_action', {
			actionId,
			itemId,
			dataDir: homeState.dataDir,
		});
		return result;
	} catch (e) {
		const errorMessage = e instanceof Error ? e.message : String(e);
		console.error('Block action failed:', e);
		return { success: false, message: errorMessage };
	}
}

/**
 * Clear the current response.
 */
export function clearResponse(): void {
	homeState.response = null;
}

/**
 * Clear conversation history.
 */
export function clearConversationHistory(): void {
	homeState.conversationHistory = [];
}

/**
 * Set the data directory for providers.
 */
export function setHomeDataDir(path: string): void {
	homeState.dataDir = path;
}

/**
 * Reset to initial state.
 */
export function resetHome(): void {
	Object.assign(homeState, createInitialState());
}

/**
 * Check if the current response is a specific type.
 */
export function isViewResponse(response: HomeResponse | null): response is ViewResponse {
	return response?.route === 'view';
}

export function isActionResponse(response: HomeResponse | null): response is ActionResponse {
	return response?.route === 'action';
}

export function isConversationResponse(
	response: HomeResponse | null
): response is ConversationResponse {
	return response?.route === 'conversation';
}

export function isWorkspaceResponse(response: HomeResponse | null): response is WorkspaceResponse {
	return response?.route === 'workspace';
}

export function isHybridResponse(response: HomeResponse | null): response is HybridResponse {
	return response?.route === 'hybrid';
}
