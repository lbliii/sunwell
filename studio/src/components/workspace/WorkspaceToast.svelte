<!--
  WorkspaceToast — Non-blocking workspace setup notification (RFC-103)
  
  Shows detected source code projects and allows users to link them
  for drift detection. Appears in bottom-right, doesn't block workflow.

  States:
  - detecting: Showing spinner while scanning
  - showing: Displaying detected projects
  - linking: Processing link requests
  - dismissed: Animating out
-->
<script lang="ts">
	import { fly, fade } from 'svelte/transition';
	import {
		workspaceStore,
		toggleLinkSelection,
		linkSelected,
		dismissToast,
		skipLinking,
		type WorkspaceLink,
	} from '$stores/workspace.svelte';
	import ProjectCard from './ProjectCard.svelte';

	// Local state for UI feedback
	let isLinking = $state(false);

	$effect(() => {
		isLinking = workspaceStore.toastState === 'linking';
	});

	async function handleLinkSelected() {
		try {
			await linkSelected();
		} catch (e) {
			console.error('Failed to link projects:', e);
		}
	}

	function handleSkip() {
		skipLinking();
	}

	function handleDontShowAgain() {
		dismissToast(true);
	}

	function handleDismiss() {
		dismissToast(false);
	}

	function getConfidenceColor(confidence: number): string {
		if (confidence >= 0.9) return 'var(--success)';
		if (confidence >= 0.7) return 'var(--warning)';
		return 'var(--text-tertiary)';
	}

	function getLanguageIcon(language: string | null): string {
		const icons: Record<string, string> = {
			python: '🐍',
			typescript: '📘',
			javascript: '📒',
			rust: '🦀',
			go: '🐹',
			java: '☕',
			ruby: '💎',
		};
		return icons[language ?? ''] ?? '📁';
	}

	// Only show if we should
	const shouldShow = $derived(workspaceStore.shouldShowToast);
	const links = $derived(workspaceStore.detectedLinks);
	const selected = $derived(workspaceStore.selectedLinks);
	const selectedCount = $derived(selected.size);
</script>

{#if shouldShow}
	<div
		class="workspace-toast"
		in:fly={{ y: 50, duration: 300 }}
		out:fade={{ duration: 200 }}
		role="dialog"
		aria-labelledby="workspace-toast-title"
	>
		<!-- Header -->
		<div class="toast-header">
			<h3 id="workspace-toast-title" class="toast-title">
				<span class="icon" aria-hidden="true">🔗</span>
				Found related projects
			</h3>
			<button
				class="dismiss-btn"
				onclick={handleDismiss}
				aria-label="Dismiss notification"
			>
				<span aria-hidden="true">✕</span>
			</button>
		</div>

		<!-- Project list -->
		<div class="project-list">
			{#each links as link (link.target)}
				<ProjectCard
					{link}
					isSelected={selected.has(link.target)}
					onToggle={() => toggleLinkSelection(link.target)}
				/>
			{/each}
		</div>

		<!-- Benefits callout -->
		<div class="benefits-callout">
			<span class="benefit-icon" aria-hidden="true">✨</span>
			<span class="benefit-text">
				Linking enables drift detection and API verification
			</span>
		</div>

		<!-- Actions -->
		<div class="toast-actions">
			<button
				class="action-btn primary"
				onclick={handleLinkSelected}
				disabled={selectedCount === 0 || isLinking}
			>
				{#if isLinking}
					<span class="spinner" aria-hidden="true"></span>
					Linking...
				{:else}
					Link Selected ({selectedCount})
				{/if}
			</button>
			<button class="action-btn secondary" onclick={handleSkip}>
				Skip
			</button>
			<button class="action-btn tertiary" onclick={handleDontShowAgain}>
				Don't show again
			</button>
		</div>
	</div>
{/if}

<style>
	.workspace-toast {
		position: fixed;
		bottom: var(--space-4);
		right: var(--space-4);
		width: 360px;
		background: var(--bg-secondary);
		border-radius: var(--radius-lg);
		border: 1px solid var(--border-subtle);
		box-shadow:
			0 8px 32px rgba(0, 0, 0, 0.4),
			0 0 60px rgba(0, 0, 0, 0.2);
		z-index: 999;
		overflow: hidden;
	}

	/* Header */
	.toast-header {
		display: flex;
		align-items: center;
		justify-content: space-between;
		padding: var(--space-3) var(--space-4);
		border-bottom: 1px solid var(--border-subtle);
		background: rgba(255, 255, 255, 0.02);
	}

	.toast-title {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		margin: 0;
		font-size: var(--text-sm);
		font-weight: 600;
		color: var(--text-primary);
	}

	.toast-title .icon {
		font-size: var(--text-base);
	}

	.dismiss-btn {
		background: none;
		border: none;
		color: var(--text-tertiary);
		cursor: pointer;
		padding: var(--space-1);
		border-radius: var(--radius-sm);
		transition: all 0.15s ease;
		line-height: 1;
	}

	.dismiss-btn:hover {
		color: var(--text-primary);
		background: rgba(255, 255, 255, 0.05);
	}

	/* Project list */
	.project-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-4);
		max-height: 200px;
		overflow-y: auto;
	}

	/* Benefits callout */
	.benefits-callout {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-4);
		background: rgba(218, 165, 32, 0.05);
		border-top: 1px solid rgba(218, 165, 32, 0.1);
		border-bottom: 1px solid rgba(218, 165, 32, 0.1);
	}

	.benefit-icon {
		font-size: var(--text-sm);
	}

	.benefit-text {
		font-size: var(--text-xs);
		color: var(--gold);
	}

	/* Actions */
	.toast-actions {
		display: flex;
		gap: var(--space-2);
		padding: var(--space-3) var(--space-4);
		background: rgba(0, 0, 0, 0.1);
	}

	.action-btn {
		flex: 1;
		padding: var(--space-2) var(--space-3);
		border-radius: var(--radius-md);
		font-size: var(--text-xs);
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s ease;
		display: flex;
		align-items: center;
		justify-content: center;
		gap: var(--space-2);
	}

	.action-btn.primary {
		background: var(--gold);
		color: var(--bg-primary);
		border: none;
	}

	.action-btn.primary:hover:not(:disabled) {
		filter: brightness(1.1);
	}

	.action-btn.primary:disabled {
		opacity: 0.5;
		cursor: not-allowed;
	}

	.action-btn.secondary {
		background: rgba(255, 255, 255, 0.05);
		color: var(--text-secondary);
		border: 1px solid var(--border-subtle);
	}

	.action-btn.secondary:hover {
		background: rgba(255, 255, 255, 0.08);
		color: var(--text-primary);
	}

	.action-btn.tertiary {
		background: transparent;
		color: var(--text-tertiary);
		border: none;
		font-size: var(--text-2xs);
	}

	.action-btn.tertiary:hover {
		color: var(--text-secondary);
	}

	/* Spinner */
	.spinner {
		width: 12px;
		height: 12px;
		border: 2px solid transparent;
		border-top-color: currentColor;
		border-radius: 50%;
		animation: spin 0.6s linear infinite;
	}

	@keyframes spin {
		to {
			transform: rotate(360deg);
		}
	}

	/* Scrollbar */
	.project-list::-webkit-scrollbar {
		width: 4px;
	}

	.project-list::-webkit-scrollbar-track {
		background: transparent;
	}

	.project-list::-webkit-scrollbar-thumb {
		background: var(--border-subtle);
		border-radius: 2px;
	}
</style>
