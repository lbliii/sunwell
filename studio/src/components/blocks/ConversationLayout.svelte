<!--
  ConversationLayout — Fluid conversation UI with morphing input (RFC-080+, RFC-082)
  
  Apple-style fluid interface where:
  - Input flows to bottom of conversation (not a separate "Ask more" button)
  - Auxiliary panels appear alongside with spring-staggered animations
  - Suggested tools integrate with input
  - Everything morphs smoothly between states using spring physics
-->
<script lang="ts">
	import { fly, slide, scale } from 'svelte/transition';
	import { backOut, cubicOut } from 'svelte/easing';
	import FluidInput from '../FluidInput.svelte';
	import { staggerDelay } from '../../lib/tetris';

	interface AuxiliaryPanel {
		panel_type: string;
		title?: string;
		data?: Record<string, unknown>;
	}

	interface Message {
		role: 'user' | 'assistant';
		content: string;
	}

	interface Props {
		messages?: Message[];
		currentResponse?: string;
		mode?: 'informational' | 'empathetic' | 'collaborative';
		auxiliaryPanels?: AuxiliaryPanel[];
		suggestedTools?: string[];
		loading?: boolean;
		onSubmit?: (value: string) => void;
		onAction?: (actionId: string, data?: unknown) => void;
		onDismiss?: () => void;
	}

	let {
		messages = [],
		currentResponse = '',
		mode = 'informational',
		auxiliaryPanels = [],
		suggestedTools = [],
		loading = false,
		onSubmit,
		onAction,
		onDismiss,
	}: Props = $props();

	let inputValue = $state('');

	// Determine layout: side-by-side if panels exist, stacked otherwise
	let hasPanels = $derived(auxiliaryPanels.length > 0);
	let hasTools = $derived(suggestedTools.length > 0);
	let hasMessages = $derived(messages.length > 0 || currentResponse);

	function getModeEmoji(m: string): string {
		switch (m) {
			case 'informational': return '💬';
			case 'empathetic': return '💜';
			case 'collaborative': return '🤝';
			default: return '💬';
		}
	}

	function getPanelIcon(panelType: string): string {
		switch (panelType) {
			case 'calendar': return '📅';
			case 'tasks': return '✓';
			case 'image': return '🖼️';
			case 'chart': return '📊';
			case 'upload': return '📎';
			case 'table': return '📋';
			case 'code': return '🐍';
			case 'editor': return '📝';
			case 'document': return '📄';
			case 'products': return '💻';
			case 'links': return '🔗';
			case 'web': return '🌐';
			case 'calculator': return '🧮';
			case 'map': return '🗺️';
			default: return '📄';
		}
	}

	function getToolIcon(tool: string): string {
		switch (tool) {
			case 'upload': return '📎';
			case 'camera': return '📷';
			case 'voice': return '🎤';
			case 'draw': return '✏️';
			default: return '🔧';
		}
	}

	function handleSubmit(value: string) {
		inputValue = '';
		onSubmit?.(value);
	}

	function handlePanelAction(panelType: string, action: string) {
		onAction?.('panel_action', { panelType, action });
	}
</script>

