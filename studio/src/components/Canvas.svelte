<!--
  Canvas — Infinite pan/zoom surface (RFC-082)
  
  The unified space containing all layouts. Users can:
  - Pan with two-finger drag or middle mouse
  - Zoom with pinch or scroll
  - Navigate to named areas
  - See overview with zoom-out
-->
<script lang="ts">
	import { spring } from 'svelte/motion';
	import { onMount, onDestroy } from 'svelte';
	import { SPRING_CONFIGS } from '../lib/tetris';
	import GestureProvider from './GestureProvider.svelte';

	interface CanvasArea {
		id: string;
		name: string;
		x: number;
		y: number;
		width: number;
		height: number;
	}

	interface Props {
		areas?: CanvasArea[];
		initialArea?: string;
		minZoom?: number;
		maxZoom?: number;
		enableMinimap?: boolean;
		onAreaChange?: (areaId: string | null) => void;
		children?: import('svelte').Snippet;
	}

	let {
		areas = [],
		initialArea,
		minZoom = 0.1,
		maxZoom = 3,
		enableMinimap = true,
		onAreaChange,
		children,
	}: Props = $props();

	// Viewport state with spring physics
	const viewportX = spring(0, { stiffness: 0.08, damping: 0.4 });
	const viewportY = spring(0, { stiffness: 0.08, damping: 0.4 });
	const viewportZoom = spring(1, { stiffness: 0.1, damping: 0.5 });

	let containerEl: HTMLDivElement | undefined = $state();
	let containerWidth = $state(0);
	let containerHeight = $state(0);

	// Track current visible area
	let currentArea: string | null = $state(null);
	let isOverviewMode = $state(false);
	let isPanning = $state(false);

	// Mouse position for zoom targeting
	let lastMouseX = 0;
	let lastMouseY = 0;

	// Navigate to initial area
	onMount(() => {
		if (initialArea) {
			navigateTo(initialArea, { animate: false });
		}

		// Set up resize observer
		if (containerEl) {
			const observer = new ResizeObserver((entries) => {
				const entry = entries[0];
				containerWidth = entry.contentRect.width;
				containerHeight = entry.contentRect.height;
			});
			observer.observe(containerEl);
			return () => observer.disconnect();
		}
	});

	/**
	 * Navigate to a specific area.
	 */
	export function navigateTo(
		areaId: string,
		options: { zoom?: number; animate?: boolean } = {}
	): void {
		const area = areas.find((a) => a.id === areaId);
		if (!area) return;

		const { zoom = 1, animate = true } = options;

		// Center the area in viewport
		const targetX = -(area.x + area.width / 2) + containerWidth / 2 / zoom;
		const targetY = -(area.y + area.height / 2) + containerHeight / 2 / zoom;

		if (animate) {
			viewportX.set(targetX);
			viewportY.set(targetY);
			viewportZoom.set(zoom);
		} else {
			viewportX.set(targetX, { hard: true });
			viewportY.set(targetY, { hard: true });
			viewportZoom.set(zoom, { hard: true });
		}

		currentArea = areaId;
		isOverviewMode = false;
		onAreaChange?.(areaId);
	}

	/**
	 * Zoom to fit specific elements.
	 */
	export function zoomToFit(elementIds: string[]): void {
		// Calculate bounding box of elements
		const filteredAreas = areas.filter((a) => elementIds.includes(a.id));
		if (filteredAreas.length === 0) return;

		const minX = Math.min(...filteredAreas.map((a) => a.x));
		const minY = Math.min(...filteredAreas.map((a) => a.y));
		const maxX = Math.max(...filteredAreas.map((a) => a.x + a.width));
		const maxY = Math.max(...filteredAreas.map((a) => a.y + a.height));

		const width = maxX - minX;
		const height = maxY - minY;

		// Calculate zoom to fit with padding
		const padding = 50;
		const zoomX = (containerWidth - padding * 2) / width;
		const zoomY = (containerHeight - padding * 2) / height;
		const zoom = Math.min(zoomX, zoomY, maxZoom);

		const centerX = minX + width / 2;
		const centerY = minY + height / 2;

		viewportX.set(-centerX + containerWidth / 2 / zoom);
		viewportY.set(-centerY + containerHeight / 2 / zoom);
		viewportZoom.set(zoom);
	}

	/**
	 * Toggle overview mode (zoom out to see everything).
	 */
	export function overview(): void {
		if (isOverviewMode) {
			// Return to previous view
			if (currentArea) {
				navigateTo(currentArea);
			} else {
				viewportZoom.set(1);
			}
			isOverviewMode = false;
		} else {
			// Zoom out to show all areas
			if (areas.length > 0) {
				zoomToFit(areas.map((a) => a.id));
			} else {
				viewportZoom.set(0.3);
			}
			isOverviewMode = true;
		}
	}

	/**
	 * Reset view to home position.
	 */
	export function reset(): void {
		viewportX.set(0);
		viewportY.set(0);
		viewportZoom.set(1);
		currentArea = null;
		isOverviewMode = false;
		onAreaChange?.(null);
	}

	// Handle gestures
	function handleGesture(action: { type: string; x?: number; y?: number; scale?: number }) {
		switch (action.type) {
			case 'pan':
				if (action.x !== undefined && action.y !== undefined) {
					viewportX.update((v) => v - action.x! / $viewportZoom);
					viewportY.update((v) => v - action.y! / $viewportZoom);
				}
				break;
			case 'pinch':
				if (action.scale !== undefined) {
					const newZoom = Math.max(minZoom, Math.min(maxZoom, $viewportZoom * action.scale));
					viewportZoom.set(newZoom);
				}
				break;
		}
	}

	// Handle wheel zoom
	function handleWheel(e: WheelEvent) {
		e.preventDefault();

		// Zoom toward mouse position
		const rect = containerEl?.getBoundingClientRect();
		if (!rect) return;

		lastMouseX = e.clientX - rect.left;
		lastMouseY = e.clientY - rect.top;

		const delta = e.deltaY > 0 ? 0.9 : 1.1;
		const newZoom = Math.max(minZoom, Math.min(maxZoom, $viewportZoom * delta));

		// Adjust position to zoom toward mouse
		const factor = newZoom / $viewportZoom;
		const mouseCanvasX = (lastMouseX / $viewportZoom - $viewportX);
		const mouseCanvasY = (lastMouseY / $viewportZoom - $viewportY);

		viewportX.set($viewportX - mouseCanvasX * (factor - 1) / factor);
		viewportY.set($viewportY - mouseCanvasY * (factor - 1) / factor);
		viewportZoom.set(newZoom);
	}

	// Handle panning with mouse drag (middle button or shift+left)
	let panStartX = 0;
	let panStartY = 0;
	let panStartViewX = 0;
	let panStartViewY = 0;

	function handleMouseDown(e: MouseEvent) {
		if (e.button === 1 || (e.button === 0 && e.shiftKey)) {
			e.preventDefault();
			isPanning = true;
			panStartX = e.clientX;
			panStartY = e.clientY;
			panStartViewX = $viewportX;
			panStartViewY = $viewportY;

			window.addEventListener('mousemove', handleMouseMove);
			window.addEventListener('mouseup', handleMouseUp);
		}
	}

	function handleMouseMove(e: MouseEvent) {
		if (!isPanning) return;

		const dx = (e.clientX - panStartX) / $viewportZoom;
		const dy = (e.clientY - panStartY) / $viewportZoom;

		viewportX.set(panStartViewX + dx, { hard: true });
		viewportY.set(panStartViewY + dy, { hard: true });
	}

	function handleMouseUp() {
		isPanning = false;
		window.removeEventListener('mousemove', handleMouseMove);
		window.removeEventListener('mouseup', handleMouseUp);
	}

	// Keyboard navigation
	function handleKeyDown(e: KeyboardEvent) {
		if (e.target !== containerEl) return;

		const step = 50 / $viewportZoom;

		switch (e.key) {
			case 'ArrowLeft':
				viewportX.update((v) => v + step);
				break;
			case 'ArrowRight':
				viewportX.update((v) => v - step);
				break;
			case 'ArrowUp':
				viewportY.update((v) => v + step);
				break;
			case 'ArrowDown':
				viewportY.update((v) => v - step);
				break;
			case '0':
				if (e.metaKey || e.ctrlKey) {
					e.preventDefault();
					reset();
				}
				break;
			case '-':
				if (e.metaKey || e.ctrlKey) {
					e.preventDefault();
					viewportZoom.update((z) => Math.max(minZoom, z * 0.8));
				}
				break;
			case '=':
			case '+':
				if (e.metaKey || e.ctrlKey) {
					e.preventDefault();
					viewportZoom.update((z) => Math.min(maxZoom, z * 1.25));
				}
				break;
		}
	}
