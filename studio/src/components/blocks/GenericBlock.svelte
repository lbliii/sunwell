<!--
  GenericBlock — Fallback block for unknown types (RFC-080)
  
  Displays arbitrary data in a key-value format.
  Used when no specific block component exists for a view type.
-->
<script lang="ts">
	import { fly } from 'svelte/transition';

	interface Props {
		readonly type: string;
		readonly data: Readonly<Record<string, unknown>>;
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

	// Pre-compute visible entries for O(1) render (avoids filter in template)
	const visibleEntries = $derived(
		Object.entries(data).filter(([k, v]) => shouldShow(k, v))
	);
</script>

<div class="generic-block" in:fly={{ y: 20, duration: 250 }}>
	<header class="block-header">
		<span class="block-type">{type}</span>
		<span class="block-badge">Block</span>
	</header>

	<div class="data-grid">
		{#each visibleEntries as [key, value] (key)}
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
		gap: var(--space-3);
	}

	.block-header {
		display: flex;
		align-items: center;
		gap: var(--space-2);
	}

	.block-type {
		color: var(--text-primary);
		font-weight: 600;
		font-size: var(--text-base);
		text-transform: capitalize;
	}

	.block-badge {
		padding: 2px 6px;
		background: var(--radiant-gold-10);
		border: 1px solid var(--radiant-gold-20);
		border-radius: var(--radius-sm);
		color: var(--gold);
		font-size: var(--text-xs);
	}

	.data-grid {
		display: flex;
		flex-direction: column;
		gap: var(--space-2);
	}

	.data-row {
		display: flex;
		justify-content: space-between;
		align-items: flex-start;
		gap: var(--space-3);
		padding: var(--space-2);
		background: var(--bg-primary);
		border-radius: var(--radius-sm);
	}

	.data-key {
		color: var(--text-secondary);
		font-size: var(--text-sm);
		flex-shrink: 0;
	}

	.data-value {
		color: var(--text-primary);
		font-size: var(--text-sm);
		text-align: right;
		word-break: break-word;
	}

	.empty-state {
		text-align: center;
		padding: var(--space-4);
		color: var(--text-tertiary);
	}
</style>
