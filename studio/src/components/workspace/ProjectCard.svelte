<!--
  ProjectCard — Compact detected project representation (RFC-103)
  
  Shows a detected source code project with:
  - Language icon
  - Project name
  - Confidence indicator
  - Selection checkbox
-->
<script lang="ts">
	import type { WorkspaceLink } from '$stores/workspace.svelte';

	interface Props {
		link: WorkspaceLink;
		isSelected: boolean;
		onToggle: () => void;
	}

	let { link, isSelected, onToggle }: Props = $props();

	function getLanguageIcon(language: string | null): string {
		const icons: Record<string, string> = {
			python: '🐍',
			typescript: '📘',
			javascript: '📒',
			rust: '🦀',
			go: '🐹',
			java: '☕',
			ruby: '💎',
			unknown: '📁',
		};
		return icons[language ?? 'unknown'] ?? '📁';
	}

	function getLanguageLabel(language: string | null): string {
		const labels: Record<string, string> = {
			python: 'Python',
			typescript: 'TypeScript',
			javascript: 'JavaScript',
			rust: 'Rust',
			go: 'Go',
			java: 'Java',
			ruby: 'Ruby',
		};
		return labels[language ?? ''] ?? 'Unknown';
	}

	function getConfidenceColor(confidence: number): string {
		if (confidence >= 0.9) return 'var(--success)';
		if (confidence >= 0.7) return 'var(--warning)';
		return 'var(--text-tertiary)';
	}

	function getConfidenceLabel(confidence: number): string {
		const pct = Math.round(confidence * 100);
		if (pct >= 90) return `${pct}% match`;
		if (pct >= 70) return `${pct}% likely`;
		return `${pct}%`;
	}

	function getProjectName(path: string): string {
		// Extract last directory name
		const parts = path.split('/').filter(Boolean);
		return parts[parts.length - 1] ?? path;
	}

	function getRelativePath(path: string): string {
		// Try to make relative for display
		if (path.startsWith('/Users/')) {
			return path.replace(/^\/Users\/[^/]+/, '~');
		}
		return path;
	}
</script>

<button
	class="project-card"
	class:selected={isSelected}
	onclick={onToggle}
	type="button"
	aria-pressed={isSelected}
>
	<!-- Checkbox -->
	<div class="checkbox" aria-hidden="true">
		{#if isSelected}
			<span class="check-icon">✓</span>
		{/if}
	</div>

	<!-- Language icon -->
	<span class="language-icon" aria-label={getLanguageLabel(link.language)}>
		{getLanguageIcon(link.language)}
	</span>

	<!-- Project info -->
	<div class="project-info">
		<span class="project-name">{getProjectName(link.target)}</span>
		<span class="project-path">{getRelativePath(link.target)}</span>
	</div>

	<!-- Confidence badge -->
	<span
		class="confidence-badge"
		style="color: {getConfidenceColor(link.confidence)}"
	>
		{getConfidenceLabel(link.confidence)}
	</span>
</button>

<style>
	.project-card {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		cursor: pointer;
		transition: all 0.15s ease;
		width: 100%;
		text-align: left;
	}

	.project-card:hover {
		background: rgba(255, 255, 255, 0.04);
		border-color: rgba(255, 255, 255, 0.1);
	}

	.project-card.selected {
		background: rgba(218, 165, 32, 0.08);
		border-color: rgba(218, 165, 32, 0.3);
	}

	/* Checkbox */
	.checkbox {
		width: 16px;
		height: 16px;
		border: 1.5px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		display: flex;
		align-items: center;
		justify-content: center;
		flex-shrink: 0;
		transition: all 0.15s ease;
	}

	.project-card.selected .checkbox {
		background: var(--gold);
		border-color: var(--gold);
	}

	.check-icon {
		font-size: 10px;
		color: var(--bg-primary);
		font-weight: bold;
	}

	/* Language icon */
	.language-icon {
		font-size: var(--text-base);
		flex-shrink: 0;
	}

	/* Project info */
	.project-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 1px;
		min-width: 0;
	}

	.project-name {
		font-size: var(--text-sm);
		font-weight: 500;
		color: var(--text-primary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.project-path {
		font-size: var(--text-2xs);
		color: var(--text-tertiary);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	/* Confidence badge */
	.confidence-badge {
		font-size: var(--text-2xs);
		font-weight: 500;
		flex-shrink: 0;
		padding: 2px 6px;
		background: rgba(255, 255, 255, 0.03);
		border-radius: var(--radius-sm);
	}
</style>
