<script lang="ts">
	/**
	 * Toast — Notification component for action feedback (RFC-075)
	 */

	interface ToastProps {
		message: string;
		type?: 'success' | 'error' | 'info';
		duration?: number;
		onClose?: () => void;
	}

	let { message, type = 'success', duration = 3000, onClose }: ToastProps = $props();

	let visible = $state(true);

	$effect(() => {
		const timer = setTimeout(() => {
			visible = false;
			onClose?.();
		}, duration);

		return () => clearTimeout(timer);
	});

	function handleClose() {
		visible = false;
		onClose?.();
	}

	const icons = {
		success: '✓',
		error: '✗',
		info: 'ℹ',
	};
</script>

{#if visible}
	<div class="toast toast-{type}" role="alert" aria-live="polite">
		<span class="icon">{icons[type]}</span>
		<span class="message">{message}</span>
		<button class="close" onclick={handleClose} aria-label="Dismiss">×</button>
	</div>
{/if}

<style>
	.toast {
		display: flex;
		align-items: center;
		gap: var(--space-3, 12px);
		padding: var(--space-3, 12px) var(--space-4, 16px);
		border-radius: var(--radius-md, 8px);
		background: var(--bg-secondary, #1e1e1e);
		border: 1px solid var(--border-subtle, #333);
		box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
		animation: slideIn 0.2s ease-out;
		max-width: 400px;
	}

	.toast-success {
		border-color: rgba(34, 197, 94, 0.5);
	}

	.toast-error {
		border-color: rgba(239, 68, 68, 0.5);
	}

	.toast-info {
		border-color: rgba(59, 130, 246, 0.5);
	}

	.icon {
		font-size: var(--text-lg, 18px);
		font-weight: bold;
	}

	.toast-success .icon {
		color: var(--success, #22c55e);
	}

	.toast-error .icon {
		color: var(--error, #ef4444);
	}

	.toast-info .icon {
		color: var(--info, #3b82f6);
	}

	.message {
		flex: 1;
		color: var(--text-primary, #fff);
		font-size: var(--text-sm, 14px);
	}

	.close {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		font-size: var(--text-lg, 18px);
		padding: 0;
		line-height: 1;
		transition: color 0.15s;
	}

	.close:hover {
		color: var(--text-secondary, #999);
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(-10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}
</style>
