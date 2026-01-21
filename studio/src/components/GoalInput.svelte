<script lang="ts">
	import { processInput, interfaceState } from '../stores/interface.svelte';

	let inputValue = $state('');
	let inputEl: HTMLInputElement | undefined = $state();

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

	{#if interfaceState.error}
		<div class="error-message">
			{interfaceState.error}
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
		gap: var(--spacing-sm, 8px);
		padding: var(--spacing-md, 12px);
		background: var(--bg-secondary, #1e1e1e);
		border-radius: var(--radius-lg, 12px);
		border: 1px solid var(--border-subtle, #333);
		transition: border-color 0.2s, box-shadow 0.2s;
	}

	.input-wrapper:focus-within {
		border-color: var(--gold, #ffd700);
		box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.1);
	}

	.goal-input.analyzing .input-wrapper {
		opacity: 0.8;
	}

	input {
		flex: 1;
		background: transparent;
		border: none;
		color: var(--text-primary, #fff);
		font-size: var(--font-size-md, 16px);
		outline: none;
		font-family: inherit;
	}

	input::placeholder {
		color: var(--text-tertiary, #666);
	}

	input:disabled {
		cursor: not-allowed;
	}

	.submit-btn {
		display: flex;
		align-items: center;
		justify-content: center;
		padding: var(--spacing-sm, 8px) var(--spacing-md, 12px);
		background: var(--gold, #ffd700);
		color: var(--bg-primary, #0a0a0a);
		border: none;
		border-radius: var(--radius-md, 8px);
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
		border: 2px solid var(--bg-primary, #0a0a0a);
		border-top-color: transparent;
		border-radius: 50%;
		animation: spin 0.8s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	.error-message {
		margin-top: var(--spacing-sm, 8px);
		padding: var(--spacing-sm, 8px) var(--spacing-md, 12px);
		background: rgba(239, 68, 68, 0.1);
		border: 1px solid rgba(239, 68, 68, 0.3);
		border-radius: var(--radius-md, 8px);
		color: var(--error, #ef4444);
		font-size: var(--font-size-sm, 14px);
	}
</style>
