<!--
  FluidInput — Context-aware morphing input (RFC-080 + RFC-082)
  
  A single input that flows through the UI based on context:
  - Hero: Large, centered (home state)
  - Chat: Bottom-anchored (conversation state)
  - Search: Compact, top-left (explorer state)
  - Command: Minimal, floating (workspace state)
  
  Uses spring physics for smooth mode transitions (RFC-082).
-->
<script lang="ts">
	import { onMount } from 'svelte';
	import { scale } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import RisingMotes from './RisingMotes.svelte';
	import { getInputModeTransitionSpring, type InputMode } from '../lib/tetris';

	interface Props {
		value?: string;
		mode?: InputMode;
		placeholder?: string;
		loading?: boolean;
		disabled?: boolean;
		onsubmit?: (value: string) => void;
	}

	let {
		value = $bindable(''),
		mode = 'hero',
		placeholder,
		loading = false,
		disabled = false,
		onsubmit,
	}: Props = $props();

	let inputEl: HTMLInputElement | undefined = $state();
	let focused = $state(false);
	// svelte-ignore state_referenced_locally - intentionally capturing initial mode for change tracking
	let previousMode: InputMode = $state(mode);

	// Spring-animated scale for mode transitions
	const inputScale = spring(1, { stiffness: 0.15, damping: 0.5 });
	const inputWidth = spring(600, { stiffness: 0.12, damping: 0.4 });
	const inputPadding = spring(16, { stiffness: 0.15, damping: 0.5 });

	// Mode-specific placeholders
	const placeholders: Record<InputMode, string> = {
		hero: 'What would you like to create?',
		chat: 'Continue the conversation...',
		search: 'Search...',
		command: 'Ask anything...',
		hidden: '',
	};

	// Mode-specific widths (in pixels)
	const modeWidths: Record<InputMode, number> = {
		hero: 600,
		chat: 500,
		search: 240,
		command: 200,
		hidden: 0,
	};

	// Mode-specific padding
	const modePaddings: Record<InputMode, number> = {
		hero: 16,
		chat: 8,
		search: 4,
		command: 4,
		hidden: 0,
	};

	let effectivePlaceholder = $derived(placeholder || placeholders[mode]);
	let isDisabled = $derived(disabled || loading);

	// React to mode changes with spring animation
	$effect(() => {
		if (mode !== previousMode) {
			const springConfig = getInputModeTransitionSpring(previousMode, mode);
			inputScale.stiffness = springConfig.stiffness / 1000;
			inputScale.damping = springConfig.damping / 50;
			inputWidth.stiffness = springConfig.stiffness / 1000;
			inputWidth.damping = springConfig.damping / 50;

			// Animate through a slight scale down then up
			inputScale.set(0.95);
			setTimeout(() => inputScale.set(1), 100);

			// Animate width and padding
			inputWidth.set(modeWidths[mode]);
			inputPadding.set(modePaddings[mode]);

			previousMode = mode;
		}
	});

	// Focus animation
	$effect(() => {
		if (focused && mode === 'search') {
			inputWidth.set(320);
		} else if (!focused && mode === 'search') {
			inputWidth.set(modeWidths.search);
		}
	});

	function handleSubmit() {
		if (value.trim() && !isDisabled) {
			onsubmit?.(value.trim());
		}
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
		// Escape to blur in non-hero modes
		if (e.key === 'Escape' && mode !== 'hero') {
			inputEl?.blur();
		}
	}

	// Programmatic autofocus to avoid browser conflicts
	onMount(() => {
		if (mode === 'hero' && inputEl) {
			inputEl.focus();
		}
	});

	export function focus() {
		inputEl?.focus();
	}

	export function blur() {
		inputEl?.blur();
	}
</script>

