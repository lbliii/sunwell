<!--
  Interface — Generative Interface page (RFC-075)
  
  The conversational entry point that routes to workspace, view, action, or conversation.
-->
<script lang="ts">
	import { untrack } from 'svelte';
	import Logo from '../components/Logo.svelte';
	import GoalInput from '../components/GoalInput.svelte';
	import InterfaceOutput from '../components/InterfaceOutput.svelte';
	import Button from '../components/Button.svelte';
	import RisingMotes from '../components/RisingMotes.svelte';
	import MouseMotes from '../components/MouseMotes.svelte';
	import { goToProject, goHome } from '../stores/app.svelte';
	import {
		interfaceState,
		clearHistory,
		composeSurface,
		loadRegistry,
	} from '../stores';
	import { project, openProject } from '../stores/project.svelte';
	import type { Message } from '../stores/interface.svelte';

	// Load registry on mount
	$effect(() => {
		untrack(() => {
			loadRegistry();
		});
	});

	// When workspace is ready, navigate to project view
	function handleWorkspaceReady() {
		// Give a moment for the surface to compose
		setTimeout(() => {
			if (project.current) {
				goToProject();
			}
		}, 500);
	}

	function handleClearHistory() {
		clearHistory();
	}

	function handleGoHome() {
		goHome();
	}

	// Format timestamp
	function formatTime(timestamp: number): string {
		return new Date(timestamp).toLocaleTimeString([], {
			hour: '2-digit',
			minute: '2-digit',
		});
	}

	// Get message style based on role and output type
	function getMessageIcon(msg: Message): string {
		if (msg.role === 'user') return '👤';
		switch (msg.outputType) {
			case 'action':
				return '⚡';
			case 'view':
				return '👁️';
			case 'workspace':
				return '🎨';
			case 'conversation':
				return '💬';
			case 'hybrid':
				return '🔄';
			default:
				return '🤖';
		}
	}
</script>

