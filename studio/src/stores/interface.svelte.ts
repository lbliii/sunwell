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
	readonly interaction_type: InteractionType;
	readonly confidence: number;
	readonly action?: ActionSpec;
	readonly view?: ViewSpec;
	readonly workspace?: WorkspaceSpec;
	readonly response?: string;
	readonly reasoning?: string;
	readonly conversation_mode?: 'informational' | 'empathetic' | 'collaborative';
}

export interface ActionSpec {
	readonly type: string;
	readonly params: Readonly<Record<string, unknown>>;
}

export interface ViewSpec {
	readonly type: 'calendar' | 'list' | 'notes' | 'search';
	readonly focus?: Readonly<Record<string, unknown>>;
	readonly query?: string;
}

export interface WorkspaceSpec {
	readonly primary: string;
	readonly secondary: readonly string[];
	readonly contextual: readonly string[];
	readonly arrangement: string;
	readonly seed_content?: Readonly<Record<string, unknown>>;
}

export interface InterfaceOutput {
	readonly type: InteractionType;
	readonly response?: string;
	readonly data?: Readonly<Record<string, unknown>>;
	readonly action_type?: string;
	readonly success?: boolean;
	readonly view_type?: string;
	readonly workspace_spec?: WorkspaceSpec;
}

export interface Message {
	readonly role: 'user' | 'assistant';
	readonly content: string;
	readonly timestamp: number;
	readonly outputType?: InteractionType;
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

// Internal mutable state (not exported directly to prevent external mutation)
let _state = $state<InterfaceState>(createInitialState());

// Read-only accessor for state (frozen to prevent mutation)
export const interfaceState = {
	get current() { return _state.current; },
	get isAnalyzing() { return _state.isAnalyzing; },
	get lastAnalysis() { return _state.lastAnalysis; },
	get messages(): readonly Message[] { return Object.freeze([..._state.messages]); },
	get error() { return _state.error; },
	get dataDir() { return _state.dataDir; },
};

// ═══════════════════════════════════════════════════════════════
// ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Process user input through the generative interface.
 */
export async function processInput(input: string): Promise<InterfaceOutput | null> {
	_state = { ..._state, isAnalyzing: true, error: null };

	// Add user message
	_state = {
		..._state,
		messages: [
			..._state.messages,
			{
				role: 'user',
				content: input,
				timestamp: Date.now(),
			},
		],
	};

	try {
		// RFC-113: Call Python via HTTP API
		const { apiPost } = await import('$lib/socket');
		const result = await apiPost<InterfaceOutput>('/api/interface/process', {
			goal: input,
			data_dir: _state.dataDir,
		});

		_state = { ..._state, current: result };

		// Add assistant response
		if (result.response) {
			_state = {
				..._state,
				messages: [
					..._state.messages,
					{
						role: 'assistant',
						content: result.response,
						timestamp: Date.now(),
						outputType: result.type,
					},
				],
			};
		}

		return result;
	} catch (e) {
		const errorMessage = e instanceof Error ? e.message : String(e);
		_state = { ..._state, error: errorMessage };
		console.error('Interface processing failed:', e);

		// Add error message
		_state = {
			..._state,
			messages: [
				..._state.messages,
				{
					role: 'assistant',
					content: `Sorry, I encountered an error: ${errorMessage}`,
					timestamp: Date.now(),
				},
			],
		};

		return null;
	} finally {
		_state = { ..._state, isAnalyzing: false };
	}
}

/**
 * Set the data directory for providers.
 */
export function setDataDir(path: string): void {
	_state = { ..._state, dataDir: path };
}

/**
 * Clear conversation history.
 */
export function clearHistory(): void {
	_state = { ..._state, messages: [] };
}

/**
 * Reset to initial state.
 */
export function resetInterface(): void {
	_state = createInitialState();
}

/**
 * Get the last N messages.
 */
export function getRecentMessages(count: number = 10): readonly Message[] {
	return Object.freeze(_state.messages.slice(-count));
}

/**
 * Check if there's an active workspace output.
 */
export function hasActiveWorkspace(): boolean {
	return _state.current?.type === 'workspace';
}

/**
 * Get the current workspace spec if available.
 */
export function getCurrentWorkspace(): WorkspaceSpec | null {
	if (_state.current?.type === 'workspace') {
		return _state.current.workspace_spec || null;
	}
	return null;
}
