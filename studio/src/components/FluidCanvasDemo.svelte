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
		background: var(--bg-primary);
		color: var(--text-primary);
	}

	.demo-header {
		padding: var(--space-4);
		border-bottom: 1px solid var(--radiant-gold-10);
	}

	.demo-header h1 {
		margin: 0 0 var(--space-3);
		font-size: var(--text-xl);
		font-weight: 500;
	}

	.demo-nav {
		display: flex;
		gap: var(--space-2);
	}

	.demo-nav button {
		padding: var(--space-2) var(--space-4);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		color: var(--text-secondary);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.demo-nav button:hover {
		background: var(--radiant-gold-5);
		border-color: var(--radiant-gold-30);
		color: var(--text-primary);
	}

	.demo-nav button.active {
		background: var(--radiant-gold-10);
		border-color: var(--radiant-gold-40);
		color: var(--text-gold);
	}

	.demo-main {
		flex: 1;
		padding: var(--space-6);
	}

	.demo-section {
		max-width: 800px;
		margin: 0 auto;
	}

	.demo-section h2 {
		margin: 0 0 var(--space-2);
		font-size: var(--text-lg);
		font-weight: 500;
	}

	.demo-description {
		color: var(--text-secondary);
		margin: 0 0 var(--space-4);
	}

	.demo-controls {
		display: flex;
		gap: var(--space-3);
		align-items: center;
		margin-top: var(--space-4);
	}

	.demo-controls button {
		padding: var(--space-2) var(--space-4);
		background: var(--radiant-gold-10);
		border: 1px solid var(--radiant-gold-30);
		border-radius: var(--radius-md);
		color: var(--text-gold);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.demo-controls button:hover {
		background: var(--radiant-gold-20);
	}

	.mode-badge, .count-badge {
		padding: var(--space-1) var(--space-3);
		background: rgba(255, 255, 255, 0.05);
		border-radius: var(--radius-full);
		font-size: var(--text-sm);
		color: var(--text-tertiary);
	}

	/* Input demo */
	.input-demo {
		display: flex;
		justify-content: center;
		padding: var(--space-6);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg);
		min-height: 150px;
		align-items: center;
	}

	/* Spatial demo */
	.spatial-demo {
		padding: var(--space-4);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg);
		min-height: 300px;
	}

	.demo-panel {
		width: 300px;
		background: rgba(10, 10, 10, 0.9);
		border: 1px solid var(--radiant-gold-20);
		border-radius: var(--radius-md);
		overflow: hidden;
	}

	.demo-panel .panel-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.03);
		border-bottom: 1px solid var(--radiant-gold-10);
	}

	.demo-panel .panel-header button {
		background: none;
		border: none;
		color: var(--text-tertiary);
		cursor: pointer;
		padding: var(--space-1);
	}

	.demo-panel .panel-header button:hover {
		color: var(--text-gold);
	}

	.demo-panel .panel-content {
		padding: var(--space-4);
		color: var(--text-secondary);
	}

	.demo-panel .panel-content p {
		margin: 0 0 var(--space-2);
	}

	/* Skeleton demo */
	.skeleton-demo {
		padding: var(--space-4);
		background: rgba(255, 255, 255, 0.02);
		border-radius: var(--radius-lg);
	}

	/* Canvas demo */
	.canvas-section {
		max-width: 100%;
	}

	.canvas-demo {
		height: 500px;
		border-radius: var(--radius-lg);
		overflow: hidden;
		border: 1px solid var(--border-subtle);
	}

	.canvas-area-content {
		background: rgba(255, 255, 255, 0.02);
		border: 1px dashed var(--radiant-gold-20);
		border-radius: var(--radius-md);
		padding: var(--space-4);
	}

	.canvas-area-content h3 {
		margin: 0 0 var(--space-2);
		color: var(--text-gold);
	}

	.canvas-area-content p {
		margin: 0;
		color: var(--text-secondary);
	}
</style>