<div class="conversation-layout" class:has-panels={hasPanels}>
	<!-- Main conversation area -->
	<div class="conversation-main">
		<!-- Header with dismiss -->
		<header class="conversation-header">
			<div class="mode-indicator">
				<span class="mode-emoji">{getModeEmoji(mode)}</span>
				<span class="mode-label">Conversation</span>
			</div>
			{#if onDismiss}
				<button class="dismiss-btn" onclick={onDismiss} aria-label="Close conversation">✕</button>
			{/if}
		</header>

		<!-- Message thread with staggered spring animations -->
		<div class="messages-container">
			{#each messages as msg, i (msg.content)}
				<div
					class="message message-{msg.role}"
					transition:fly={{
						y: 16,
						duration: 350,
						delay: staggerDelay(i, 40),
						easing: backOut,
					}}
				>
					<span class="message-role" transition:scale={{ delay: staggerDelay(i, 40) + 50, duration: 200 }}>
						{msg.role === 'user' ? '👤' : '✨'}
					</span>
					<p class="message-content">{msg.content}</p>
				</div>
			{/each}

			{#if currentResponse}
				<div
					class="message message-assistant current"
					transition:fly={{
						y: 16,
						duration: 350,
						easing: backOut,
					}}
				>
					<span class="message-role" transition:scale={{ delay: 50, duration: 200 }}>✨</span>
					<p class="message-content">{currentResponse}</p>
				</div>
			{/if}

			{#if loading}
				<div class="message message-assistant thinking" transition:fly={{ y: 10, duration: 200 }}>
					<span class="message-role">✨</span>
					<span class="thinking-dots">Thinking<span class="dots">...</span></span>
				</div>
			{/if}
		</div>

		<!-- Suggested tools (inline with input area) -->
		{#if hasTools}
			<div class="tool-suggestions" transition:slide={{ duration: 200 }}>
				{#each suggestedTools as tool}
					<button
						class="tool-chip"
						onclick={() => onAction?.('use_tool', { tool })}
						aria-label={tool}
					>
						<span>{getToolIcon(tool)}</span>
					</button>
				{/each}
			</div>
		{/if}

		<!-- Fluid input at bottom -->
		<div class="input-area">
			<FluidInput
				bind:value={inputValue}
				mode="chat"
				{loading}
				onsubmit={handleSubmit}
			/>
		</div>
	</div>

	<!-- Auxiliary panels area with spring stagger -->
	{#if hasPanels}
		<aside class="auxiliary-panels" transition:fly={{ x: 80, duration: 350, easing: cubicOut }}>
			{#each auxiliaryPanels as panel, i (i)}
				<div
					class="panel panel-{panel.panel_type}"
					transition:fly={{
						x: 40,
						y: 8,
						duration: 300,
						delay: staggerDelay(i, 60),
						easing: backOut,
					}}
				>
					<header class="panel-header">
						<span class="panel-icon">{getPanelIcon(panel.panel_type)}</span>
						<span class="panel-title">{panel.title || panel.panel_type}</span>
					</header>

					<div class="panel-content">
						{#if panel.panel_type === 'calendar'}
							<!-- Calendar panel -->
							<div class="calendar-panel">
								<div class="calendar-week">
									{#each ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as day}
										<div class="calendar-day" class:has-event={panel.data?.events?.some((e: Record<string, string>) => e.day === day)}>
											<span class="day-name">{day}</span>
											{#if panel.data?.events}
												{#each panel.data.events.filter((e: Record<string, string>) => e.day === day) as event}
													<div class="calendar-event">{event.title}</div>
												{/each}
											{/if}
										</div>
									{/each}
								</div>
								<button class="add-event-btn" onclick={() => handlePanelAction('calendar', 'add')}>
									+ Add Event
								</button>
							</div>
						{:else if panel.panel_type === 'tasks'}
							<!-- Task list panel -->
							<div class="tasks-panel">
								{#if panel.data?.items}
									{#each panel.data.items as task}
										<label class="task-item">
											<input type="checkbox" checked={task.done} onchange={() => handlePanelAction('tasks', 'toggle')} />
											<span class:done={task.done}>{task.text}</span>
										</label>
									{/each}
								{:else}
									<div class="panel-placeholder">
										<span>✓</span>
										<span>No tasks yet</span>
									</div>
								{/if}
								<button class="add-task-btn" onclick={() => handlePanelAction('tasks', 'add')}>
									+ Add Task
								</button>
							</div>
						{:else if panel.panel_type === 'code'}
							<!-- Code panel -->
							<div class="code-panel">
								<pre class="code-block language-{panel.data?.language || 'text'}"><code>{panel.data?.snippet || '// Code here'}</code></pre>
								<div class="code-actions">
									<button onclick={() => handlePanelAction('code', 'copy')}>Copy</button>
									<button onclick={() => handlePanelAction('code', 'run')}>Run</button>
								</div>
							</div>
						{:else if panel.panel_type === 'editor'}
							<!-- Editor panel -->
							<div class="editor-panel">
								<textarea
									class="editor-textarea"
									placeholder="Start writing..."
									value={panel.data?.content || ''}
									oninput={(e) => handlePanelAction('editor', 'change')}
								></textarea>
								<div class="editor-actions">
									<button onclick={() => handlePanelAction('editor', 'copy')}>Copy</button>
									<button onclick={() => handlePanelAction('editor', 'expand')}>Expand</button>
								</div>
							</div>
						{:else if panel.panel_type === 'document'}
							<!-- Document preview panel -->
							<div class="document-panel">
								<div class="document-preview">
									<span class="document-icon">📄</span>
									<span class="document-name">{panel.data?.name || 'Document'}</span>
									{#if panel.data?.pages}
										<span class="document-pages">Page 1 of {panel.data.pages}</span>
									{/if}
								</div>
								<div class="document-actions">
									<button onclick={() => handlePanelAction('document', 'prev')}>◀</button>
									<button onclick={() => handlePanelAction('document', 'next')}>▶</button>
								</div>
							</div>
						{:else if panel.panel_type === 'products'}
							<!-- Product list panel -->
							<div class="products-panel">
								{#if panel.data?.items}
									{#each panel.data.items as product}
										<div class="product-item">
											<span class="product-name">{product.name}</span>
											<span class="product-rating">{'⭐'.repeat(Math.floor(product.rating || 4))}</span>
											<span class="product-price">{product.price || '$?'}</span>
										</div>
									{/each}
								{:else}
									<div class="panel-placeholder">
										<span>💻</span>
										<span>Product recommendations</span>
									</div>
								{/if}
								<button class="compare-btn" onclick={() => handlePanelAction('products', 'compare')}>
									Compare
								</button>
							</div>
						{:else if panel.panel_type === 'links'}
							<!-- Links/resources panel -->
							<div class="links-panel">
								{#if panel.data?.resources}
									{#each panel.data.resources as link}
										<a href={link.url} target="_blank" rel="noopener noreferrer" class="resource-link">
											<span class="link-icon">{link.icon || '🔗'}</span>
											<span class="link-title">{link.title}</span>
										</a>
									{/each}
								{:else}
									<div class="panel-placeholder">
										<span>🔗</span>
										<span>Related resources</span>
									</div>
								{/if}
							</div>
						{:else if panel.panel_type === 'image'}
							<!-- Image panel -->
							{#if panel.data?.url}
								<img
									src={panel.data.url}
									alt={panel.data?.alt || 'Image'}
									class="panel-image"
								/>
							{:else if panel.data?.query}
								<div class="panel-placeholder">
									<span>🔍</span>
									<span>Search: {panel.data.query}</span>
								</div>
							{:else}
								<div class="panel-placeholder">
									<span>🖼️</span>
									<span>Visual aid</span>
								</div>
							{/if}
						{:else if panel.panel_type === 'chart'}
							<!-- Chart panel placeholder -->
							<div class="panel-placeholder chart">
								<span>📊</span>
								<span>{panel.data?.chart_type || 'Chart'}</span>
								{#if panel.data?.data_hint}
									<span class="hint">{panel.data.data_hint}</span>
								{/if}
							</div>
						{:else if panel.panel_type === 'upload'}
							<!-- Upload panel -->
							<div class="upload-zone">
								<button
									class="upload-btn"
									onclick={() => handlePanelAction('upload', 'select')}
								>
									<span class="upload-icon">📎</span>
									<span class="upload-text">
										{panel.data?.purpose || 'Drop files here or click to upload'}
									</span>
									{#if panel.data?.accept}
										<span class="upload-hint">Accepts: {panel.data.accept}</span>
									{/if}
								</button>
							</div>
						{:else if panel.panel_type === 'table'}
							<!-- Table panel placeholder -->
							<div class="panel-placeholder">
								<span>📋</span>
								<span>{panel.data?.description || 'Data table'}</span>
							</div>
						{:else if panel.panel_type === 'web'}
							<!-- Web link panel -->
							<a
								href={panel.data?.url}
								target="_blank"
								rel="noopener noreferrer"
								class="web-link"
							>
								<span class="web-icon">🌐</span>
								<span class="web-title">{panel.data?.title || panel.data?.url}</span>
								<span class="web-arrow">→</span>
							</a>
						{:else if panel.panel_type === 'calculator'}
							<!-- Calculator placeholder -->
							<div class="panel-placeholder">
								<span>🧮</span>
								<span>Calculator</span>
							</div>
						{:else if panel.panel_type === 'map'}
							<!-- Map placeholder -->
							<div class="panel-placeholder">
								<span>🗺️</span>
								<span>{panel.data?.query || 'Map'}</span>
							</div>
						{:else}
							<!-- Generic panel -->
							<div class="panel-placeholder">
								<span>📄</span>
								<span>{panel.panel_type}</span>
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</aside>
	{/if}
</div>

<style>
	.conversation-layout {
		display: flex;
		gap: var(--space-4, 16px);
		width: 100%;
		max-width: 700px;
		animation: slideUp 0.3s ease;
	}

	@keyframes slideUp {
		from {
			opacity: 0;
			transform: translateY(20px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	.conversation-layout.has-panels {
		max-width: 1000px;
	}

	.conversation-main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		background: linear-gradient(
			180deg,
			rgba(255, 215, 0, 0.02) 0%,
			rgba(10, 10, 10, 0.98) 100%
		);
		border: 1px solid rgba(255, 215, 0, 0.1);
		border-radius: var(--radius-lg, 12px);
		overflow: hidden;
	}

	/* Header */
	.conversation-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-3, 12px) var(--space-4, 16px);
		border-bottom: 1px solid rgba(255, 215, 0, 0.08);
	}

	.mode-indicator {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
	}

	.mode-emoji {
		font-size: var(--text-lg, 18px);
	}

	.mode-label {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		padding: var(--space-1, 4px);
		border-radius: var(--radius-sm, 4px);
		transition: all 0.15s ease;
	}

	.dismiss-btn:hover {
		color: var(--text-primary, #fff);
		background: rgba(255, 255, 255, 0.05);
	}

	/* Messages */
	.messages-container {
		flex: 1;
		padding: var(--space-4, 16px);
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
		max-height: 400px;
		overflow-y: auto;
	}

	.message {
		display: flex;
		gap: var(--space-2, 8px);
		align-items: flex-start;
	}

	.message-role {
		flex-shrink: 0;
		width: 24px;
		text-align: center;
	}

	.message-content {
		margin: 0;
		color: var(--text-primary, #fff);
		line-height: 1.6;
		white-space: pre-wrap;
	}

	.message-user {
		opacity: 0.8;
	}

	.message-user .message-content {
		color: var(--text-secondary, #999);
	}

	.message-assistant.current .message-content {
		color: var(--text-primary, #fff);
	}

	.thinking-dots {
		color: var(--text-tertiary, #666);
	}

	.thinking-dots .dots {
		animation: blink 1.4s infinite;
	}

	@keyframes blink {
		0%, 20% { opacity: 1; }
		50% { opacity: 0.3; }
		80%, 100% { opacity: 1; }
	}

	/* Tool suggestions */
	.tool-suggestions {
		display: flex;
		gap: var(--space-2, 8px);
		padding: 0 var(--space-4, 16px);
	}

	.tool-chip {
		padding: var(--space-1, 4px) var(--space-2, 8px);
		background: rgba(255, 215, 0, 0.05);
		border: 1px solid rgba(255, 215, 0, 0.15);
		border-radius: var(--radius-full, 9999px);
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.tool-chip:hover {
		background: rgba(255, 215, 0, 0.15);
		border-color: rgba(255, 215, 0, 0.3);
		color: var(--text-gold, #ffd700);
	}

	/* Input area at bottom */
	.input-area {
		padding: var(--space-3, 12px) var(--space-4, 16px);
		border-top: 1px solid rgba(255, 215, 0, 0.08);
		background: rgba(0, 0, 0, 0.2);
	}

	/* Auxiliary panels */
	.auxiliary-panels {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
		width: 280px;
		flex-shrink: 0;
	}

	.panel {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-md, 8px);
		overflow: hidden;
	}

	.panel-header {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px) var(--space-3, 12px);
		background: rgba(255, 255, 255, 0.03);
		border-bottom: 1px solid var(--border-subtle, #333);
	}

	.panel-icon {
		font-size: var(--text-lg, 18px);
	}

	.panel-title {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		font-weight: 500;
		text-transform: capitalize;
	}

	.panel-content {
		padding: var(--space-3, 12px);
	}

	.panel-placeholder {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		gap: var(--space-2, 8px);
		padding: var(--space-6, 24px);
		color: var(--text-tertiary, #666);
		text-align: center;
	}

	.panel-placeholder span:first-child {
		font-size: 2rem;
		opacity: 0.5;
	}

	.panel-placeholder.chart {
		background: linear-gradient(
			135deg,
			rgba(100, 200, 255, 0.05) 0%,
			rgba(50, 100, 200, 0.05) 100%
		);
	}

	.panel-placeholder .hint {
		font-size: var(--text-xs, 12px);
		opacity: 0.7;
	}

	.panel-image {
		width: 100%;
		border-radius: var(--radius-sm, 4px);
		object-fit: cover;
	}

	/* Upload zone */
	.upload-zone {
		padding: var(--space-2, 8px);
	}

	.upload-btn {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2, 8px);
		width: 100%;
		padding: var(--space-4, 16px);
		background: rgba(255, 215, 0, 0.03);
		border: 2px dashed rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-md, 8px);
		color: var(--text-secondary, #999);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.upload-btn:hover {
		background: rgba(255, 215, 0, 0.08);
		border-color: rgba(255, 215, 0, 0.4);
		color: var(--text-gold, #ffd700);
	}

	.upload-icon {
		font-size: 1.5rem;
	}

	.upload-text {
		font-size: var(--text-sm, 14px);
	}

	.upload-hint {
		font-size: var(--text-xs, 12px);
		opacity: 0.7;
	}

	/* Web link */
	.web-link {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-3, 12px);
		background: rgba(100, 150, 255, 0.05);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		text-decoration: none;
		transition: all 0.15s ease;
	}

	.web-link:hover {
		background: rgba(100, 150, 255, 0.1);
		color: var(--text-primary, #fff);
	}

	.web-title {
		flex: 1;
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	.web-arrow {
		color: rgba(100, 150, 255, 0.7);
	}

	/* Calendar panel */
	.calendar-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.calendar-week {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
	}

	.calendar-day {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: var(--space-1, 4px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-xs, 2px);
		min-height: 48px;
	}

	.calendar-day.has-event {
		background: rgba(255, 215, 0, 0.1);
		border: 1px solid rgba(255, 215, 0, 0.3);
	}

	.day-name {
		font-size: 10px;
		color: var(--text-tertiary, #666);
		text-transform: uppercase;
	}

	.calendar-event {
		font-size: 9px;
		padding: 2px 4px;
		background: rgba(255, 215, 0, 0.2);
		border-radius: 2px;
		color: var(--text-gold, #ffd700);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
		max-width: 100%;
	}

	.add-event-btn, .add-task-btn, .compare-btn {
		padding: var(--space-2, 8px);
		background: rgba(255, 215, 0, 0.05);
		border: 1px dashed rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		cursor: pointer;
		transition: all 0.15s ease;
		font-size: var(--text-sm, 14px);
	}

	.add-event-btn:hover, .add-task-btn:hover, .compare-btn:hover {
		background: rgba(255, 215, 0, 0.1);
		border-color: rgba(255, 215, 0, 0.4);
		color: var(--text-gold, #ffd700);
	}

	/* Tasks panel */
	.tasks-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.task-item {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-sm, 4px);
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.task-item:hover {
		background: rgba(255, 255, 255, 0.05);
	}

	.task-item input[type="checkbox"] {
		accent-color: var(--text-gold, #ffd700);
	}

	.task-item span.done {
		text-decoration: line-through;
		color: var(--text-tertiary, #666);
	}

	/* Code panel */
	.code-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.code-block {
		margin: 0;
		padding: var(--space-3, 12px);
		background: rgba(0, 0, 0, 0.4);
		border-radius: var(--radius-sm, 4px);
		overflow-x: auto;
		font-family: 'JetBrains Mono', 'Fira Code', monospace;
		font-size: var(--text-sm, 14px);
		line-height: 1.5;
		color: var(--text-primary, #fff);
	}

	.code-actions, .editor-actions, .document-actions {
		display: flex;
		gap: var(--space-2, 8px);
	}

	.code-actions button, .editor-actions button, .document-actions button {
		flex: 1;
		padding: var(--space-2, 8px);
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		cursor: pointer;
		font-size: var(--text-xs, 12px);
		transition: all 0.15s ease;
	}

	.code-actions button:hover, .editor-actions button:hover, .document-actions button:hover {
		background: rgba(255, 255, 255, 0.1);
		color: var(--text-primary, #fff);
	}

	/* Editor panel */
	.editor-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.editor-textarea {
		width: 100%;
		min-height: 120px;
		padding: var(--space-3, 12px);
		background: rgba(0, 0, 0, 0.3);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-primary, #fff);
		font-family: inherit;
		font-size: var(--text-sm, 14px);
		line-height: 1.6;
		resize: vertical;
	}

	.editor-textarea:focus {
		outline: none;
		border-color: rgba(255, 215, 0, 0.4);
	}

	/* Document panel */
	.document-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
	}

	.document-preview {
		display: flex;
		flex-direction: column;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-6, 24px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-sm, 4px);
	}

	.document-icon {
		font-size: 3rem;
		opacity: 0.5;
	}

	.document-name {
		font-size: var(--text-sm, 14px);
		color: var(--text-primary, #fff);
	}

	.document-pages {
		font-size: var(--text-xs, 12px);
		color: var(--text-tertiary, #666);
	}

	/* Products panel */
	.products-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.product-item {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px) var(--space-3, 12px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-sm, 4px);
		border: 1px solid var(--border-subtle, #333);
	}

	.product-name {
		flex: 1;
		font-size: var(--text-sm, 14px);
		color: var(--text-primary, #fff);
	}

	.product-rating {
		font-size: 10px;
	}

	.product-price {
		font-size: var(--text-sm, 14px);
		color: var(--text-gold, #ffd700);
		font-weight: 500;
	}

	/* Links panel */
	.links-panel {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.resource-link {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-2, 8px) var(--space-3, 12px);
		background: rgba(100, 150, 255, 0.05);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		text-decoration: none;
		transition: all 0.15s ease;
	}

	.resource-link:hover {
		background: rgba(100, 150, 255, 0.1);
		color: var(--text-primary, #fff);
	}

	.link-icon {
		font-size: var(--text-lg, 18px);
	}

	.link-title {
		flex: 1;
		font-size: var(--text-sm, 14px);
		overflow: hidden;
		text-overflow: ellipsis;
		white-space: nowrap;
	}

	/* Responsive */
	@media (max-width: 768px) {
		.conversation-layout {
			flex-direction: column;
		}

		.auxiliary-panels {
			width: 100%;
			flex-direction: row;
			flex-wrap: wrap;
		}

		.panel {
			flex: 1;
			min-width: 200px;
		}
	}
</style>
