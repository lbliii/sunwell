<!--
  SkeletonLayout — Speculative UI composition (RFC-082)
  
  Renders a UI skeleton instantly based on compositor prediction,
  before the main content is ready. Content streams in progressively.
  
  Flow:
  1. Compositor predicts layout (50-100ms)
  2. SkeletonLayout renders skeleton with shimmer
  3. Content streams in, replacing skeleton lines
  4. Final state: full content with animated panels
-->
<script lang="ts">
	import { fly, fade, scale } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import FluidInput from './FluidInput.svelte';
	import { SPRING_CONFIGS, staggerDelay } from '../lib/tetris';

	interface PanelSpec {
		panel_type: string;
		title?: string;
		data?: Record<string, unknown>;
	}

	interface CompositionSpec {
		page_type: string;
		panels: PanelSpec[];
		input_mode: 'hero' | 'chat' | 'search' | 'command' | 'hidden';
		suggested_tools: string[];
		confidence: number;
		source: string;
	}

	interface Props {
		composition: CompositionSpec;
		content?: string;
		streaming?: boolean;
		loading?: boolean;
		onSubmit?: (value: string) => void;
		onPanelAction?: (panelType: string, action: string) => void;
	}

	let {
		composition,
		content = '',
		streaming = false,
		loading = false,
		onSubmit,
		onPanelAction,
	}: Props = $props();

	// Spring-animated opacity for smooth content fade-in
	const contentOpacity = spring(0, { stiffness: 0.1, damping: 0.4 });

	// Track when content arrives
	$effect(() => {
		if (content) {
			contentOpacity.set(1);
		} else {
			contentOpacity.set(0);
		}
	});

	// Panel icon mapping
	function getPanelIcon(panelType: string): string {
		const icons: Record<string, string> = {
			calendar: '📅',
			tasks: '✓',
			chart: '📊',
			image: '🖼️',
			code: '🐍',
			editor: '📝',
			document: '📄',
			products: '💻',
			links: '🔗',
			map: '🗺️',
			upload: '📎',
			notes: '📝',
			sources: '📚',
			file_tree: '📁',
			terminal: '⬛',
			preview: '👁️',
		};
		return icons[panelType] || '📄';
	}

	// Get skeleton line count based on panel type
	function getSkeletonLineCount(panelType: string): number {
		const counts: Record<string, number> = {
			calendar: 4,
			tasks: 5,
			chart: 3,
			code: 6,
			editor: 8,
			products: 4,
			links: 3,
			notes: 5,
		};
		return counts[panelType] || 3;
	}

	let inputValue = $state('');
</script>

<div
	class="skeleton-layout layout-{composition.page_type}"
	class:has-panels={composition.panels.length > 0}
	class:streaming
	in:fade={{ duration: 150 }}