{#if mode !== 'hidden'}
	<div
		class="fluid-input mode-{mode}"
		class:focused
		class:loading
		class:disabled={isDisabled}
		style:transform="scale({$inputScale})"
		style:max-width="{$inputWidth}px"
		style:--input-padding="{$inputPadding}px"
		transition:scale={{ duration: 200 }}
	>
		{#if mode === 'hero'}
			<!-- Hero mode: Large with motes -->
			<div class="input-glow"></div>
		{/if}

		<div class="input-container">
			{#if mode === 'search'}
				<span class="search-icon" aria-hidden="true">🔍</span>
			{/if}

			<input
				bind:this={inputEl}
				bind:value
				placeholder={effectivePlaceholder}
				disabled={isDisabled}
				onkeydown={handleKeydown}
				onfocus={() => (focused = true)}
				onblur={() => (focused = false)}
				type="text"
				spellcheck="false"
				autocomplete="off"
				aria-label={effectivePlaceholder}
			/>

			<button
				class="submit-btn"
				onclick={handleSubmit}
				disabled={isDisabled}
				aria-label={loading ? 'Processing...' : 'Send'}
				type="button"
			>
				{#if loading}
					<span class="loading-spinner">⟳</span>
				{:else if mode === 'chat'}
					<span class="send-icon">↑</span>
				{:else if mode === 'search'}
					<span class="go-icon">→</span>
				{:else}
					<span class="enter-icon">⏎</span>
				{/if}
			</button>
		</div>

		{#if mode === 'hero' && focused}
			<div class="motes-container">
				<RisingMotes count={5} intensity="subtle" active={true} />
			</div>
		{/if}
	</div>
{/if}

<style>
	.fluid-input {
		position: relative;
		/* Spring physics handles transitions via inline styles */
		will-change: transform, max-width;
	}

	/* ══════════════════════════════════════════════════════════════
	   HERO MODE — Large, centered, dramatic
	   ══════════════════════════════════════════════════════════════ */
	.mode-hero {
		width: 100%;
	}

	.mode-hero .input-container {
		padding: 0 var(--input-padding, 16px);
		background: var(--bg-input, #111);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-lg);
	}

	.mode-hero input {
		padding: var(--input-padding, 16px) 0;
		font-size: var(--text-base);
	}

	.mode-hero.focused .input-container {
		border-color: var(--border-emphasis, var(--radiant-gold-40));
		box-shadow: var(--glow-gold-inset, 0 0 20px var(--radiant-gold-10) inset);
	}

	.mode-hero .input-glow {
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

	.mode-hero.focused .input-glow {
		opacity: 1;
	}

	.motes-container {
		position: absolute;
		bottom: 100%;
		left: 50%;
		transform: translateX(-50%);
		width: 200px;
		height: 100px;
		pointer-events: none;
	}

	/* ══════════════════════════════════════════════════════════════
	   CHAT MODE — Bottom-anchored, conversation style
	   ══════════════════════════════════════════════════════════════ */
	.mode-chat {
		width: 100%;
	}

	.mode-chat .input-container {
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-full);
	}

	.mode-chat input {
		padding: var(--space-2) 0;
		font-size: var(--text-sm);
	}

	.mode-chat.focused .input-container {
		border-color: var(--radiant-gold-30);
		background: rgba(255, 255, 255, 0.05);
	}

	.mode-chat .submit-btn {
		width: 28px;
		height: 28px;
		background: var(--gold);
		color: var(--bg-primary);
		border-radius: 50%;
	}

	.mode-chat .submit-btn:hover:not(:disabled) {
		background: var(--gold-light);
		transform: scale(1.05);
	}

	.send-icon {
		font-weight: bold;
	}

	/* ══════════════════════════════════════════════════════════════
	   SEARCH MODE — Compact, top-positioned
	   ══════════════════════════════════════════════════════════════ */
	.mode-search {
		width: 100%;
	}

	.mode-search .input-container {
		padding: var(--input-padding, 4px) var(--space-2);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
	}

	.mode-search input {
		padding: var(--input-padding, 4px) 0;
		font-size: var(--text-sm);
	}

	.mode-search.focused .input-container {
		border-color: var(--radiant-gold-30);
	}

	.search-icon {
		color: var(--text-tertiary);
		font-size: var(--text-sm);
		margin-right: var(--space-1);
	}

	.mode-search .submit-btn {
		width: 24px;
		height: 24px;
	}

	/* ══════════════════════════════════════════════════════════════
	   COMMAND MODE — Minimal, floating
	   ══════════════════════════════════════════════════════════════ */
	.mode-command {
		width: 100%;
	}

	.mode-command .input-container {
		padding: var(--input-padding, 4px) var(--space-2);
		background: rgba(0, 0, 0, 0.8);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		backdrop-filter: blur(8px);
	}

	.mode-command input {
		padding: var(--input-padding, 4px) 0;
		font-size: var(--text-xs);
		font-family: var(--font-mono);
	}

	.mode-command .submit-btn {
		width: 20px;
		height: 20px;
		font-size: var(--text-xs);
	}

	/* ══════════════════════════════════════════════════════════════
	   SHARED STYLES
	   ══════════════════════════════════════════════════════════════ */
	.input-container {
		display: flex;
		align-items: center;
		transition: all 0.2s ease;
	}

	input {
		flex: 1;
		background: transparent;
		border: none;
		outline: none;
		color: var(--text-primary);
		font-family: var(--font-mono);
		min-width: 0;
	}

	input::placeholder {
		color: var(--text-tertiary);
	}

	input:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.submit-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		margin-left: var(--space-2);
		color: var(--text-tertiary);
		border-radius: var(--radius-sm);
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.submit-btn:hover:not(:disabled) {
		color: var(--text-gold);
		background: var(--radiant-gold-10);
	}

	.submit-btn:disabled {
		cursor: not-allowed;
		opacity: 0.5;
	}

	.loading-spinner {
		display: inline-block;
		animation: spin 1s linear infinite;
		color: var(--text-gold);
	}

	@keyframes spin {
		from {
			transform: rotate(0deg);
		}
		to {
			transform: rotate(360deg);
		}
	}

	/* Disabled state */
	.fluid-input.disabled {
		opacity: 0.6;
		pointer-events: none;
	}
</style>
