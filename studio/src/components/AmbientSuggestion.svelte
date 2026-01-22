<script lang="ts">
	/**
	 * AmbientSuggestion — Proactive suggestion UI (RFC-082 Phase 6)
	 *
	 * Displays non-intrusive suggestions that fade in when relevant.
	 * Designed to be ambient - present but not demanding attention.
	 */
	import { fly, fade, scale } from 'svelte/transition';
	import { spring } from 'svelte/motion';
	import { backOut } from 'svelte/easing';
	import {
		suggestionState,
		acceptSuggestion,
		dismissSuggestion,
		dismissAll,
		type Suggestion,
	} from '../stores/suggestions.svelte';

	// Spring for hover effects
	const hoverScale = spring(1, { stiffness: 300, damping: 20 });

	// Track which suggestion is being hovered
	let hoveredId = $state<string | null>(null);

	async function handleAccept(suggestion: Suggestion) {
		await acceptSuggestion(suggestion.id);
	}

	function handleDismiss(suggestion: Suggestion) {
		dismissSuggestion(suggestion.id);
	}

	function handleDismissAll() {
		dismissAll();
	}

	// Update spring on hover
	$effect(() => {
		hoverScale.set(hoveredId ? 1.02 : 1);
	});
</script>

{#if suggestionState.suggestions.length > 0}
	<div class="ambient-suggestions" transition:fade={{ duration: 200 }}>
		{#each suggestionState.suggestions as suggestion, i (suggestion.id)}
			<div
				class="suggestion"
				class:hovered={hoveredId === suggestion.id}
				role="button"
				tabindex="0"
				onmouseenter={() => (hoveredId = suggestion.id)}
				onmouseleave={() => (hoveredId = null)}
				onfocus={() => (hoveredId = suggestion.id)}
				onblur={() => (hoveredId = null)}
				transition:fly={{ y: 20, delay: i * 50, duration: 300, easing: backOut }}
			>
				<span class="suggestion-icon" transition:scale={{ delay: i * 50 + 100 }}>
					{suggestion.icon}
				</span>

				<div class="suggestion-content">
					<span class="suggestion-text">{suggestion.text}</span>
					{#if suggestion.subtext}
						<span class="suggestion-subtext">{suggestion.subtext}</span>
					{/if}
				</div>

				<div class="suggestion-actions">
					<button
						class="action-yes"
						onclick={() => handleAccept(suggestion)}
						aria-label="Accept suggestion"
					>
						Yes
					</button>
					<button
						class="action-dismiss"
						onclick={() => handleDismiss(suggestion)}
						aria-label="Dismiss suggestion"
					>
						Not now
					</button>
				</div>

				<!-- Confidence indicator -->
				<div
					class="confidence-bar"
					style:width="{suggestion.confidence * 100}%"
					aria-label="Confidence: {Math.round(suggestion.confidence * 100)}%"
				></div>
			</div>
		{/each}

		<!-- Dismiss all link (if multiple suggestions) -->
		{#if suggestionState.suggestions.length > 1}
			<button class="dismiss-all" onclick={handleDismissAll} transition:fade={{ delay: 200 }}>
				Dismiss all suggestions
			</button>
		{/if}
	</div>
{/if}

<style>
	.ambient-suggestions {
		position: fixed;
		bottom: 5rem;
		right: 1.5rem;
		display: flex;
		flex-direction: column;
		gap: 0.75rem;
		z-index: 100;
		max-width: 24rem;
		pointer-events: auto;
	}

	.suggestion {
		position: relative;
		display: flex;
		align-items: flex-start;
		gap: 0.75rem;
		padding: 0.875rem 1rem;
		background: var(--surface-elevated, hsl(220 20% 14%));
		border-radius: 0.75rem;
		border: 1px solid var(--border-subtle, hsl(220 15% 22%));
		box-shadow:
			0 4px 12px rgba(0, 0, 0, 0.15),
			0 2px 4px rgba(0, 0, 0, 0.1);
		cursor: pointer;
		transition:
			transform 0.15s ease,
			box-shadow 0.15s ease,
			border-color 0.15s ease;
		overflow: hidden;
	}

	.suggestion.hovered {
		transform: translateY(-2px);
		box-shadow:
			0 8px 20px rgba(0, 0, 0, 0.2),
			0 4px 8px rgba(0, 0, 0, 0.15);
		border-color: var(--accent-subtle, hsl(210 60% 40%));
	}

	.suggestion-icon {
		font-size: 1.5rem;
		line-height: 1;
		flex-shrink: 0;
	}

	.suggestion-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 0.25rem;
		min-width: 0;
	}

	.suggestion-text {
		font-size: 0.875rem;
		font-weight: 500;
		color: var(--text-primary, hsl(0 0% 95%));
		line-height: 1.4;
	}

	.suggestion-subtext {
		font-size: 0.75rem;
		color: var(--text-secondary, hsl(0 0% 60%));
		line-height: 1.4;
	}

	.suggestion-actions {
		display: flex;
		gap: 0.5rem;
		flex-shrink: 0;
	}

	.suggestion-actions button {
		padding: 0.375rem 0.75rem;
		border-radius: 0.375rem;
		font-size: 0.75rem;
		font-weight: 500;
		cursor: pointer;
		transition:
			background 0.15s ease,
			transform 0.1s ease;
		border: none;
	}

	.suggestion-actions button:active {
		transform: scale(0.95);
	}

	.action-yes {
		background: var(--accent-primary, hsl(210 60% 50%));
		color: white;
	}

	.action-yes:hover {
		background: var(--accent-hover, hsl(210 60% 55%));
	}

	.action-dismiss {
		background: transparent;
		color: var(--text-secondary, hsl(0 0% 60%));
		border: 1px solid var(--border-subtle, hsl(220 15% 25%)) !important;
	}

	.action-dismiss:hover {
		background: var(--surface-hover, hsl(220 20% 18%));
		color: var(--text-primary, hsl(0 0% 90%));
	}

	.confidence-bar {
		position: absolute;
		bottom: 0;
		left: 0;
		height: 2px;
		background: linear-gradient(
			90deg,
			var(--accent-primary, hsl(210 60% 50%)),
			var(--accent-secondary, hsl(280 60% 50%))
		);
		opacity: 0.5;
		transition: opacity 0.15s ease;
	}

	.suggestion.hovered .confidence-bar {
		opacity: 0.8;
	}

	.dismiss-all {
		align-self: flex-end;
		padding: 0.25rem 0.5rem;
		font-size: 0.7rem;
		color: var(--text-tertiary, hsl(0 0% 45%));
		background: transparent;
		border: none;
		cursor: pointer;
		opacity: 0.7;
		transition: opacity 0.15s ease;
	}

	.dismiss-all:hover {
		opacity: 1;
		color: var(--text-secondary, hsl(0 0% 60%));
	}

	/* Responsive */
	@media (max-width: 640px) {
		.ambient-suggestions {
			left: 1rem;
			right: 1rem;
			max-width: none;
		}

		.suggestion {
			flex-wrap: wrap;
		}

		.suggestion-actions {
			width: 100%;
			justify-content: flex-end;
			margin-top: 0.5rem;
		}
	}

	/* Reduced motion */
	@media (prefers-reduced-motion: reduce) {
		.suggestion {
			transition: none;
		}

		.suggestion.hovered {
			transform: none;
		}
	}
</style>