</script>

<section
	bind:this={containerEl}
	class="canvas-container"
	class:panning={isPanning}
	class:overview={isOverviewMode}
	tabindex="0"
	role="application"
	aria-label="Canvas navigation: use arrow keys to pan, Cmd/Ctrl +/- to zoom"
	onwheel={handleWheel}
	onmousedown={handleMouseDown}
	onkeydown={handleKeyDown}
>
	<GestureProvider
		enablePan={true}
		enablePinch={true}
		onGesture={handleGesture}
	>
		<div
			class="canvas-content"
			style:transform="translate({$viewportX}px, {$viewportY}px) scale({$viewportZoom})"
		>
			<!-- Area markers (visible in overview) -->
			{#if isOverviewMode}
				{#each areas as area (area.id)}
					<button
						class="area-marker"
						class:active={currentArea === area.id}
						style:left="{area.x}px"
						style:top="{area.y}px"
						style:width="{area.width}px"
						style:height="{area.height}px"
						onclick={() => navigateTo(area.id)}
					>
						<span class="area-name">{area.name}</span>
					</button>
				{/each}
			{/if}

			<!-- Canvas content slot -->
			{@render children?.()}
		</div>
	</GestureProvider>

	<!-- Minimap -->
	{#if enableMinimap && areas.length > 0}
		<div class="minimap">
			<div class="minimap-content">
				{#each areas as area (area.id)}
					<button
						class="minimap-area"
						class:active={currentArea === area.id}
						style:left="{area.x / 20}px"
						style:top="{area.y / 20}px"
						style:width="{Math.max(area.width / 20, 4)}px"
						style:height="{Math.max(area.height / 20, 4)}px"
						onclick={() => navigateTo(area.id)}
						aria-label="Navigate to {area.name}"
					></button>
				{/each}

				<!-- Viewport indicator -->
				<div
					class="minimap-viewport"
					style:left="{-$viewportX / 20}px"
					style:top="{-$viewportY / 20}px"
					style:width="{containerWidth / $viewportZoom / 20}px"
					style:height="{containerHeight / $viewportZoom / 20}px"
				></div>
			</div>
		</div>
	{/if}

	<!-- Zoom controls -->
	<div class="canvas-controls">
		<button
			class="control-btn"
			onclick={() => viewportZoom.update((z) => Math.min(maxZoom, z * 1.25))}
			aria-label="Zoom in"
		>
			+
		</button>
		<span class="zoom-level">{Math.round($viewportZoom * 100)}%</span>
		<button
			class="control-btn"
			onclick={() => viewportZoom.update((z) => Math.max(minZoom, z * 0.8))}
			aria-label="Zoom out"
		>
			−
		</button>
		<button
			class="control-btn"
			onclick={overview}
			aria-label={isOverviewMode ? 'Exit overview' : 'Show overview'}
		>
			{isOverviewMode ? '⊙' : '⊕'}
		</button>
	</div>
</section>

<style>
	.canvas-container {
		position: relative;
		width: 100%;
		height: 100%;
		overflow: hidden;
		background: var(--bg-base, #0a0a0a);
		cursor: default;
		outline: none;
	}

	.canvas-container:focus-visible {
		box-shadow: inset 0 0 0 2px var(--gold, #ffd700);
	}

	.canvas-container.panning {
		cursor: grabbing;
	}

	.canvas-container.overview {
		background:
			radial-gradient(circle at center, rgba(255, 215, 0, 0.02) 0%, transparent 70%),
			var(--bg-base, #0a0a0a);
	}

	.canvas-content {
		position: absolute;
		transform-origin: 0 0;
		will-change: transform;
	}

	/* Area markers (visible in overview) */
	.area-marker {
		position: absolute;
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-md, 8px);
		cursor: pointer;
		transition: all 0.2s ease;
	}

	.area-marker:hover {
		background: rgba(255, 215, 0, 0.05);
		border-color: rgba(255, 215, 0, 0.4);
	}

	.area-marker.active {
		border-color: rgba(255, 215, 0, 0.6);
		box-shadow: 0 0 20px rgba(255, 215, 0, 0.1);
	}

	.area-name {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		padding: var(--space-1, 4px) var(--space-2, 8px);
		background: rgba(10, 10, 10, 0.9);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		font-size: var(--text-xs, 12px);
		white-space: nowrap;
		margin-bottom: var(--space-1, 4px);
	}

	/* Minimap */
	.minimap {
		position: absolute;
		bottom: var(--space-4, 16px);
		right: var(--space-4, 16px);
		width: 150px;
		height: 100px;
		background: rgba(10, 10, 10, 0.8);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-sm, 4px);
		overflow: hidden;
		backdrop-filter: blur(8px);
	}

	.minimap-content {
		position: relative;
		width: 100%;
		height: 100%;
	}

	.minimap-area {
		position: absolute;
		background: rgba(255, 215, 0, 0.3);
		border: none;
		border-radius: 1px;
		cursor: pointer;
		transition: background 0.15s ease;
	}

	.minimap-area:hover {
		background: rgba(255, 215, 0, 0.5);
	}

	.minimap-area.active {
		background: rgba(255, 215, 0, 0.7);
	}

	.minimap-viewport {
		position: absolute;
		border: 1px solid rgba(255, 255, 255, 0.5);
		border-radius: 1px;
		pointer-events: none;
	}

	/* Zoom controls */
	.canvas-controls {
		position: absolute;
		bottom: var(--space-4, 16px);
		left: var(--space-4, 16px);
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		background: rgba(10, 10, 10, 0.8);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-1, 4px);
		backdrop-filter: blur(8px);
	}

	.control-btn {
		width: 28px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		background: transparent;
		border: none;
		border-radius: var(--radius-sm, 4px);
		color: var(--text-secondary, #999);
		font-size: var(--text-lg, 18px);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.control-btn:hover {
		background: rgba(255, 215, 0, 0.1);
		color: var(--text-gold, #ffd700);
	}

	.control-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}

	.zoom-level {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
		min-width: 40px;
		text-align: center;
		font-variant-numeric: tabular-nums;
	}
</style>
