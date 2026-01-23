<!--
  HabitsBlock — Beautiful habit tracker with embedded actions (RFC-080)
  
  Shows habit cards with:
  - Completion rings (animated)
  - Streak flames
  - Quick-complete buttons (BlockAction: "complete")
  
  This is a Block, not a View — it has embedded actions.
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface Habit {
		id: string;
		name: string;
		streak: number;
		completed_today: number;
		target: number;
		is_complete: boolean;
		color?: string;
		icon?: string;
	}

	interface Props {
		data: {
			habits: Habit[];
			habit_count: number;
			complete_count: number;
			incomplete_count: number;
		};
		onAction?: (actionId: string, habitId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function handleComplete(habitId: string) {
		onAction?.('complete', habitId);
	}

	function handleSkip(habitId: string) {
		onAction?.('skip', habitId);
	}

	function getCompletionPercent(habit: Habit): number {
		return Math.min((habit.completed_today / habit.target) * 100, 100);
	}

	function getStreakEmoji(streak: number): string {
		if (streak >= 30) return '🔥';
		if (streak >= 7) return '✨';
		if (streak >= 3) return '⭐';
		return '';
	}
</script>

<div class="habits-view">
	<header class="habits-header">
		<h3 class="habits-title">Today's Habits</h3>
		<div class="habits-summary">
			<span class="complete-count">{data.complete_count}</span>
			<span class="separator">/</span>
			<span class="total-count">{data.habit_count}</span>
			<span class="label">complete</span>
		</div>
	</header>

	<div class="habits-grid">
		{#each data.habits as habit, i (habit.id)}
			<div
				class="habit-card"
				class:complete={habit.is_complete}
				in:fly={{ y: 20, delay: staggerDelay(i), duration: 300 }}
			>
				<div class="habit-ring">
					<svg viewBox="0 0 36 36" class="circular-chart" aria-hidden="true">
						<path
							class="circle-bg"
							d="M18 2.0845
								 a 15.9155 15.9155 0 0 1 0 31.831
								 a 15.9155 15.9155 0 0 1 0 -31.831"
						/>
						<path
							class="circle"
							stroke-dasharray="{getCompletionPercent(habit)}, 100"
							d="M18 2.0845
								 a 15.9155 15.9155 0 0 1 0 31.831
								 a 15.9155 15.9155 0 0 1 0 -31.831"
						/>
					</svg>
					<span class="habit-icon">{habit.icon || '○'}</span>
				</div>

				<div class="habit-info">
					<span class="habit-name">{habit.name}</span>
					<span class="habit-progress">
						{habit.completed_today}/{habit.target}
						{#if habit.streak > 0}
							<span class="streak">
								{getStreakEmoji(habit.streak)} {habit.streak}d
							</span>
						{/if}
					</span>
				</div>

				{#if !habit.is_complete}
					<button
						class="quick-complete"
						onclick={() => handleComplete(habit.id)}
						aria-label="Complete {habit.name}"
					>
						+1
					</button>
				{:else}
					<span class="check-mark" aria-label="Completed">✓</span>
				{/if}
			</div>
		{/each}
	</div>

	{#if data.habits.length === 0}
		<div class="empty-state">
			<p>No habits configured yet.</p>
		</div>
	{/if}
</div>

<style>
	.habits-view {
		display: flex;
		flex-direction: column;
		gap: var(--space-4);
	}

	.habits-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.habits-title {
		margin: 0;
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--text-primary);
	}

	.habits-summary {
		display: flex;
		align-items: baseline;
		gap: var(--space-1);
		font-size: var(--text-sm);
	}

	.complete-count {
		color: var(--gold);
		font-weight: 700;
		font-size: var(--text-xl);
	}

	.separator {
		color: var(--text-tertiary);
	}

	.total-count {
		color: var(--text-secondary);
		font-weight: 500;
	}

	.label {
		color: var(--text-tertiary);
		margin-left: var(--space-1);
	}

	.habits-grid {
		display: grid;
		grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
		gap: var(--space-3);
	}

	.habit-card {
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-3);
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--radiant-gold-10);
		border-radius: var(--radius-lg);
		transition: all 0.2s ease;
	}

	.habit-card:hover {
		background: var(--radiant-gold-5);
		border-color: var(--radiant-gold-20);
		transform: translateY(-2px);
	}

	.habit-card.complete {
		opacity: 0.7;
	}

	.habit-ring {
		position: relative;
		width: 44px;
		height: 44px;
		flex-shrink: 0;
	}

	.circular-chart {
		width: 100%;
		height: 100%;
		transform: rotate(-90deg);
	}

	.circle-bg {
		fill: none;
		stroke: var(--radiant-gold-10);
		stroke-width: 3;
	}

	.circle {
		fill: none;
		stroke: var(--gold);
		stroke-width: 3;
		stroke-linecap: round;
		transition: stroke-dasharray 0.6s ease;
	}

	.habit-icon {
		position: absolute;
		top: 50%;
		left: 50%;
		transform: translate(-50%, -50%);
		font-size: var(--text-lg);
	}

	.habit-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 0;
	}

	.habit-name {
		color: var(--text-primary);
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.habit-progress {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		color: var(--text-tertiary);
		font-size: var(--text-sm);
	}

	.streak {
		color: var(--gold);
		font-weight: 500;
	}

	.quick-complete {
		padding: var(--space-2) var(--space-3);
		background: var(--radiant-gold-10);
		border: 1px solid var(--radiant-gold-30);
		border-radius: var(--radius-md);
		color: var(--gold);
		font-weight: 600;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.quick-complete:hover {
		background: var(--radiant-gold-20);
		transform: scale(1.05);
	}

	.quick-complete:focus-visible {
		outline: 2px solid var(--gold);
		outline-offset: 2px;
	}

	.check-mark {
		color: var(--success);
		font-size: var(--text-xl);
		font-weight: bold;
	}

	.empty-state {
		text-align: center;
		padding: var(--space-6);
		color: var(--text-tertiary);
	}
</style>
