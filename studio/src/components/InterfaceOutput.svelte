<script lang="ts">
	/**
	 * InterfaceOutput — Renders different output types from Generative Interface (RFC-075)
	 *
	 * Handles workspace, view, action, conversation, and hybrid outputs.
	 */

	import { interfaceState, composeSurface } from '../stores';
	import Toast from './ui/Toast.svelte';
	import Panel from './Panel.svelte';
	import type { InterfaceOutput } from '../stores/interface.svelte';

	interface Props {
		output: InterfaceOutput | null;
		onWorkspaceReady?: () => void;
	}

	let { output, onWorkspaceReady }: Props = $props();

	// Toast state
	let toasts = $state<Array<{ id: number; message: string; type: 'success' | 'error' | 'info' }>>([]);
	let toastId = 0;

	function showToast(message: string, type: 'success' | 'error' | 'info' = 'success') {
		const id = ++toastId;
		toasts = [...toasts, { id, message, type }];
	}

	function removeToast(id: number) {
		toasts = toasts.filter((t) => t.id !== id);
	}

	// Handle action outputs - show toast
	$effect(() => {
		if (output?.type === 'action' && output.response) {
			const type = output.success ? 'success' : 'error';
			showToast(output.response, type);
		}
	});

	// Handle workspace outputs - trigger surface composition
	$effect(() => {
		if (output?.type === 'workspace' && output.workspace_spec) {
			const spec = output.workspace_spec;
			// Compose surface with the workspace spec
			composeSurface(output.response || 'Workspace', undefined, undefined, spec.arrangement as any);
			onWorkspaceReady?.();
		}
	});

	function formatCalendarEvent(event: any): string {
		const start = new Date(event.start);
		return `${start.toLocaleDateString()} ${start.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} - ${event.title}`;
	}

	function getModeEmoji(mode: string | undefined): string {
		switch (mode) {
			case 'informational':
				return '💬';
			case 'empathetic':
				return '💜';
			case 'collaborative':
				return '🤝';
			default:
				return '💬';
		}
	}
</script>

