<!--
  FluidCanvasDemo — Showcase of RFC-082 fluid canvas features
  
  Demonstrates:
  - Spring physics animations
  - Spatial memory (minimize/restore)
  - Gesture interactions
  - Shared element transitions
  - Skeleton loading states
  - Canvas navigation
-->
<script lang="ts">
	import { fade } from 'svelte/transition';
	import Canvas from './Canvas.svelte';
	import FluidInput from './FluidInput.svelte';
	import SkeletonLayout from './SkeletonLayout.svelte';
	import MinimizedDock from './MinimizedDock.svelte';
	import GestureProvider from './GestureProvider.svelte';
	import { spatialState, minimizedCount } from '../lib/spatial-state';
	import { sendPanel, receivePanel } from '../lib/shared-element';
	import type { InputMode } from '../lib/tetris';

	// Demo state
	let currentView: 'home' | 'conversation' | 'skeleton' | 'canvas' = $state('home');
	let inputMode: InputMode = $state('hero');
	let showPanel = $state(true);
	let panelId = 'demo-panel';

	// Canvas areas
	const canvasAreas = [
		{ id: 'home', name: 'Home', x: 0, y: 0, width: 800, height: 600 },
		{ id: 'projects', name: 'Projects', x: 900, y: 0, width: 600, height: 400 },
		{ id: 'research', name: 'Research', x: 0, y: 700, width: 700, height: 500 },
	];

	// Demo composition spec
	const demoComposition = {
		page_type: 'conversation',
		panels: [
			{ panel_type: 'calendar', title: 'This Week' },
			{ panel_type: 'tasks', title: 'Tasks' },
		],
		input_mode: 'chat' as const,
		suggested_tools: ['upload', 'voice'],
		confidence: 0.92,
		source: 'regex',
	};

	// Handle input mode transitions
	function cycleInputMode() {
		const modes: InputMode[] = ['hero', 'chat', 'search', 'command'];
		const currentIndex = modes.indexOf(inputMode);
		inputMode = modes[(currentIndex + 1) % modes.length];
	}

	// Handle panel minimize/restore
	function togglePanel() {
		if (showPanel) {
			spatialState.register(panelId, 'panel', {
				x: 100,
				y: 100,
				width: 300,
				height: 400,
				state: 'expanded',
			});
			spatialState.minimize(panelId, 'right');
			showPanel = false;
		} else {
			spatialState.restore(panelId);
			showPanel = true;
		}
	}

	// Handle gestures
	function handleGesture(action: { type: string; direction?: string }) {
		console.log('Gesture:', action);
		if (action.type === 'swipe' && action.direction === 'right') {
			togglePanel();
		}
	}
</script>

