<!--
  ConversationBlock — AI conversation response (RFC-080)
  
  Displays conversational responses with:
  - Mode indicator (informational, empathetic, collaborative)
  - Follow-up prompt
  - Dismiss action
-->
<script lang="ts">
	import { fly, fade } from 'svelte/transition';

	interface Props {
		message: string;
		mode?: 'informational' | 'empathetic' | 'collaborative';
		onAction?: (actionId: string) => void;
	}

	let { message, mode = 'informational', onAction }: Props = $props();

	function getModeEmoji(m: string): string {
		switch (m) {
			case 'informational':
				return '💬';
			case 'empathetic':
				return '💜';
			case 'collaborative':
				return '🤝';
			default:
				return '💬';
		}
	}

	function getModeLabel(m: string): string {
		switch (m) {
			case 'informational':
				return 'Info';
			case 'empathetic':
				return 'Support';
			case 'collaborative':
				return 'Collaborate';
			default:
				return 'Response';
		}
	}

	function handleFollowUp() {
		onAction?.('follow_up');
	}

	function handleDismiss() {
		onAction?.('dismiss');
	}
</script>

<div class="conversation-block" in:fly={{ y: 30, duration: 300 }}>
	<div class="conversation-header">
		<div class="mode-badge">
			<span class="mode-emoji" aria-hidden="true">{getModeEmoji(mode)}</span>
			<span class="mode-label">{getModeLabel(mode)}</span>
		</div>
		<button class="dismiss-btn" onclick={handleDismiss} aria-label="Dismiss">
			<span aria-hidden="true">✕</span>
		</button>
	</div>

	<div class="conversation-content">
		<p class="message-text">{message}</p>
	</div>

	<div class="conversation-actions">
		<button class="action-btn follow-up" onclick={handleFollowUp}>
			Ask more
		</button>
	</div>
</div>

<style>
	.conversation-block {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
		padding: var(--space-4, 16px);
		background: linear-gradient(
			135deg,
			rgba(255, 215, 0, 0.05) 0%,
			rgba(10, 10, 10, 0.95) 100%
		);
		border: 1px solid rgba(255, 215, 0, 0.15);
		border-radius: var(--radius-lg, 12px);
		margin-top: var(--space-4, 16px);
		width: 100%;
		max-width: 600px;
	}

	.conversation-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.mode-badge {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		padding: var(--space-1, 4px) var(--space-2, 8px);
		background: rgba(255, 215, 0, 0.1);
		border-radius: var(--radius-sm, 4px);
	}

	.mode-emoji {
		font-size: var(--text-lg, 18px);
	}

	.mode-label {
		color: var(--gold, #ffd700);
		font-size: var(--text-xs, 12px);
		font-weight: 500;
		text-transform: uppercase;
		letter-spacing: 0.5px;
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		padding: var(--space-1, 4px);
		border-radius: var(--radius-sm, 4px);
		transition: all 0.15s ease;
	}

	.dismiss-btn:hover {
		color: var(--text-primary, #fff);
		background: rgba(255, 255, 255, 0.05);
	}

	.dismiss-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}

	.conversation-content {
		color: var(--text-primary, #fff);
		line-height: 1.6;
	}

	.message-text {
		margin: 0;
		white-space: pre-wrap;
	}

	.conversation-actions {
		display: flex;
		gap: var(--space-2, 8px);
		padding-top: var(--space-2, 8px);
		border-top: 1px solid rgba(255, 215, 0, 0.1);
	}

	.action-btn {
		padding: var(--space-2, 8px) var(--space-3, 12px);
		background: rgba(255, 255, 255, 0.05);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-md, 8px);
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.action-btn:hover {
		background: rgba(255, 215, 0, 0.1);
		border-color: rgba(255, 215, 0, 0.3);
		color: var(--gold, #ffd700);
	}

	.action-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}
</style>