<!-- Toast container -->
<div class="toast-container">
	{#each toasts as toast (toast.id)}
		<Toast message={toast.message} type={toast.type} onClose={() => removeToast(toast.id)} />
	{/each}
</div>

<!-- Main output rendering -->
{#if output}
	<div class="output-container">
		{#if output.type === 'conversation'}
			<div class="conversation">
				<div class="conversation-header">
					<span class="emoji">{getModeEmoji(output.data?.mode as string)}</span>
					<span class="label">Response</span>
				</div>
				<div class="conversation-content">
					{output.response}
				</div>
			</div>
		{:else if output.type === 'view'}
			<div class="view">
				<div class="view-header">
					<span class="label">{output.view_type || 'View'}</span>
				</div>
				{#if output.response}
					<div class="view-response">{output.response}</div>
				{/if}

				{#if output.data}
					{@const data = output.data as Record<string, any>}

					{#if output.view_type === 'calendar'}
						<div class="calendar-view">
							{#if data.events?.length > 0}
								<div class="event-list">
									{#each data.events.slice(0, 10) as event}
										<div class="event-item">
											<span class="event-date">
												{new Date(event.start).toLocaleDateString('en-US', {
													weekday: 'short',
													month: 'short',
													day: 'numeric',
												})}
											</span>
											<span class="event-time">
												{new Date(event.start).toLocaleTimeString([], {
													hour: '2-digit',
													minute: '2-digit',
												})}
											</span>
											<span class="event-title">{event.title}</span>
											{#if event.location}
												<span class="event-location">📍 {event.location}</span>
											{/if}
										</div>
									{/each}
								</div>
							{:else}
								<div class="empty-state">No events found</div>
							{/if}
						</div>
					{:else if output.view_type === 'list'}
						<div class="list-view">
							<div class="list-header">{data.list_name || 'List'}</div>
							{#if data.items?.length > 0}
								<div class="item-list">
									{#each data.items as item}
										<div class="list-item" class:completed={item.completed}>
											<span class="item-check">{item.completed ? '✓' : '○'}</span>
											<span class="item-text">{item.text}</span>
										</div>
									{/each}
								</div>
							{:else}
								<div class="empty-state">No items</div>
							{/if}
						</div>
					{:else if output.view_type === 'notes'}
						<div class="notes-view">
							{#if data.notes?.length > 0}
								<div class="notes-list">
									{#each data.notes as note}
										<div class="note-item">
											<div class="note-title">{note.title}</div>
											<div class="note-preview">
												{note.content?.slice(0, 150)}{note.content?.length > 150 ? '...' : ''}
											</div>
											{#if note.tags?.length > 0}
												<div class="note-tags">
													{#each note.tags as tag}
														<span class="tag">{tag}</span>
													{/each}
												</div>
											{/if}
										</div>
									{/each}
								</div>
							{:else}
								<div class="empty-state">No notes found</div>
							{/if}
						</div>
					{:else if output.view_type === 'search'}
						<div class="search-view">
							<div class="search-query">Results for "{data.query}"</div>
							{#if data.results?.length > 0}
								<div class="results-list">
									{#each data.results.slice(0, 15) as result}
										<div class="result-item result-{result.type}">
											<span class="result-icon">
												{result.type === 'note'
													? '📝'
													: result.type === 'list_item'
														? '📋'
														: '📅'}
											</span>
											<span class="result-text">
												{result.title || result.text}
												{#if result.list}
													<span class="result-meta">[{result.list}]</span>
												{/if}
											</span>
										</div>
									{/each}
								</div>
							{:else}
								<div class="empty-state">No results</div>
							{/if}
						</div>
					{/if}
				{/if}
			</div>
		{:else if output.type === 'workspace'}
			<div class="workspace-ready">
				<div class="workspace-icon">🎨</div>
				<div class="workspace-message">
					{output.response || 'Workspace ready'}
				</div>
				{#if output.workspace_spec}
					<div class="workspace-spec">
						<span class="spec-label">Primary:</span>
						<span class="spec-value">{output.workspace_spec.primary}</span>
						{#if output.workspace_spec.secondary?.length > 0}
							<span class="spec-label">Secondary:</span>
							<span class="spec-value">{output.workspace_spec.secondary.join(', ')}</span>
						{/if}
					</div>
				{/if}
			</div>
		{:else if output.type === 'hybrid'}
			<!-- Hybrid shows both action toast (handled above) and view -->
			{@const viewData = output.data?.view as Record<string, any> | undefined}
			{#if viewData}
				<div class="view">
					<div class="view-header">
						<span class="label">{viewData.view_type || 'View'}</span>
					</div>
					{#if viewData.response}
						<div class="view-response">{viewData.response}</div>
					{/if}
					<!-- Render view data similar to above -->
				</div>
			{/if}
		{/if}
	</div>
{/if}

<style>
	.toast-container {
		position: fixed;
		top: var(--space-4, 16px);
		right: var(--space-4, 16px);
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
		z-index: 1000;
	}

	.output-container {
		animation: fadeIn 0.2s ease-out;
	}

	/* Conversation */
	.conversation {
		background: var(--bg-secondary, #1e1e1e);
		border-radius: var(--radius-lg, 12px);
		padding: var(--space-4, 16px);
		border: 1px solid var(--border-subtle, #333);
	}

	.conversation-header {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		margin-bottom: var(--space-3, 12px);
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
	}

	.conversation-header .emoji {
		font-size: var(--text-lg, 18px);
	}

	.conversation-content {
		color: var(--text-primary, #fff);
		line-height: 1.6;
	}

	/* View */
	.view {
		background: var(--bg-secondary, #1e1e1e);
		border-radius: var(--radius-lg, 12px);
		padding: var(--space-4, 16px);
		border: 1px solid var(--border-subtle, #333);
	}

	.view-header {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		margin-bottom: var(--space-3, 12px);
	}

	.view-header .label {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		text-transform: capitalize;
	}

	.view-response {
		color: var(--text-primary, #fff);
		margin-bottom: var(--space-4, 16px);
		padding-bottom: var(--space-3, 12px);
		border-bottom: 1px solid var(--border-subtle, #333);
	}

	/* Calendar */
	.event-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.event-item {
		display: grid;
		grid-template-columns: auto auto 1fr auto;
		gap: var(--space-3, 12px);
		align-items: center;
		padding: var(--space-2, 8px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-sm, 4px);
	}

	.event-date {
		color: var(--gold, #ffd700);
		font-size: var(--text-sm, 14px);
		font-weight: 500;
	}

	.event-time {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
	}

	.event-title {
		color: var(--text-primary, #fff);
	}

	.event-location {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
	}

	/* List */
	.list-header {
		color: var(--gold, #ffd700);
		font-weight: 600;
		margin-bottom: var(--space-3, 12px);
		text-transform: capitalize;
	}

	.item-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-1, 4px);
	}

	.list-item {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-sm, 4px);
	}

	.list-item.completed {
		opacity: 0.5;
	}

	.item-check {
		color: var(--success, #22c55e);
		font-weight: bold;
	}

	.list-item.completed .item-check {
		color: var(--text-tertiary, #666);
	}

	.item-text {
		color: var(--text-primary, #fff);
	}

	.list-item.completed .item-text {
		text-decoration: line-through;
	}

	/* Notes */
	.notes-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
	}

	.note-item {
		padding: var(--space-3, 12px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-md, 8px);
	}

	.note-title {
		color: var(--text-primary, #fff);
		font-weight: 600;
		margin-bottom: var(--space-1, 4px);
	}

	.note-preview {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		line-height: 1.4;
	}

	.note-tags {
		display: flex;
		gap: var(--space-1, 4px);
		margin-top: var(--space-2, 8px);
	}

	.tag {
		background: var(--bg-secondary, #1e1e1e);
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
		padding: 2px 6px;
		border-radius: var(--radius-sm, 4px);
	}

	/* Search */
	.search-query {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		margin-bottom: var(--space-3, 12px);
	}

	.results-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-1, 4px);
	}

	.result-item {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-sm, 4px);
	}

	.result-icon {
		font-size: var(--text-lg, 18px);
	}

	.result-text {
		color: var(--text-primary, #fff);
	}

	.result-meta {
		color: var(--text-tertiary, #666);
		font-size: var(--text-sm, 14px);
	}

	/* Workspace */
	.workspace-ready {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-3, 12px);
		padding: var(--space-6, 24px);
		background: var(--bg-secondary, #1e1e1e);
		border-radius: var(--radius-lg, 12px);
		border: 1px solid var(--gold, #ffd700);
		text-align: center;
	}

	.workspace-icon {
		font-size: 48px;
	}

	.workspace-message {
		color: var(--text-primary, #fff);
		font-size: var(--text-lg, 18px);
	}

	.workspace-spec {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2, 8px);
		justify-content: center;
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
	}

	.spec-label {
		color: var(--text-tertiary, #666);
	}

	.spec-value {
		color: var(--gold, #ffd700);
	}

	/* Empty state */
	.empty-state {
		color: var(--text-tertiary, #666);
		text-align: center;
		padding: var(--space-4, 16px);
		font-style: italic;
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
