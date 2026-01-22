<!--
  ChatHistory — Sidebar for viewing/managing chat sessions (RFC-080 enhancement)
  
  Shows conversation history with ability to:
  - View past messages in current session
  - Start new sessions
  - Clear history
-->
<script lang="ts">
	import { fly, slide } from 'svelte/transition';
	import { homeState, clearConversationHistory } from '../stores/home.svelte';
	import Button from './Button.svelte';

	interface Props {
		isOpen?: boolean;
		onClose?: () => void;
		onNewSession?: () => void;
	}

	let { isOpen = false, onClose, onNewSession }: Props = $props();

	function formatTime(timestamp: number): string {
		const date = new Date(timestamp);
		return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
	}

	function handleClear() {
		clearConversationHistory();
	}

	function handleNewSession() {
		clearConversationHistory();
		onNewSession?.();
		onClose?.();
	}
</script>

{#if isOpen}
	<!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
	<div class="overlay" onclick={onClose} transition:fly={{ opacity: 0 }}></div>

	<aside class="chat-history" transition:fly={{ x: -300, duration: 200 }}>
		<header class="header">
			<h2 class="title">💬 Chat History</h2>
			<button class="close-btn" onclick={onClose} aria-label="Close">
				✕
			</button>
		</header>

		<div class="content">
			{#if homeState.conversationHistory.length === 0}
				<div class="empty-state">
					<span class="empty-icon">🌟</span>
					<p class="empty-text">No messages yet</p>
					<p class="empty-hint">Start a conversation by typing in the input</p>
				</div>
			{:else}
				<div class="messages">
					{#each homeState.conversationHistory as msg (msg.timestamp)}
						<div class="message message-{msg.role}" transition:slide={{ duration: 150 }}>
							<div class="message-meta">
								<span class="message-role">
									{msg.role === 'user' ? '👤' : '✨'}
								</span>
								<span class="message-time">{formatTime(msg.timestamp)}</span>
							</div>
							<p class="message-content">{msg.content}</p>
						</div>
					{/each}
				</div>
			{/if}
		</div>

		<footer class="footer">
			<Button variant="ghost" onclick={handleNewSession}>
				➕ New Session
			</Button>
			{#if homeState.conversationHistory.length > 0}
				<Button variant="ghost" onclick={handleClear}>
					🗑️ Clear
				</Button>
			{/if}
		</footer>
	</aside>
{/if}

<style>
	.overlay {
		position: fixed;
		inset: 0;
		background: rgba(0, 0, 0, 0.5);
		z-index: 99;
	}

	.chat-history {
		position: fixed;
		top: 0;
		left: 0;
		bottom: 0;
		width: 320px;
		max-width: 90vw;
		background: var(--bg-surface, #111);
		border-right: 1px solid var(--border-subtle, #333);
		display: flex;
		flex-direction: column;
		z-index: 100;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-4, 16px);
		border-bottom: 1px solid var(--border-subtle, #333);
	}

	.title {
		margin: 0;
		font-size: var(--text-lg, 18px);
		font-weight: 600;
		color: var(--text-primary, #fff);
	}

	.close-btn {
		background: none;
		border: none;
		color: var(--text-tertiary, #666);
		cursor: pointer;
		padding: var(--space-2, 8px);
		border-radius: var(--radius-sm, 4px);
		transition: all 0.15s ease;
	}

	.close-btn:hover {
		color: var(--text-primary, #fff);
		background: rgba(255, 255, 255, 0.05);
	}

	.content {
		flex: 1;
		overflow-y: auto;
		padding: var(--space-3, 12px);
	}

	.empty-state {
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		height: 100%;
		gap: var(--space-2, 8px);
		text-align: center;
	}

	.empty-icon {
		font-size: 2rem;
		opacity: 0.6;
	}

	.empty-text {
		color: var(--text-secondary, #999);
		font-size: var(--text-base, 16px);
		margin: 0;
	}

	.empty-hint {
		color: var(--text-tertiary, #666);
		font-size: var(--text-sm, 14px);
		margin: 0;
	}

	.messages {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
	}

	.message {
		padding: var(--space-3, 12px);
		border-radius: var(--radius-md, 8px);
		background: rgba(255, 255, 255, 0.03);
		border: 1px solid transparent;
	}

	.message-user {
		border-color: rgba(255, 255, 255, 0.1);
	}

	.message-assistant {
		border-color: rgba(255, 215, 0, 0.15);
		background: linear-gradient(
			135deg,
			rgba(255, 215, 0, 0.03) 0%,
			rgba(255, 255, 255, 0.02) 100%
		);
	}

	.message-meta {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		margin-bottom: var(--space-1, 4px);
	}

	.message-role {
		font-size: var(--text-sm, 14px);
	}

	.message-time {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
	}

	.message-content {
		color: var(--text-primary, #fff);
		font-size: var(--text-sm, 14px);
		line-height: 1.5;
		margin: 0;
		white-space: pre-wrap;
		word-break: break-word;
	}

	.footer {
		display: flex;
		gap: var(--space-2, 8px);
		padding: var(--space-3, 12px);
		border-top: 1px solid var(--border-subtle, #333);
	}
</style>
