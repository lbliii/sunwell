/**
 * Suggestions Store — Ambient Suggestion Engine (RFC-082 Phase 6)
 *
 * Generates proactive suggestions based on:
 * - User patterns (time-of-day, project affinity)
 * - Current context (what's open, what was recently done)
 * - Common transitions (what users typically do next)
 */

import {
	predictActivity,
	getTopProjects,
	getRecommendedLayout,
	predictNextActivity,
	isCommonTransition,
	type ActivityType,
} from './patterns.svelte';

// ═══════════════════════════════════════════════════════════════
// TYPES
// ═══════════════════════════════════════════════════════════════

export type SuggestionType = 'project' | 'layout' | 'activity' | 'tool' | 'transition';

export interface Suggestion {
	id: string;
	type: SuggestionType;
	text: string;
	subtext?: string;
	icon: string;
	confidence: number;
	action: () => void | Promise<void>;
	dismiss: () => void;
	metadata?: Record<string, unknown>;
}

export interface SuggestionContext {
	currentPage: string;
	currentProject?: string;
	currentActivity?: ActivityType;
	recentActions: string[];
	timeOfDay: number;
}

// ═══════════════════════════════════════════════════════════════
// STATE
// ═══════════════════════════════════════════════════════════════

interface SuggestionState {
	/** Current suggestions (max 3) */
	suggestions: Suggestion[];

	/** Dismissed suggestion IDs (don't re-show) */
	dismissed: Set<string>;

	/** Whether suggestions are enabled */
	enabled: boolean;

	/** Last context used for generation */
	lastContext: SuggestionContext | null;

	/** Cooldown period after dismissal (ms) */
	cooldownUntil: number;
}

function createInitialState(): SuggestionState {
	return {
		suggestions: [],
		dismissed: new Set(),
		enabled: true,
		lastContext: null,
		cooldownUntil: 0,
	};
}

export let suggestionState = $state<SuggestionState>(createInitialState());

// ═══════════════════════════════════════════════════════════════
// SUGGESTION GENERATORS
// ═══════════════════════════════════════════════════════════════

/**
 * Generate project suggestions based on affinity and time.
 */
function generateProjectSuggestions(context: SuggestionContext): Suggestion[] {
	const topProjects = getTopProjects(3);
	const suggestions: Suggestion[] = [];

	for (const project of topProjects) {
		// Skip current project
		if (project.id === context.currentProject) continue;

		// Skip low-affinity projects
		if (project.affinity < 0.4) continue;

		const suggestion: Suggestion = {
			id: `project-${project.id}`,
			type: 'project',
			text: `Continue working on ${project.id}?`,
			subtext: `You've been active on this project recently`,
			icon: '📁',
			confidence: project.affinity,
			action: () => {
				// This will be connected to navigation
				console.log(`Opening project: ${project.id}`);
			},
			dismiss: () => dismissSuggestion(`project-${project.id}`),
			metadata: { projectId: project.id, affinity: project.affinity },
		};

		suggestions.push(suggestion);
	}

	return suggestions;
}

/**
 * Generate layout suggestions based on detected activity.
 */
function generateLayoutSuggestions(context: SuggestionContext): Suggestion[] {
	const predictedActivity = predictActivity();
	const currentActivity = context.currentActivity ?? 'idle';

	// Only suggest if predicted differs from current
	if (predictedActivity === currentActivity) return [];

	const layout = getRecommendedLayout(predictedActivity);

	return [
		{
			id: `layout-${predictedActivity}`,
			type: 'layout',
			text: `This looks like ${formatActivity(predictedActivity)}`,
			subtext: `Want me to open ${layout.primary}?`,
			icon: getActivityIcon(predictedActivity),
			confidence: 0.7,
			action: () => {
				console.log(`Applying layout for: ${predictedActivity}`);
			},
			dismiss: () => dismissSuggestion(`layout-${predictedActivity}`),
			metadata: { activity: predictedActivity, layout },
		},
	];
}

/**
 * Generate tool suggestions based on common patterns.
 */
function generateToolSuggestions(context: SuggestionContext): Suggestion[] {
	const suggestions: Suggestion[] = [];

	// Check if user typically has certain tools open
	const activity = context.currentActivity ?? predictActivity();
	const layout = getRecommendedLayout(activity);

	// Suggest secondary panels that aren't open
	for (const panel of layout.secondary.slice(0, 2)) {
		const suggestionId = `tool-${panel}`;

		if (suggestionState.dismissed.has(suggestionId)) continue;

		suggestions.push({
			id: suggestionId,
			type: 'tool',
			text: `Open ${panel}?`,
			subtext: `You usually have this open when ${formatActivity(activity)}`,
			icon: '🔧',
			confidence: 0.6,
			action: () => {
				console.log(`Opening tool: ${panel}`);
			},
			dismiss: () => dismissSuggestion(suggestionId),
			metadata: { tool: panel },
		});
	}

	return suggestions;
}

