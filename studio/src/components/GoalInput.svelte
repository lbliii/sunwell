<script lang="ts">
	import { processInput, interfaceState } from '../stores/interface.svelte';
	import { parseError, getCategoryIcon } from '$lib/error';
	import ErrorDisplay from './ui/ErrorDisplay.svelte';

	let inputValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();

	// Parse error into structured format
	const parsedError = $derived(interfaceState.error ? parseError(interfaceState.error) : null);

	async function handleSubmit() {
		const goal = inputValue.trim();
		if (!goal) return;

		inputValue = '';
		await processInput(goal);
	}

	function handleKeydown(e: KeyboardEvent) {
		if (e.key === 'Enter' && !e.shiftKey) {
			e.preventDefault();
			handleSubmit();
		}
	}

	// Focus input on mount
	$effect(() => {
		if (inputEl) {
			inputEl.focus();
		}
	});
</script>

<div class="goal-input" class:analyzing={interfaceState.isAnalyzing}>
	<div class="input-wrapper">
		<input
			bind:this={inputEl}
			bind:value={inputValue}
			onkeydown={handleKeydown}
			placeholder="What would you like to do?"
			disabled={interfaceState.isAnalyzing}
		/>

		<button
			onclick={handleSubmit}
			disabled={interfaceState.isAnalyzing || !inputValue.trim()}
			class="submit-btn"
		>
			{#if interfaceState.isAnalyzing}
				<span class="spinner"></span>
			{:else}
				<svg
					width="20"
					height="20"
					viewBox="0 0 24 24"
					fill="none"
					stroke="currentColor"
					stroke-width="2"
				>
					<path d="M22 2L11 13" />
					<path d="M22 2L15 22L11 13L2 9L22 2Z" />
				</svg>
			{/if}
		</button>
	</div>

	{#if parsedError}
		<div class="error-container">
			<ErrorDisplay error={parsedError} compact />
		</div>
	{/if}
</div>

<style>
	.goal-input {
		width: 100%;
		max-width: 600px;
	}

	.input-wrapper {
		display: flex;
		gap: var(--spacing-sm);
		padding: var(--spacing-md);
		background: var(--bg-secondary);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border-subtle);
		transition: border-color 0.2s, box-shadow 0.2s;
	}

	.input-wrapper:focus-within {
		border-color: var(--gold);
		box-shadow: 0 0 0 2px var(--radiant-gold-10);
	}

	.goal-input.analyzing .input-wrapper {
		opacity: 0.8;
	}

	input {
		flex: 1;
		background: transparent;
		border: none;
		color: var(--text-primary);
		font-size: var(--font-size-md, 16px);
		outline: none;
		font-family: inherit;
	}

	input::placeholder {
		color: var(--text-tertiary);
	}

	input:disabled {
		cursor: not-allowed;
	}

	.submit-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--spacing-sm) var(--spacing-md);
		background: var(--gold);
		color: var(--bg-primary);
		border: none;
		border-radius: var(--radius-md);
		font-weight: 600;
		cursor: pointer;
		transition: opacity 0.2s, transform 0.1s;
	}

	.submit-btn:hover:not(:disabled) {
		opacity: 0.9;
		transform: scale(1.02);
	}

	.submit-btn:active:not(:disabled) {
		transform: scale(0.98);
	}

	.submit-btn:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.spinner {
		display: inline-block;
		width: 16px;
		height: 16px;
		border: 2px solid var(--bg-primary);
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.error-container {
		margin-top: var(--spacing-sm);
	}
</style>
