<!--
  MinimizedDock — Edge dock for minimized panels (RFC-082)
  
  Panels minimize to dock edges (left, right, bottom) and show
  peek indicators. Click to restore with spring animation.
-->
<script lang="ts">
	import { fly, scale } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import { spatialState, dockElements } from '../lib/spatial-state';
	import { staggerDelay } from '../lib/tetris';

	type DockEdge = 'left' | 'right' | 'bottom';

	interface Props {
		edge: DockEdge;
		onRestore?: (id: string) => void;
	}

	let { edge, onRestore }: Props = $props();

	// Get elements in this dock
	// svelte-ignore state_referenced_locally - edge prop is static per component instance
	const elements = dockElements(edge);

	// Hover state for peek preview
	let hoveredId: string | null = $state(null);
	let previewScale = spring(0, { stiffness: 0.15, damping: 0.5 });

	// Icon mapping for element types
	function getIcon(type: string): string {
		const icons: Record<string, string> = {
			panel: '📋',
			calendar: '📅',
			tasks: '✓',
			chart: '📊',
			code: '🐍',
			editor: '📝',
			document: '📄',
			file_tree: '📁',
			terminal: '⬛',
			conversation: '💬',
			notes: '📝',
			map: '🗺️',
		};
		return icons[type] || '📄';
	}

	// Get position classes based on edge
	function getPositionClass(): string {
		switch (edge) {
			case 'left': return 'dock-left';
			case 'right': return 'dock-right';
			case 'bottom': return 'dock-bottom';
		}
	}

	// Get transition based on edge
	function getTransition(index: number) {
		const delay = staggerDelay(index, 30);
		switch (edge) {
			case 'left': return { x: -30, duration: 200, delay };
			case 'right': return { x: 30, duration: 200, delay };
			case 'bottom': return { y: 30, duration: 200, delay };
		}
	}

	function handleRestore(id: string) {
		spatialState.restore(id);
		onRestore?.(id);
	}

	function handleHover(id: string | null) {
		hoveredId = id;
		previewScale.set(id ? 1 : 0);
	}
</script>

{#if $elements.length > 0}
	<div class="minimized-dock {getPositionClass()}">
		<div class="dock-container">
			{#each $elements as element, i (element.id)}
				<button
					class="dock-item"
					class:hovered={hoveredId === element.id}
					transition:fly={getTransition(i)}
					onclick={() => handleRestore(element.id)}
					onmouseenter={() => handleHover(element.id)}
					onmouseleave={() => handleHover(null)}
					aria-label="Restore {element.type}"
				>
					<span class="dock-icon">{getIcon(element.type)}</span>

					<!-- Peek preview on hover -->
					{#if hoveredId === element.id}
						<div
							class="peek-preview"
							style:transform="scale({$previewScale})"
							transition:scale={{ duration: 150 }}
						>
							<span class="peek-title">{element.type}</span>
							<span class="peek-hint">Click to restore</span>
						</div>
					{/if}
				</button>
			{/each}
		</div>

		<!-- Dock glow effect -->
		<div class="dock-glow"></div>
	</div>
{/if}

<style>
	.minimized-dock {
		position: fixed;
		z-index: 100;
		pointer-events: none;
	}

	.dock-container {
		display: flex;
		gap: var(--space-2);
		pointer-events: auto;
	}

	/* Position variants */
	.dock-left {
		left: var(--space-3);
		top: 50%;
		transform: translateY(-50%);
	}

	.dock-left .dock-container {
		flex-direction: column;
	}

	.dock-right {
		right: var(--space-3);
		top: 50%;
		transform: translateY(-50%);
	}

	.dock-right .dock-container {
		flex-direction: column;
	}

	.dock-bottom {
		bottom: var(--space-3);
		left: 50%;
		transform: translateX(-50%);
	}

	.dock-bottom .dock-container {
		flex-direction: row;
	}

	/* Dock item */
	.dock-item {
		position: relative;
		width: 44px;
		height: 44px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: rgba(10, 10, 10, 0.9);
		border: 1px solid var(--radiant-gold-20);
		border-radius: var(--radius-md);
		cursor: pointer;
		transition: all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
		backdrop-filter: blur(12px);
	}

	.dock-item:hover {
		background: rgba(20, 20, 20, 0.95);
		border-color: var(--radiant-gold-40);
		transform: scale(1.1);
		box-shadow:
			0 4px 20px rgba(0, 0, 0, 0.4),
			0 0 20px var(--radiant-gold-10);
	}

	.dock-item:active {
		transform: scale(0.95);
	}

	.dock-icon {
		font-size: 20px;
		transition: transform 0.2s ease;
	}

	.dock-item:hover .dock-icon {
		transform: scale(1.1);
	}

	/* Peek preview */
	.peek-preview {
		position: absolute;
		background: rgba(10, 10, 10, 0.95);
		border: 1px solid var(--radiant-gold-30);
		border-radius: var(--radius-sm);
		padding: var(--space-2) var(--space-3);
		white-space: nowrap;
		backdrop-filter: blur(12px);
		transform-origin: center;
	}

	/* Position peek based on dock edge */
	.dock-left .peek-preview {
		left: calc(100% + 12px);
		top: 50%;
		transform: translateY(-50%);
	}

	.dock-right .peek-preview {
		right: calc(100% + 12px);
		top: 50%;
		transform: translateY(-50%);
	}

	.dock-bottom .peek-preview {
		bottom: calc(100% + 12px);
		left: 50%;
		transform: translateX(-50%);
	}

	.peek-title {
		display: block;
		color: var(--text-primary);
		font-size: var(--text-sm);
		font-weight: 500;
		text-transform: capitalize;
	}

	.peek-hint {
		display: block;
		color: var(--text-tertiary);
		font-size: var(--text-xs);
		margin-top: 2px;
	}

	/* Dock glow effect */
	.dock-glow {
		position: absolute;
		inset: -20px;
		background: radial-gradient(
			ellipse at center,
			var(--radiant-gold-5) 0%,
			transparent 70%
		);
		pointer-events: none;
		opacity: 0;
		transition: opacity 0.3s ease;
	}

	.minimized-dock:hover .dock-glow {
		opacity: 1;
	}

	/* Position glow correctly */
	.dock-left .dock-glow {
		left: -10px;
		right: auto;
		width: 100px;
	}

	.dock-right .dock-glow {
		right: -10px;
		left: auto;
		width: 100px;
	}

	.dock-bottom .dock-glow {
		bottom: -10px;
		top: auto;
		height: 100px;
	}

	/* Keyboard focus */
	.dock-item:focus-visible {
		outline: 2px solid var(--gold);
		outline-offset: 2px;
	}
</style>
