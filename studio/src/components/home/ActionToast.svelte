<!--
  ActionToast — Action feedback toast (RFC-080)
  
  Shows confirmation or error feedback for executed actions.
  Auto-dismisses after a timeout.
-->
<script lang="ts">
	import { fly, fade } from 'svelte/transition';

	interface Props {
		actionType: string;
		success: boolean;
		message: string;
		duration?: number;
		onDismiss?: () => void;
	}

	let { actionType, success, message, duration = 4000, onDismiss }: Props = $props();

	let visible = $state(true);

	// Auto-dismiss after duration
	$effect(() => {
		const timer = setTimeout(() => {
			visible = false;
			setTimeout(() => onDismiss?.(), 300);
		}, duration);

		return () => clearTimeout(timer);
	});

	function handleDismiss() {
		visible = false;
		setTimeout(() => onDismiss?.(), 300);
	}

	function getIcon(): string {
		return success ? '✓' : '✕';
	}
</script>

{#if visible}
	<div
		class="action-toast"
		class:success
		class:error={!success}
		in:fly={{ y: -20, duration: 250 }}
		out:fade={{ duration: 200 }}
		role="alert"
		aria-live="polite"
	>
		<span class="toast-icon" aria-hidden="true">{getIcon()}</span>
		<div class="toast-content">
			<span class="toast-action">{actionType}</span>
			<span class="toast-message">{message}</span>
		</div>
		<button class="dismiss-btn" onclick={handleDismiss} aria-label="Dismiss">
			<span aria-hidden="true">✕</span>
		</button>

		<!-- Progress bar -->
		<div class="progress-bar">
			<div class="progress-fill" style="animation-duration: {duration}ms"></div>
		</div>
	</div>
{/if}

<style>
	.action-toast {
		position: fixed;
		top: var(--space-4);
		right: var(--space-4);
		display: flex;
		align-items: center;
		gap: var(--space-3);
		padding: var(--space-3) var(--space-4);
		background: var(--bg-secondary);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border-subtle);
		box-shadow:
			0 4px 24px rgba(0, 0, 0, 0.4),
			0 0 40px rgba(0, 0, 0, 0.2);
		z-index: 1000;
		min-width: 280px;
		max-width: 400px;
		overflow: hidden;
	}

	.action-toast.success {
		border-color: rgba(34, 197, 94, 0.3);
	}

	.action-toast.error {
		border-color: rgba(239, 68, 68, 0.3);
	}

	.toast-icon {
		width: 28px;
		height: 28px;
		display: flex;
		align-items: center;
		justify-content: center;
		border-radius: 50%;
		font-weight: bold;
		flex-shrink: 0;
	}

	.success .toast-icon {
		background: rgba(34, 197, 94, 0.15);
		color: var(--success);
	}

	.error .toast-icon {
		background: rgba(239, 68, 68, 0.15);
		color: var(--error);
	}

	.toast-content {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.toast-action {
		color: var(--text-tertiary);
		font-size: var(--text-xs);
		text-transform: capitalize;
	}

	.toast-message {
		color: var(--text-primary);
		font-size: var(--text-sm);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: var(--text-tertiary);
		cursor: pointer;
		padding: var(--space-1);
		border-radius: var(--radius-sm);
		transition: all 0.15s ease;
		flex-shrink: 0;
	}

	.dismiss-btn:hover {
		color: var(--text-primary);
		background: rgba(255, 255, 255, 0.05);
	}

	.dismiss-btn:focus-visible {
		outline: 2px solid var(--gold);
		outline-offset: 2px;
	}

	/* Progress bar */
	.progress-bar {
		position: absolute;
		bottom: 0;
		left: 0;
		right: 0;
		height: 3px;
		background: rgba(255, 255, 255, 0.05);
	}

	.progress-fill {
		height: 100%;
		animation: shrink linear forwards;
	}

	.success .progress-fill {
		background: var(--success);
	}

	.error .progress-fill {
		background: var(--error);
	}

	@keyframes shrink {
		from {
			width: 100%;
		}
		to {
			width: 0;
		}
	}
</style>
