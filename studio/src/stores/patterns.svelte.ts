/**
 * Pattern Store — Predictive Intelligence (RFC-082 Phase 6)
 *
 * Tracks user patterns to enable proactive suggestions:
 * - Time-of-day activity patterns
 * - Project affinity scoring
 * - Layout preferences per task type
 * - Frequent state transitions
 */

// Browser detection (works in Tauri/SvelteKit)
const browser = typeof window !== 'undefined';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type ActivityType =
	| 'deep_work'
	| 'email_triage'
	| 'meetings'
	| 'admin'
	| 'review'
	| 'planning'
	| 'coding'
	| 'writing'
	| 'research'
	| 'idle';

export type HourRange = `${number}-${number}`; // e.g., "9-12"

export interface LayoutConfig {
	primary: string;
	secondary: string[];
}

export interface StateTransition {
	from: string;
	to: string;
	count: number;
	lastOccurred: number;
}

export interface UserPattern {
	/** Activity patterns by time of day */
	timeOfDay: Record<HourRange, ActivityType>;

	/** Project affinity scores (0-1) */
	projectAffinities: Record<string, number>;

	/** Layout preferences per task type */
	layoutPreferences: Record<ActivityType, LayoutConfig>;

	/** Frequent state transitions */
	frequentTransitions: StateTransition[];

	/** Last updated timestamp */
	lastUpdated: number;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

const STORAGE_KEY = 'sunwell_user_patterns';

interface PatternState {
	/** Learned user patterns */
	patterns: UserPattern;

	/** Activity tracking for pattern learning */
	activityLog: Array<{
		type: ActivityType;
		projectId?: string;
		hour: number;
		timestamp: number;
	}>;

	/** Current activity (for tracking) */
	currentActivity: ActivityType | null;

