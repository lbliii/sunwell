<!--
  GenericBlock — Fallback block for unknown types (RFC-080)
  
  Displays arbitrary data in a key-value format.
  Used when no specific block component exists for a view type.
-->
<script lang="ts">
	import { fly } from 'svelte/transition';

	interface Props {
		type: string;
		data: Record<string, unknown>;
	}

	let { type, data }: Props = $props();

	function formatValue(value: unknown): string {
		if (value === null || value === undefined) return '—';
		if (typeof value === 'boolean') return value ? '✓' : '✕';
		if (typeof value === 'number') return value.toLocaleString();
		if (typeof value === 'string') return value;
		if (Array.isArray(value)) return `[${value.length} items]`;
		if (typeof value === 'object') return JSON.stringify(value, null, 2);
		return String(value);
	}

	function formatKey(key: string): string {
		return key
			.replace(/_/g, ' ')
			.replace(/([A-Z])/g, ' $1')
			.toLowerCase()
			.replace(/^./, (s) => s.toUpperCase());
	}

	// Filter out internal/complex fields
	function shouldShow(key: string, value: unknown): boolean {
		if (key.startsWith('_')) return false;
		if (typeof value === 'object' && value !== null && !Array.isArray(value)) return false;
		return true;
	}
</script>

<div class="generic-block" in:fly={{ y: 20, duration: 250 }}>
	<header class="block-header">
		<span class="block-type">{type}</span>
		<span class="block-badge">Block</span>
	</header>

	<div class="data-grid">
		{#each Object.entries(data).filter(([k, v]) => shouldShow(k, v)) as [key, value]}
			<div class="data-row">
				<span class="data-key">{formatKey(key)}</span>
				<span class="data-value">{formatValue(value)}</span>
			</div>
		{/each}
	</div>

	{#if Object.keys(data).length === 0}
		<div class="empty-state">
			<p>No data available</p>
		</div>
	{/if}
</div>

<style>
	.generic-block {
		display: flex;
		flex-direction: column;
		gap: var(--space-3, 12px);
	}

	.block-header {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
	}

	.block-type {
		color: var(--text-primary, #fff);
		font-weight: 600;
		font-size: var(--text-base, 16px);
		text-transform: capitalize;
	}

	.block-badge {
		padding: 2px 6px;
		background: rgba(255, 215, 0, 0.1);
		border: 1px solid rgba(255, 215, 0, 0.2);
		border-radius: var(--radius-sm, 4px);
		color: var(--gold, #ffd700);
		font-size: var(--text-xs, 12px);
	}

	.data-grid {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.data-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: var(--space-3, 12px);
		padding: var(--space-2, 8px);
		background: var(--bg-primary, #0a0a0a);
		border-radius: var(--radius-sm, 4px);
	}

	.data-key {
		color: var(--text-secondary, #999);
		font-size: var(--text-sm, 14px);
		flex-shrink: 0;
	}

	.data-value {
		color: var(--text-primary, #fff);
		font-size: var(--text-sm, 14px);
		text-align: right;
		word-break: break-word;
	}

	.empty-state {
		text-align: center;
		padding: var(--space-4, 16px);
		color: var(--text-tertiary, #666);
	}
</style>
