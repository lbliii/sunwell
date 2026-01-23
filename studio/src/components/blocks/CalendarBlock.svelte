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
		gap: var(--space-4);
	}

	.calendar-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.calendar-title {
		margin: 0;
		font-size: var(--text-lg);
		font-weight: 600;
		color: var(--text-primary);
	}

	.add-event-btn {
		display: flex;
		align-items: center;
		gap: var(--space-1);
		padding: var(--space-1) var(--space-2);
		background: var(--radiant-gold-10);
		border: 1px solid var(--radiant-gold-20);
		border-radius: var(--radius-sm);
		color: var(--gold);
		font-size: var(--text-sm);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.add-event-btn:hover {
		background: var(--radiant-gold-20);
	}

	.add-event-btn:focus-visible {
		outline: 2px solid var(--gold);
		outline-offset: 2px;
	}

	.event-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.event-item {
		display: grid;
		grid-template-columns: auto 1fr auto;
		gap: var(--space-3);
		align-items: center;
		padding: var(--space-3);
		background: var(--bg-primary);
		border-radius: var(--radius-md);
		border-left: 3px solid transparent;
		transition: all 0.2s ease;
	}

	.event-item:hover {
		background: var(--radiant-gold-5);
	}

	.event-item.today {
		border-left-color: var(--gold);
	}

	.event-time-block {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		min-width: 70px;
	}

	.event-time {
		color: var(--gold);
		font-size: var(--text-sm);
		font-weight: 600;
	}

	.event-time.all-day {
		font-size: var(--text-xs);
	}

	.event-date {
		color: var(--text-tertiary);
		font-size: var(--text-xs);
	}

	.event-details {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		min-width: 0;
	}

	.event-title {
		color: var(--text-primary);
		font-weight: 500;
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.event-location {
		color: var(--text-tertiary);
		font-size: var(--text-xs);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.event-indicator {
		width: 8px;
		height: 8px;
		border-radius: 50%;
		background: var(--text-tertiary);
		opacity: 0.5;
	}

	.event-indicator.today {
		background: var(--gold);
		opacity: 1;
		box-shadow: 0 0 8px rgba(var(--radiant-gold-rgb), 0.5);
	}

	.empty-state {
		text-align: center;
		padding: var(--space-6);
		color: var(--text-tertiary);
	}
</style>