	/** Current project (for tracking) */
	currentProject: string | null;
}

function createDefaultPatterns(): UserPattern {
	return {
		timeOfDay: {
			'6-9': 'email_triage',
			'9-12': 'deep_work',
			'12-13': 'admin',
			'13-17': 'coding',
			'17-19': 'review',
		},
		projectAffinities: {},
		layoutPreferences: {
			deep_work: { primary: 'CodeEditor', secondary: ['Terminal', 'FileTree'] },
			coding: { primary: 'CodeEditor', secondary: ['Terminal', 'FileTree'] },
			writing: { primary: 'ProseEditor', secondary: ['Outline', 'Notes'] },
			research: { primary: 'Browser', secondary: ['Notes', 'Search'] },
			email_triage: { primary: 'Email', secondary: ['Calendar'] },
			meetings: { primary: 'Calendar', secondary: ['Notes'] },
			admin: { primary: 'TaskList', secondary: ['Calendar'] },
			review: { primary: 'DiffView', secondary: ['Terminal', 'Notes'] },
			planning: { primary: 'Whiteboard', secondary: ['Notes', 'Calendar'] },
			idle: { primary: 'Home', secondary: [] },
		},
		frequentTransitions: [],
		lastUpdated: Date.now(),
	};
}

function createInitialState(): PatternState {
	return {
		patterns: createDefaultPatterns(),
		activityLog: [],
		currentActivity: null,
		currentProject: null,
	};
}

export let patternState = $state<PatternState>(createInitialState());

// Load from localStorage on init
if (browser) {
	const stored = localStorage.getItem(STORAGE_KEY);
	if (stored) {
		try {
			const parsed = JSON.parse(stored);
			patternState.patterns = { ...createDefaultPatterns(), ...parsed.patterns };
			patternState.activityLog = parsed.activityLog ?? [];
		} catch (e) {
			console.error('Failed to load patterns from localStorage:', e);
		}
	}
}

// ═══════════════════════════════════════════════════════════════
// PERSISTENCE
// ═══════════════════════════════════════════════════════════════

function persistPatterns(): void {
	if (!browser) return;

	localStorage.setItem(
		STORAGE_KEY,
		JSON.stringify({
			patterns: patternState.patterns,
			activityLog: patternState.activityLog.slice(-200), // Keep last 200
		})
	);
}

// ═══════════════════════════════════════════════════════════════
// TRACKING ACTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Record current activity for pattern learning.
 */
export function trackActivity(activity: ActivityType, projectId?: string): void {
	const now = new Date();
	const hour = now.getHours();

	// Track state transition
	if (patternState.currentActivity && patternState.currentActivity !== activity) {
		recordTransition(patternState.currentActivity, activity);
	}

	// Update current state
	patternState.currentActivity = activity;
	patternState.currentProject = projectId ?? null;

	// Add to activity log
	patternState.activityLog = [
		...patternState.activityLog.slice(-199),
		{
			type: activity,
			projectId,
			hour,
			timestamp: Date.now(),
		},
	];

	// Update project affinity
	if (projectId) {
		const currentAffinity = patternState.patterns.projectAffinities[projectId] ?? 0.5;
		// Exponential moving average with recency bias
		patternState.patterns.projectAffinities[projectId] = Math.min(
			1.0,
			currentAffinity * 0.9 + 0.1
		);
	}

	// Update time-of-day patterns
	const hourRange = getHourRange(hour);
	const existingActivity = patternState.patterns.timeOfDay[hourRange];

	// Only update if we have enough data or no existing pattern
	if (!existingActivity || shouldUpdateTimePattern(hourRange, activity)) {
		patternState.patterns.timeOfDay[hourRange] = activity;
	}

	patternState.patterns.lastUpdated = Date.now();
	persistPatterns();
}

/**
 * Record a state transition for pattern learning.
 */
function recordTransition(from: string, to: string): void {
	const existing = patternState.patterns.frequentTransitions.find(
		(t) => t.from === from && t.to === to
	);

	if (existing) {
		existing.count += 1;
		existing.lastOccurred = Date.now();
	} else {
		patternState.patterns.frequentTransitions.push({
			from,
			to,
			count: 1,
			lastOccurred: Date.now(),
		});
	}

	// Keep only top 20 most frequent transitions
	patternState.patterns.frequentTransitions.sort((a, b) => b.count - a.count);
	patternState.patterns.frequentTransitions = patternState.patterns.frequentTransitions.slice(
		0,
		20
	);
}

/**
 * Update project affinity (e.g., when user opens a project).
 */
export function boostProjectAffinity(projectId: string, amount: number = 0.1): void {
	const current = patternState.patterns.projectAffinities[projectId] ?? 0.5;
	patternState.patterns.projectAffinities[projectId] = Math.min(1.0, current + amount);

	// Decay other projects slightly
	for (const [id, affinity] of Object.entries(patternState.patterns.projectAffinities)) {
		if (id !== projectId) {
			patternState.patterns.projectAffinities[id] = Math.max(0, affinity - 0.02);
		}
	}

	patternState.patterns.lastUpdated = Date.now();
	persistPatterns();
}

/**
 * Update layout preference for a task type.
 */
export function setLayoutPreference(taskType: ActivityType, layout: LayoutConfig): void {
	patternState.patterns.layoutPreferences[taskType] = layout;
	patternState.patterns.lastUpdated = Date.now();
	persistPatterns();
}

// ═══════════════════════════════════════════════════════════════
// PREDICTION FUNCTIONS
// ═══════════════════════════════════════════════════════════════

/**
 * Predict likely activity for current time.
 */
export function predictActivity(): ActivityType {
	const hour = new Date().getHours();
	const hourRange = getHourRange(hour);
	return patternState.patterns.timeOfDay[hourRange] ?? 'idle';
}

/**
 * Get top projects by affinity.
 */
export function getTopProjects(count: number = 5): Array<{ id: string; affinity: number }> {
	return Object.entries(patternState.patterns.projectAffinities)
		.map(([id, affinity]) => ({ id, affinity }))
		.sort((a, b) => b.affinity - a.affinity)
		.slice(0, count);
}

/**
 * Get recommended layout for an activity.
 */
export function getRecommendedLayout(activity: ActivityType): LayoutConfig {
	return (
		patternState.patterns.layoutPreferences[activity] ?? {
			primary: 'Home',
			secondary: [],
		}
	);
}

/**
 * Predict next activity based on current state and transitions.
 */
export function predictNextActivity(): ActivityType | null {
	if (!patternState.currentActivity) return null;

	// Find most frequent transition from current activity
	const transitions = patternState.patterns.frequentTransitions.filter(
		(t) => t.from === patternState.currentActivity
	);

	if (transitions.length === 0) return null;

	// Return the most frequent next state
	return transitions[0].to as ActivityType;
}

/**
 * Check if a transition is common.
 */
export function isCommonTransition(from: string, to: string): boolean {
	const transition = patternState.patterns.frequentTransitions.find(
		(t) => t.from === from && t.to === to
	);
	return (transition?.count ?? 0) >= 3;
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

function getHourRange(hour: number): HourRange {
	if (hour >= 6 && hour < 9) return '6-9';
	if (hour >= 9 && hour < 12) return '9-12';
	if (hour >= 12 && hour < 13) return '12-13';
	if (hour >= 13 && hour < 17) return '13-17';
	if (hour >= 17 && hour < 19) return '17-19';
	if (hour >= 19 && hour < 22) return '19-22';
	return '22-6';
}

function shouldUpdateTimePattern(hourRange: HourRange, activity: ActivityType): boolean {
	// Count occurrences of this activity in this time range
	const recentLogs = patternState.activityLog.filter((log) => {
		const logRange = getHourRange(log.hour);
		return logRange === hourRange && log.type === activity;
	});

	// Update if we have at least 3 occurrences
	return recentLogs.length >= 3;
}

/**
 * Reset all patterns to defaults.
 */
export function resetPatterns(): void {
	Object.assign(patternState, createInitialState());
	if (browser) {
		localStorage.removeItem(STORAGE_KEY);
	}
}

/**
 * Get pattern statistics for debugging.
 */
export function getPatternStats(): {
	activityLogSize: number;
	projectCount: number;
	transitionCount: number;
	lastUpdated: Date;
} {
	return {
		activityLogSize: patternState.activityLog.length,
		projectCount: Object.keys(patternState.patterns.projectAffinities).length,
		transitionCount: patternState.patterns.frequentTransitions.length,
		lastUpdated: new Date(patternState.patterns.lastUpdated),
	};
}