<div class="demo-container">
	<header class="demo-header">
		<h1>🌟 Fluid Canvas Demo (RFC-082)</h1>
		<nav class="demo-nav">
			<button
				class:active={currentView === 'home'}
				onclick={() => (currentView = 'home')}
			>
				Home
			</button>
			<button
				class:active={currentView === 'conversation'}
				onclick={() => (currentView = 'conversation')}
			>
				Conversation
			</button>
			<button
				class:active={currentView === 'skeleton'}
				onclick={() => (currentView = 'skeleton')}
			>
				Skeleton
			</button>
			<button
				class:active={currentView === 'canvas'}
				onclick={() => (currentView = 'canvas')}
			>
				Canvas
			</button>
		</nav>
	</header>

	<main class="demo-main">
		{#if currentView === 'home'}
			<section class="demo-section" transition:fade>
				<h2>🎯 Input Mode Transitions</h2>
				<p class="demo-description">
					Click the button to cycle through input modes. Watch the spring physics!
				</p>

				<div class="input-demo">
					<FluidInput mode={inputMode} placeholder="Type something..." />
				</div>

				<div class="demo-controls">
					<button onclick={cycleInputMode}>
						Cycle Mode ({inputMode})
					</button>
					<span class="mode-badge">{inputMode}</span>
				</div>
			</section>

		{:else if currentView === 'conversation'}
			<section class="demo-section" transition:fade>
				<h2>🗂️ Spatial Memory & Dock</h2>
				<p class="demo-description">
					Swipe right or click to minimize the panel. It goes to the dock!
				</p>

				<div class="spatial-demo">
					<GestureProvider
						enableSwipe={true}
						onGesture={handleGesture}
					>
						{#if showPanel}
							<div
								class="demo-panel"
								in:receivePanel={{ key: panelId }}
								out:sendPanel={{ key: panelId }}
							>
								<header class="panel-header">
									<span>📋 Demo Panel</span>
									<button onclick={togglePanel}>✕</button>
								</header>
								<div class="panel-content">
									<p>Swipe right or click ✕ to minimize</p>
									<p>Minimized panels go to the edge dock</p>
								</div>
							</div>
						{/if}
					</GestureProvider>

					<div class="demo-controls">
						<button onclick={togglePanel}>
							{showPanel ? 'Minimize Panel' : 'Restore Panel'}
						</button>
						<span class="count-badge">Minimized: {$minimizedCount}</span>
					</div>
				</div>
			</section>

		{:else if currentView === 'skeleton'}
			<section class="demo-section" transition:fade>
				<h2>⚡ Speculative UI Skeleton</h2>
				<p class="demo-description">
					Skeleton appears instantly while content is loading.
				</p>

				<div class="skeleton-demo">
					<SkeletonLayout
						composition={demoComposition}
						streaming={true}
						loading={true}
					/>
				</div>
			</section>

		{:else if currentView === 'canvas'}
			<section class="demo-section canvas-section" transition:fade>
				<h2>🎨 Infinite Canvas</h2>
				<p class="demo-description">
					Pan with Shift+drag or middle mouse. Zoom with scroll. Click areas to navigate.
				</p>

				<div class="canvas-demo">
					<Canvas
						areas={canvasAreas}
						initialArea="home"
						enableMinimap={true}
					>
						{#each canvasAreas as area (area.id)}
							<div
								class="canvas-area-content"
								style:position="absolute"
								style:left="{area.x}px"
								style:top="{area.y}px"
								style:width="{area.width}px"
								style:height="{area.height}px"
							>
								<h3>{area.name}</h3>
								<p>This is the {area.name} area</p>
							</div>
						{/each}
					</Canvas>
				</div>
			</section>
		{/if}
	</main>

	<!-- Minimized dock (always visible) -->
	<MinimizedDock edge="right" />
</div>

<style>
	.demo-container {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		background: var(--bg-base, #0a0a0a);
		color: var(--text-primary, #fff);
	}

	.demo-header {
		padding: var(--space-4, 16px);
		border-bottom: 1px solid rgba(255, 215, 0, 0.1);
	}

	.demo-header h1 {
		margin: 0 0 var(--space-3, 12px);
		font-size: var(--text-xl, 20px);
		font-weight: 500;
	}

	.demo-nav {
		display: flex;
		gap: var(--space-2, 8px);
	}

	.demo-nav button {
		padding: var(--space-2, 8px) var(--space-4, 16px);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-md, 8px);
		color: var(--text-secondary, #999);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.demo-nav button:hover {
		background: rgba(255, 215, 0, 0.05);
		border-color: rgba(255, 215, 0, 0.3);
		color: var(--text-primary, #fff);
	}

	.demo-nav button.active {
		background: rgba(255, 215, 0, 0.1);
		border-color: rgba(255, 215, 0, 0.4);
		color: var(--text-gold, #ffd700);
	}

	.demo-main {
		flex: 1;
		padding: var(--space-6, 24px);
	}

	.demo-section {
		max-width: 800px;
		margin: 0 auto;
	}

	.demo-section h2 {
		margin: 0 0 var(--space-2, 8px);
		font-size: var(--text-lg, 18px);
		font-weight: 500;
	}

	.demo-description {
		color: var(--text-secondary, #999);
		margin: 0 0 var(--space-4, 16px);
	}

	.demo-controls {
		display: flex;
		gap: var(--space-3, 12px);
		align-items: center;
		margin-top: var(--space-4, 16px);
	}

	.demo-controls button {
		padding: var(--space-2, 8px) var(--space-4, 16px);
		background: rgba(255, 215, 0, 0.1);
		border: 1px solid rgba(255, 215, 0, 0.3);
		border-radius: var(--radius-md, 8px);
		color: var(--text-gold, #ffd700);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.demo-controls button:hover {
		background: rgba(255, 215, 0, 0.2);
	}

	.mode-badge, .count-badge {
		padding: var(--space-1, 4px) var(--space-3, 12px);
		background: rgba(255, 255, 255, 0.05);
		border-radius: var(--radius-full, 9999px);
		font-size: var(--text-sm, 14px);
		color: var(--text-tertiary, #666);
	}

	/* Input demo */
	.input-demo {
		display: flex;
		justify-content: center;
		padding: var(--space-6, 24px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg, 12px);
		min-height: 150px;
		align-items: center;
	}

	/* Spatial demo */
	.spatial-demo {
		padding: var(--space-4, 16px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg, 12px);
		min-height: 300px;
	}

	.demo-panel {
		width: 300px;
		background: rgba(10, 10, 10, 0.9);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-md, 8px);
		overflow: hidden;
	}

	.demo-panel .panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-2, 8px) var(--space-3, 12px);
		background: rgba(255, 255, 255, 0.03);
		border-bottom: 1px solid rgba(255, 215, 0, 0.1);
	}

	.demo-panel .panel-header button {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		padding: var(--space-1, 4px);
	}

	.demo-panel .panel-header button:hover {
		color: var(--text-gold, #ffd700);
	}

	.demo-panel .panel-content {
		padding: var(--space-4, 16px);
		color: var(--text-secondary, #999);
	}

	.demo-panel .panel-content p {
		margin: 0 0 var(--space-2, 8px);
	}

	/* Skeleton demo */
	.skeleton-demo {
		padding: var(--space-4, 16px);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg, 12px);
	}

	/* Canvas demo */
	.canvas-section {
		max-width: 100%;
	}

	.canvas-demo {
		height: 500px;
		border-radius: var(--radius-lg, 12px);
		overflow: hidden;
		border: 1px solid var(--border-subtle, #333);
	}

	.canvas-area-content {
		background: rgba(255, 255, 255, 0.02);
		border: 1px dashed rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-4, 16px);
	}

	.canvas-area-content h3 {
		margin: 0 0 var(--space-2, 8px);
		color: var(--text-gold, #ffd700);
	}

	.canvas-area-content p {
		margin: 0;
		color: var(--text-secondary, #999);
	}
</style>
