<!--
  DriftBadge — Drift warning indicator (RFC-103)
  
  Shows drift status for a documentation node:
  - Green: No drift detected
  - Yellow: Minor drift (1-2 warnings)
  - Red: Significant drift (3+ warnings)
  - Gray: No source linked (drift detection disabled)

  Hover shows drift details.
-->
<script lang="ts">
	import { fade } from 'svelte/transition';

	interface DriftInfo {
		count: number;
		status: 'healthy' | 'warning' | 'critical' | 'no_source';
		issues: string[];
	}

	interface Props {
		drift: DriftInfo;
		compact?: boolean;
	}

	let { drift, compact = false }: Props = $props();

	let showTooltip = $state(false);

	function getStatusColor(): string {
		switch (drift.status) {
			case 'healthy':
				return 'var(--success)';
			case 'warning':
				return 'var(--warning)';
			case 'critical':
				return 'var(--error)';
			case 'no_source':
			default:
				return 'var(--text-tertiary)';
		}
	}

	function getStatusIcon(): string {
		switch (drift.status) {
			case 'healthy':
				return '✓';
			case 'warning':
				return '⚠';
			case 'critical':
				return '✕';
			case 'no_source':
			default:
				return '○';
		}
	}

	function getStatusLabel(): string {
		switch (drift.status) {
			case 'healthy':
				return 'No drift';
			case 'warning':
				return `${drift.count} drift warning${drift.count > 1 ? 's' : ''}`;
			case 'critical':
				return `${drift.count} drift issues`;
			case 'no_source':
			default:
				return 'No source linked';
		}
	}

	function handleMouseEnter() {
		if (drift.issues.length > 0 || drift.status === 'no_source') {
			showTooltip = true;
		}
	}

	function handleMouseLeave() {
		showTooltip = false;
	}
</script>

<div
	class="drift-badge"
	class:compact
	style="--status-color: {getStatusColor()}"
	onmouseenter={handleMouseEnter}
	onmouseleave={handleMouseLeave}
	role="status"
	aria-label={getStatusLabel()}
>
	<span class="status-icon" aria-hidden="true">{getStatusIcon()}</span>
	{#if !compact}
		<span class="status-label">{getStatusLabel()}</span>
	{/if}

	<!-- Tooltip -->
	{#if showTooltip}
		<div class="tooltip" transition:fade={{ duration: 150 }}>
			<div class="tooltip-header">
				<span class="tooltip-icon" aria-hidden="true">{getStatusIcon()}</span>
				<span class="tooltip-title">{getStatusLabel()}</span>
			</div>

			{#if drift.status === 'no_source'}
				<div class="tooltip-content">
					<p>Link source code to enable drift detection.</p>
					<p class="tooltip-hint">Click to open workspace settings.</p>
				</div>
			{:else if drift.issues.length > 0}
				<ul class="drift-issues">
					{#each drift.issues.slice(0, 5) as issue}
						<li class="drift-issue">{issue}</li>
					{/each}
					{#if drift.issues.length > 5}
						<li class="more-issues">+{drift.issues.length - 5} more</li>
					{/if}
				</ul>
			{:else}
				<div class="tooltip-content">
					<p>Documentation matches source code.</p>
				</div>
			{/if}
		</div>
	{/if}
</div>

<style>
	.drift-badge {
		position: relative;
		display: inline-flex;
		align-items: center;
		gap: var(--space-1);
		padding: var(--space-1) var(--space-2);
		background: rgba(255, 255, 255, 0.02);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-sm);
		cursor: default;
		font-size: var(--text-xs);
		transition: all 0.15s ease;
	}

	.drift-badge:hover {
		background: rgba(255, 255, 255, 0.04);
	}

	.drift-badge.compact {
		padding: var(--space-1);
		border: none;
		background: transparent;
	}

	.status-icon {
		color: var(--status-color);
		font-weight: bold;
		font-size: var(--text-xs);
	}

	.status-label {
		color: var(--text-secondary);
		white-space: nowrap;
	}

	/* Tooltip */
	.tooltip {
		position: absolute;
		bottom: calc(100% + 8px);
		left: 50%;
		transform: translateX(-50%);
		width: 280px;
		background: var(--bg-secondary);
		border: 1px solid var(--border-subtle);
		border-radius: var(--radius-md);
		box-shadow:
			0 8px 24px rgba(0, 0, 0, 0.4),
			0 0 40px rgba(0, 0, 0, 0.2);
		z-index: 100;
		overflow: hidden;
	}

	.tooltip::after {
		content: '';
		position: absolute;
		top: 100%;
		left: 50%;
		transform: translateX(-50%);
		border: 6px solid transparent;
		border-top-color: var(--border-subtle);
	}

	.tooltip-header {
		display: flex;
		align-items: center;
		gap: var(--space-2);
		padding: var(--space-2) var(--space-3);
		background: rgba(255, 255, 255, 0.02);
		border-bottom: 1px solid var(--border-subtle);
	}

	.tooltip-icon {
		color: var(--status-color);
		font-weight: bold;
	}

	.tooltip-title {
		font-size: var(--text-sm);
		font-weight: 500;
		color: var(--text-primary);
	}

	.tooltip-content {
		padding: var(--space-2) var(--space-3);
	}

	.tooltip-content p {
		margin: 0;
		font-size: var(--text-xs);
		color: var(--text-secondary);
	}

	.tooltip-hint {
		color: var(--gold) !important;
		margin-top: var(--space-1) !important;
	}

	/* Drift issues list */
	.drift-issues {
		margin: 0;
		padding: var(--space-2) var(--space-3);
		list-style: none;
		display: flex;
		flex-direction: column;
		gap: var(--space-1);
	}

	.drift-issue {
		font-size: var(--text-xs);
		color: var(--text-secondary);
		padding-left: var(--space-3);
		position: relative;
	}

	.drift-issue::before {
		content: '•';
		position: absolute;
		left: 0;
		color: var(--status-color);
	}

	.more-issues {
		font-size: var(--text-2xs);
		color: var(--text-tertiary);
		padding-left: var(--space-3);
	}
</style>