/**
 * Generate transition suggestions based on common patterns.
 */
function generateTransitionSuggestions(context: SuggestionContext): Suggestion[] {
	if (!context.currentActivity) return [];

	const nextActivity = predictNextActivity();
	if (!nextActivity) return [];

	// Only suggest if this is a common transition
	if (!isCommonTransition(context.currentActivity, nextActivity)) return [];

	const suggestionId = `transition-${context.currentActivity}-${nextActivity}`;

	if (suggestionState.dismissed.has(suggestionId)) return [];

	return [
		{
			id: suggestionId,
			type: 'transition',
			text: `Ready to switch to ${formatActivity(nextActivity)}?`,
			subtext: `You often do this after ${formatActivity(context.currentActivity)}`,
			icon: '➡️',
			confidence: 0.65,
			action: () => {
				console.log(`Transitioning to: ${nextActivity}`);
			},
			dismiss: () => dismissSuggestion(suggestionId),
			metadata: { from: context.currentActivity, to: nextActivity },
		},
	];
}

// ═══════════════════════════════════════════════════════════════
// MAIN API
// ═══════════════════════════════════════════════════════════════

/**
 * Generate suggestions based on current context.
 */
export function generateSuggestions(context: SuggestionContext): void {
	if (!suggestionState.enabled) return;

	// Respect cooldown
	if (Date.now() < suggestionState.cooldownUntil) return;

	suggestionState.lastContext = context;

	// Generate all potential suggestions
	const allSuggestions = [
		...generateProjectSuggestions(context),
		...generateLayoutSuggestions(context),
		...generateToolSuggestions(context),
		...generateTransitionSuggestions(context),
	];

	// Filter out dismissed suggestions
	const filtered = allSuggestions.filter((s) => !suggestionState.dismissed.has(s.id));

	// Sort by confidence and take top 3
	const sorted = filtered.sort((a, b) => b.confidence - a.confidence);
	suggestionState.suggestions = sorted.slice(0, 3);
}

/**
 * Dismiss a suggestion (don't show again this session).
 */
export function dismissSuggestion(id: string): void {
	suggestionState.dismissed.add(id);
	suggestionState.suggestions = suggestionState.suggestions.filter((s) => s.id !== id);

	// Apply cooldown (30 seconds)
	suggestionState.cooldownUntil = Date.now() + 30000;
}

/**
 * Dismiss all current suggestions.
 */
export function dismissAll(): void {
	const suggestions = suggestionState.suggestions;
	if (Array.isArray(suggestions)) {
		for (const suggestion of suggestions) {
			suggestionState.dismissed.add(suggestion.id);
		}
	}
	suggestionState.suggestions = [];

	// Apply longer cooldown (2 minutes)
	suggestionState.cooldownUntil = Date.now() + 120000;
}

/**
 * Accept a suggestion (execute its action).
 */
export async function acceptSuggestion(id: string): Promise<void> {
	const suggestion = suggestionState.suggestions.find((s) => s.id === id);
	if (!suggestion) return;

	// Execute the action
	await suggestion.action();

	// Remove from suggestions
	suggestionState.suggestions = suggestionState.suggestions.filter((s) => s.id !== id);
}

/**
 * Enable/disable suggestions.
 */
export function setSuggestionsEnabled(enabled: boolean): void {
	suggestionState.enabled = enabled;
	if (!enabled) {
		suggestionState.suggestions = [];
	}
}

/**
 * Clear dismissed suggestions (allow re-suggestion).
 */
export function clearDismissed(): void {
	suggestionState.dismissed.clear();
	suggestionState.cooldownUntil = 0;
}

/**
 * Get current top suggestion (if any).
 */
export function getTopSuggestion(): Suggestion | null {
	return suggestionState.suggestions[0] ?? null;
}

// ═══════════════════════════════════════════════════════════════
// UTILITIES
// ═══════════════════════════════════════════════════════════════

function formatActivity(activity: ActivityType): string {
	const labels: Record<ActivityType, string> = {
		deep_work: 'deep work',
		email_triage: 'email',
		meetings: 'meetings',
		admin: 'admin work',
		review: 'code review',
		planning: 'planning',
		coding: 'coding',
		writing: 'writing',
		research: 'research',
		idle: 'browsing',
	};
	return labels[activity] ?? activity;
}

function getActivityIcon(activity: ActivityType): string {
	const icons: Record<ActivityType, string> = {
		deep_work: '🎯',
		email_triage: '📧',
		meetings: '📅',
		admin: '📋',
		review: '👀',
		planning: '📐',
		coding: '💻',
		writing: '✍️',
		research: '🔍',
		idle: '🏠',
	};
	return icons[activity] ?? '💡';
}