<MouseMotes spawnRate={30} maxParticles={20}>
	{#snippet children()}
		<div class="interface-page">
			<!-- Background aura -->
			<div class="background-aura"></div>

			<!-- Ambient motes -->
			<div class="ambient-motes">
				<RisingMotes count={8} intensity="normal" />
			</div>

			<!-- Header -->
			<header class="header">
				<button class="back-btn" onclick={handleGoHome}>← Home</button>
				<div class="logo-small">
					<Logo size="sm" />
				</div>
				{#if interfaceState.messages.length > 0}
					<button class="clear-btn" onclick={handleClearHistory}>Clear</button>
				{:else}
					<div></div>
				{/if}
			</header>

			<!-- Main content -->
			<main class="main">
				<!-- Message history -->
				{#if interfaceState.messages.length > 0}
					<div class="messages">
						{#each interfaceState.messages as msg (msg.timestamp)}
							<div class="message message-{msg.role}">
								<div class="message-header">
									<span class="message-icon">{getMessageIcon(msg)}</span>
									<span class="message-time">{formatTime(msg.timestamp)}</span>
								</div>
								<div class="message-content">{msg.content}</div>
							</div>
						{/each}

						{#if interfaceState.isAnalyzing}
							<div class="message message-assistant analyzing">
								<div class="message-header">
									<span class="message-icon">🤖</span>
									<span class="thinking">Thinking...</span>
								</div>
							</div>
						{/if}
					</div>
				{:else}
					<!-- Empty state -->
					<div class="empty-state">
						<div class="empty-icon">✨</div>
						<h2>What would you like to do?</h2>
						<p>Ask me anything — I'll figure out the best way to help.</p>
						<div class="examples">
							<div class="example">"Add milk to my grocery list"</div>
							<div class="example">"What am I doing this weekend?"</div>
							<div class="example">"Write a story about dragons"</div>
							<div class="example">"I feel stressed about work"</div>
						</div>
					</div>
				{/if}

				<!-- Current output -->
				{#if interfaceState.current && !interfaceState.isAnalyzing}
					<div class="output-section">
						<InterfaceOutput
							output={interfaceState.current}
							onWorkspaceReady={handleWorkspaceReady}
						/>
					</div>
				{/if}
			</main>

			<!-- Input area -->
			<footer class="footer">
				<GoalInput />
			</footer>
		</div>
	{/snippet}
</MouseMotes>

<style>
	.interface-page {
		display: flex;
		flex-direction: column;
		min-height: 100vh;
		position: relative;
		overflow: hidden;
	}

	.background-aura {
		position: absolute;
		top: 0;
		left: 50%;
		transform: translateX(-50%);
		width: 100%;
		height: 40%;
		background: radial-gradient(
			ellipse 60% 50% at 50% 0%,
			rgba(255, 215, 0, 0.04) 0%,
			rgba(218, 165, 32, 0.02) 30%,
			transparent 60%
		);
		pointer-events: none;
		z-index: 0;
	}

	.ambient-motes {
		position: absolute;
		top: 10%;
		left: 50%;
		transform: translateX(-50%);
		width: 400px;
		height: 200px;
		pointer-events: none;
		z-index: 1;
	}

	.header {
		display: flex;
		justify-content: space-between;
		align-items: center;
		padding: var(--space-4, 16px) var(--space-6, 24px);
		position: relative;
		z-index: 10;
	}

	.back-btn,
	.clear-btn {
		background: none;
		border: none;
		color: var(--text-secondary, #999);
		cursor: pointer;
		font-size: var(--text-sm, 14px);
		transition: color 0.15s;
	}

	.back-btn:hover,
	.clear-btn:hover {
		color: var(--text-primary, #fff);
	}

	.logo-small {
		opacity: 0.7;
	}

	.main {
		flex: 1;
		display: flex;
		flex-direction: column;
		padding: var(--space-4, 16px) var(--space-6, 24px);
		max-width: 800px;
		margin: 0 auto;
		width: 100%;
		position: relative;
		z-index: 2;
		overflow-y: auto;
	}

	/* Empty state */
	.empty-state {
		flex: 1;
		display: flex;
		flex-direction: column;
		align-items: center;
		justify-content: center;
		text-align: center;
		gap: var(--space-4, 16px);
		animation: fadeIn 0.3s ease;
	}

	.empty-icon {
		font-size: 48px;
		margin-bottom: var(--space-2, 8px);
	}

	.empty-state h2 {
		color: var(--text-primary, #fff);
		font-size: var(--text-2xl, 24px);
		font-weight: 600;
		margin: 0;
	}

	.empty-state p {
		color: var(--text-secondary, #999);
		margin: 0;
	}

	.examples {
		display: flex;
		flex-wrap: wrap;
		gap: var(--space-2, 8px);
		justify-content: center;
		margin-top: var(--space-4, 16px);
	}

	.example {
		background: var(--bg-secondary, #1e1e1e);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-md, 8px);
		padding: var(--space-2, 8px) var(--space-3, 12px);
		color: var(--text-tertiary, #666);
		font-size: var(--text-sm, 14px);
	}

	/* Messages */
	.messages {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
		padding-bottom: var(--space-4, 16px);
	}

	.message {
		max-width: 80%;
		animation: slideIn 0.2s ease-out;
	}

	.message-user {
		align-self: flex-end;
	}

	.message-assistant {
		align-self: flex-start;
	}

	.message-header {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		margin-bottom: var(--space-1, 4px);
	}

	.message-icon {
		font-size: var(--text-sm, 14px);
	}

	.message-time {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
	}

	.message-content {
		background: var(--bg-secondary, #1e1e1e);
		border-radius: var(--radius-lg, 12px);
		padding: var(--space-3, 12px) var(--space-4, 16px);
		color: var(--text-primary, #fff);
		line-height: 1.5;
	}

	.message-user .message-content {
		background: var(--gold, #ffd700);
		color: var(--bg-primary, #0a0a0a);
	}

	.analyzing .thinking {
		color: var(--text-tertiary, #666);
		font-style: italic;
		animation: pulse 1.5s ease-in-out infinite;
	}

	/* Output section */
	.output-section {
		margin-top: var(--space-4, 16px);
	}

	/* Footer */
	.footer {
		padding: var(--space-4, 16px) var(--space-6, 24px);
		display: flex;
		justify-content: center;
		position: relative;
		z-index: 10;
		background: linear-gradient(transparent, var(--bg-primary, #0a0a0a) 50%);
	}

	@keyframes fadeIn {
		from {
			opacity: 0;
			transform: translateY(10px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@keyframes slideIn {
		from {
			opacity: 0;
			transform: translateY(5px);
		}
		to {
			opacity: 1;
			transform: translateY(0);
		}
	}

	@keyframes pulse {
		0%,
		100% {
			opacity: 0.5;
		}
		50% {
			opacity: 1;
		}
	}
</style>
