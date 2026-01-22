<!--
  CalendarBlock — Today's events with quick actions (RFC-080)
  
  Shows upcoming events in a timeline format with:
  - Event times and titles
  - Location info
  - Quick add action
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface CalendarEvent {
		id: string;
		title: string;
		start: string;
		end?: string;
		location?: string;
		all_day?: boolean;
	}

	interface Props {
		data: {
			events: CalendarEvent[];
			start?: string;
			end?: string;
		};
		onAction?: (actionId: string, eventId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function formatTime(dateString: string): string {
		const date = new Date(dateString);
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	function formatDate(dateString: string): string {
		const date = new Date(dateString);
		return date.toLocaleDateString('en-US', {
			weekday: 'short',
			month: 'short',
			day: 'numeric',
		});
	}

	function isToday(dateString: string): boolean {
		const date = new Date(dateString);
		const today = new Date();
		return date.toDateString() === today.toDateString();
	}

	function handleAddEvent() {
		onAction?.('add_event');
	}

	function handleRSVP(eventId: string) {
		onAction?.('rsvp', eventId);
	}
</script>

<div class="calendar-view">
	<header class="calendar-header">
		<h3 class="calendar-title">Upcoming Events</h3>
		<button class="add-event-btn" onclick={handleAddEvent} aria-label="Add event">
			<span aria-hidden="true">📅</span> + Event
		</button>
	</header>

	{#if data.events.length > 0}
		<div class="event-list">
			{#each data.events.slice(0, 10) as event, i (event.id)}
				<div
					class="event-item"
					class:today={isToday(event.start)}
					in:fly={{ y: 15, delay: staggerDelay(i), duration: 250 }}
				>
					<div class="event-time-block">
						{#if event.all_day}
							<span class="event-time all-day">All day</span>
						{:else}
							<span class="event-time">{formatTime(event.start)}</span>
						{/if}
						<span class="event-date">{formatDate(event.start)}</span>
					</div>
					
					<div class="event-details">
						<span class="event-title">{event.title}</span>
						{#if event.location}
							<span class="event-location">
								<span aria-hidden="true">📍</span> {event.location}
							</span>
						{/if}
					</div>

					<div class="event-indicator" class:today={isToday(event.start)}></div>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-state">
			<p>No upcoming events</p>
		</div>
	{/if}
</div>

<style>
	.calendar-view {
		display: flex;
		flex-direction: column;
		gap: var(--space-4, 16px);
	}

	.calendar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.calendar-title {
		margin: 0;
		font-size: var(--text-lg, 18px);
		font-weight: 600;
		color: var(--text-primary, #fff);
	}

	.add-event-btn {
		display: flex;
		align-items: center;
		gap: var(--space-1, 4px);
		padding: var(--space-1, 4px) var(--space-2, 8px);
		background: rgba(255, 215, 0, 0.1);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-sm, 4px);
		color: var(--gold, #ffd700);
		font-size: var(--text-sm, 14px);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.add-event-btn:hover {
		background: rgba(255, 215, 0, 0.2);
	}

	.add-event-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}

	.event-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.event-item {
		display: grid;
		grid-template-columns: auto 1fr auto;
		gap: var(--space-3, 12px);
		align-items: center;
		padding: var(--space-3, 12px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-md, 8px);
		border-left: 3px solid transparent;
		transition: all 0.2s ease;
	}

	.event-item:hover {
		background: rgba(255, 215, 0, 0.05);
	}

	.event-item.today {
		border-left-color: var(--gold, #ffd700);
	}

	.event-time-block {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		min-width: 70px;
	}

	.event-time {
		color: var(--gold, #ffd700);
		font-size: var(--text-sm, 14px);
		font-weight: 600;
	}

	.event-time.all-day {
		font-size: var(--text-xs, 12px);
	}

	.event-date {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
	}

	.event-details {
		display: flex;
		flex-direction: column;
		gap: var(--space-1, 4px);
		min-width: 0;
	}

	.event-title {
		color: var(--text-primary, #fff);
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.event-location {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.event-indicator {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-tertiary, #666);
		opacity: 0.5;
	}

	.event-indicator.today {
		background: var(--gold, #ffd700);
		opacity: 1;
		box-shadow: 0 0 8px rgba(255, 215, 0, 0.5);
	}

	.empty-state {
		text-align: center;
		padding: var(--space-6, 24px);
		color: var(--text-tertiary, #666);
	}
</style>