>
	<!-- Main content area -->
	<main class="skeleton-main">
		<!-- Content or skeleton -->
		<div class="content-area">
			{#if content}
				<div
					class="content"
					style:opacity={$contentOpacity}
					transition:fade={{ duration: 200 }}
				>
					{@html content}
				</div>
			{:else}
				<div class="skeleton-content" in:fade={{ duration: 100 }}>
					<div class="skeleton-line w-75" style:animation-delay="0ms"></div>
					<div class="skeleton-line w-100" style:animation-delay="100ms"></div>
					<div class="skeleton-line w-60" style:animation-delay="200ms"></div>
					{#if loading}
						<div class="skeleton-line w-80" style:animation-delay="300ms"></div>
						<div class="skeleton-line w-45" style:animation-delay="400ms"></div>
					{/if}
				</div>
			{/if}

			{#if streaming}
				<div class="streaming-indicator">
					<span class="streaming-dot"></span>
					<span class="streaming-text">Generating...</span>
				</div>
			{/if}
		</div>

		<!-- Fluid input positioned by mode -->
		<div class="input-area input-{composition.input_mode}">
			<FluidInput
				bind:value={inputValue}
				mode={composition.input_mode}
				{loading}
				onsubmit={(v) => {
					inputValue = '';
					onSubmit?.(v);
				}}
			/>

			{#if composition.suggested_tools.length > 0}
				<div class="suggested-tools" transition:fly={{ y: 10, duration: 200, delay: 300 }}>
					{#each composition.suggested_tools as tool, i (tool)}
						<button
							class="tool-chip"
							style:animation-delay="{staggerDelay(i, 50)}ms"
							onclick={() => onPanelAction?.('input', `use_${tool}`)}
						>
							{tool === 'upload' ? '📎' : tool === 'voice' ? '🎤' : tool === 'camera' ? '📷' : '🔧'}
						</button>
					{/each}
				</div>
			{/if}
		</div>
	</main>

	<!-- Auxiliary panels area -->
	{#if composition.panels.length > 0}
		<aside class="skeleton-panels" transition:fly={{ x: 100, duration: 300 }}>
			{#each composition.panels as panel, i (panel.panel_type + i)}
				<div
					class="skeleton-panel panel-{panel.panel_type}"
					transition:fly={{ x: 50, duration: 200, delay: staggerDelay(i, 50) }}
				>
					<header class="panel-header">
						<span class="panel-icon">{getPanelIcon(panel.panel_type)}</span>
						<span class="panel-title">{panel.title || panel.panel_type}</span>
					</header>

					<div class="panel-content">
						<!-- Skeleton lines for panel -->
						{#each Array(getSkeletonLineCount(panel.panel_type)) as _, lineIdx (lineIdx)}
							<div
								class="skeleton-line"
								class:w-100={lineIdx % 3 === 0}
								class:w-75={lineIdx % 3 === 1}
								class:w-50={lineIdx % 3 === 2}
								style:animation-delay="{staggerDelay(lineIdx, 80)}ms"
							></div>
						{/each}

						<!-- Panel-specific skeleton elements -->
						{#if panel.panel_type === 'calendar'}
							<div class="skeleton-calendar">
								{#each ['M', 'T', 'W', 'T', 'F', 'S', 'S'] as day, i (i)}
									<div class="calendar-day-skeleton">
										<span>{day}</span>
									</div>
								{/each}
							</div>
						{:else if panel.panel_type === 'chart'}
							<div class="skeleton-chart">
								<div class="chart-bar" style:height="60%"></div>
								<div class="chart-bar" style:height="80%"></div>
								<div class="chart-bar" style:height="45%"></div>
								<div class="chart-bar" style:height="90%"></div>
								<div class="chart-bar" style:height="55%"></div>
							</div>
						{:else if panel.panel_type === 'code'}
							<div class="skeleton-code">
								<div class="code-line"><span class="keyword"></span><span class="text w-40"></span></div>
								<div class="code-line indent"><span class="text w-60"></span></div>
								<div class="code-line indent"><span class="string"></span><span class="text w-30"></span></div>
								<div class="code-line"></div>
								<div class="code-line"><span class="keyword"></span><span class="text w-50"></span></div>
							</div>
						{/if}
					</div>
				</div>
			{/each}
		</aside>
	{/if}
</div>

<style>
	.skeleton-layout {
		display: flex;
		gap: var(--space-4);
		width: 100%;
		max-width: 700px;
		min-height: 300px;
	}

	.skeleton-layout.has-panels {
		max-width: 1000px;
	}

	/* Main content area */
	.skeleton-main {
		flex: 1;
		min-width: 0;
		display: flex;
		flex-direction: column;
		background: linear-gradient(
			180deg,
			rgba(var(--radiant-gold-rgb), 0.02) 0%,
			rgba(10, 10, 10, 0.98) 100%
		);
		border: 1px solid var(--radiant-gold-10);
		border-radius: var(--radius-lg);
		overflow: hidden;
	}

	.content-area {
		flex: 1;
		padding: var(--space-4);
		min-height: 200px;
	}

	.content {
		color: var(--text-primary);
		line-height: 1.6;
	}

	/* Skeleton lines with shimmer */
	.skeleton-content {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
	}

	.skeleton-line {
		height: 1em;
		background: linear-gradient(
			90deg,
			rgba(255, 255, 255, 0.03) 0%,
			rgba(255, 255, 255, 0.08) 50%,
			rgba(255, 255, 255, 0.03) 100%
		);
		background-size: 200% 100%;
		animation: shimmer 1.5s infinite;
		border-radius: 4px;
	}

	.skeleton-line.w-100 { width: 100%; }
	.skeleton-line.w-80 { width: 80%; }
	.skeleton-line.w-75 { width: 75%; }
	.skeleton-line.w-60 { width: 60%; }
	.skeleton-line.w-50 { width: 50%; }
	.skeleton-line.w-45 { width: 45%; }
	.skeleton-line.w-40 { width: 40%; }
	.skeleton-line.w-30 { width: 30%; }

	@keyframes shimmer {
		0% { background-position: 200% 0; }
		100% { background-position: -200% 0; }
	}

	/* Streaming indicator */
	.streaming-indicator {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin-top: var(--space-3);
		color: var(--text-tertiary);
		font-size: var(--text-sm);
	}

	.streaming-dot {
		width: 8px;
		height: 8px;
		background: var(--gold);
		border-radius: 50%;
		animation: pulse 1s infinite;
	}

	@keyframes pulse {
		0%, 100% { opacity: 0.4; transform: scale(0.9); }
		50% { opacity: 1; transform: scale(1.1); }
	}

	/* Input area positioning */
	.input-area {
		padding: var(--space-3) var(--space-4);
		border-top: 1px solid rgba(var(--radiant-gold-rgb), 0.08);
		background: rgba(0, 0, 0, 0.2);
	}

	.input-hero {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: var(--space-6);
		border-top: none;
		background: transparent;
	}

	.suggested-tools {
		display: flex;
		gap: var(--space-2);
		margin-top: var(--space-2);
	}

	.tool-chip {
		padding: var(--space-1) var(--space-2);
		background: var(--radiant-gold-5);
		border: 1px solid var(--radiant-gold-15);
		border-radius: var(--radius-full);
		color: var(--text-secondary);
		font-size: var(--text-sm);
		cursor: pointer;
		transition: all 0.15s ease;
		animation: fadeSlideUp 0.3s ease backwards;
	}

	.tool-chip:hover {
		background: var(--radiant-gold-15);
		border-color: var(--radiant-gold-30);
		color: var(--text-gold);
	}

	@keyframes fadeSlideUp {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	/* Panels area */
	.skeleton-panels {
		display: flex;
		flex-direction: column;
		gap: var(--space-3);
		width: 280px;
		flex-shrink: 0;
	}

	.skeleton-panel {
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		overflow: hidden;
	}

	.panel-header {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.03);
		border-bottom: 1px solid var(--border-subtle);
	}

	.panel-icon {
		font-size: var(--text-lg);
	}

	.panel-title {
		color: var(--text-secondary);
		font-size: var(--text-sm);
		font-weight: 500;
		text-transform: capitalize;
	}

	.panel-content {
		padding: var(--space-3);
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	/* Calendar skeleton */
	.skeleton-calendar {
		display: grid;
		grid-template-columns: repeat(7, 1fr);
		gap: 2px;
		margin-top: var(--space-2);
	}

	.calendar-day-skeleton {
		display: flex;
		flex-direction: column;
		align-items: center;
		padding: var(--space-1);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-xs);
		min-height: 32px;
	}

	.calendar-day-skeleton span {
		font-size: 10px;
		color: var(--text-tertiary);
	}

	/* Chart skeleton */
	.skeleton-chart {
		display: flex;
		align-items: flex-end;
		gap: var(--space-2);
		height: 80px;
		margin-top: var(--space-2);
	}

	.chart-bar {
		flex: 1;
		background: linear-gradient(
			180deg,
			var(--radiant-gold-20) 0%,
			var(--radiant-gold-5) 100%
		);
		border-radius: 2px 2px 0 0;
		animation: barGrow 0.5s ease backwards;
	}

	.chart-bar:nth-child(1) { animation-delay: 100ms; }
	.chart-bar:nth-child(2) { animation-delay: 150ms; }
	.chart-bar:nth-child(3) { animation-delay: 200ms; }
	.chart-bar:nth-child(4) { animation-delay: 250ms; }
	.chart-bar:nth-child(5) { animation-delay: 300ms; }

	@keyframes barGrow {
		from {
			transform: scaleY(0);
			transform-origin: bottom;
		}
		to {
			transform: scaleY(1);
		}
	}

	/* Code skeleton */
	.skeleton-code {
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
		background: rgba(0, 0, 0, 0.3);
		padding: var(--space-2);
		border-radius: var(--radius-sm);
		font-family: monospace;
	}

	.code-line {
		display: flex;
		gap: var(--space-1);
		height: 14px;
	}

	.code-line.indent {
		padding-left: var(--space-3);
	}

	.code-line .keyword {
		width: 40px;
		background: rgba(197, 134, 192, 0.2);
		border-radius: 2px;
	}

	.code-line .string {
		width: 20px;
		background: rgba(206, 145, 120, 0.2);
		border-radius: 2px;
	}

	.code-line .text {
		background: rgba(255, 255, 255, 0.05);
		border-radius: 2px;
		animation: shimmer 1.5s infinite;
	}

	.code-line .text.w-30 { width: 30%; }
	.code-line .text.w-40 { width: 40%; }
	.code-line .text.w-50 { width: 50%; }
	.code-line .text.w-60 { width: 60%; }

	/* Responsive */
	@media (max-width: 768px) {
		.skeleton-layout {
			flex-direction: column;
		}

		.skeleton-panels {
			width: 100%;
			flex-direction: row;
			flex-wrap: wrap;
		}

		.skeleton-panel {
			flex: 1;
			min-width: 200px;
		}
	}
</style>
