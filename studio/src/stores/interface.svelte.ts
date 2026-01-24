/**
 * Interface Store — Generative Interface state management (RFC-075)
 *
 * Manages the state for the LLM-driven interaction routing system.
 */

// Dynamic import used in analyzeIntent() for code splitting

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type InteractionType = 'workspace' | 'view' | 'action' | 'conversation' | 'hybrid';

export interface IntentAnalysis {
	interaction_type: InteractionType;
	confidence: number;
	action?: ActionSpec;
	view?: ViewSpec;
	workspace?: WorkspaceSpec;
	response?: string;
	reasoning?: string;
	conversation_mode?: 'informational' | 'empathetic' | 'collaborative';
}

export interface ActionSpec {
	type: string;
	params: Record<string, unknown>;
}

export interface ViewSpec {
	type: 'calendar' | 'list' | 'notes' | 'search';
	focus?: Record<string, unknown>;
	query?: string;
}

export interface WorkspaceSpec {
	primary: string;
	secondary: string[];
	contextual: string[];
	arrangement: string;
	seed_content?: Record<string, unknown>;
}

export interface InterfaceOutput {
	type: InteractionType;
	response?: string;
	data?: Record<string, unknown>;
	action_type?: string;
	success?: boolean;
	view_type?: string;
	workspace_spec?: WorkspaceSpec;
}

export interface Message {
	role: 'user' | 'assistant';
	content: string;
	timestamp: number;
	outputType?: InteractionType;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface InterfaceState {
	/** Current output being displayed */
	current: InterfaceOutput | null;

	/** Is analysis in progress */
	isAnalyzing: boolean;

	/** Last analysis result (for debugging) */
	lastAnalysis: IntentAnalysis | null;

	/** Conversation history */
	messages: Message[];

	/** Error state */
	error: string | null;

	/** Data directory path */
	dataDir: string | null;
}

function createInitialState(): InterfaceState {
	return {
		current: null,
		isAnalyzing: false,
		lastAnalysis: null,
		messages: [],
		error: null,
		dataDir: null,
	};
}

export let interfaceState = $state<InterfaceState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Process user input through the generative interface.
 */
export async function processInput(input: string): Promise<InterfaceOutput | null> {
	interfaceState.isAnalyzing = true;
	interfaceState.error = null;

	// Add user message
	interfaceState.messages = [
		...interfaceState.messages,
		{
			role: 'user',
			content: input,
			timestamp: Date.now(),
		},
	];

	try {
		// RFC-113: Call Python via HTTP API
		const { apiPost } = await import('$lib/socket');
		const result = await apiPost<InterfaceOutput>('/api/interface/process', {
			goal: input,
			data_dir: interfaceState.dataDir,
		});

		interfaceState.current = result;

		// Add assistant response
		if (result.response) {
			interfaceState.messages = [
				...interfaceState.messages,
				{
					role: 'assistant',
					content: result.response,
					timestamp: Date.now(),
					outputType: result.type,
				},
			];
		}

		return result;
	} catch (e) {
		const errorMessage = e instanceof Error ? e.message : String(e);
		interfaceState.error = errorMessage;
		console.error('Interface processing failed:', e);

		// Add error message
		interfaceState.messages = [
			...interfaceState.messages,
			{
				role: 'assistant',
				content: `Sorry, I encountered an error: ${errorMessage}`,
				timestamp: Date.now(),
			},
		];

		return null;
	} finally {
		interfaceState.isAnalyzing = false;
	}
}

/**
 * Set the data directory for providers.
 */
export function setDataDir(path: string): void {
	interfaceState.dataDir = path;
}

/**
 * Clear conversation history.
 */
export function clearHistory(): void {
	interfaceState.messages = [];
}

/**
 * Reset to initial state.
 */
export function resetInterface(): void {
	Object.assign(interfaceState, createInitialState());
}

/**
 * Get the last N messages.
 */
export function getRecentMessages(count: number = 10): Message[] {
	return interfaceState.messages.slice(-count);
}

/**
 * Check if there's an active workspace output.
 */
export function hasActiveWorkspace(): boolean {
	return interfaceState.current?.type === 'workspace';
}

/**
 * Get the current workspace spec if available.
 */
export function getCurrentWorkspace(): WorkspaceSpec | null {
	if (interfaceState.current?.type === 'workspace') {
		return interfaceState.current.workspace_spec || null;
	}
	return null;
}
