<!--
  SearchBlock — Search results display (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface SearchResult { id: string; type: 'note' | 'list_item' | 'event' | 'file'; title?: string; text?: string; list?: string; path?: string; }
	interface Props {
		data: { results: SearchResult[]; query: string; };
		onAction?: (actionId: string, resultId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function getIcon(type: string): string {
		const icons: Record<string, string> = { note: '📝', list_item: '📋', event: '📅', file: '📄' };
		return icons[type] || '🔍';
	}

	function handleOpen(resultId: string) { onAction?.('open', resultId); }
</script>

<div class="search-view">
	<header class="search-header">
		<span class="search-query">Results for "{data.query}"</span>
		<span class="result-count">{data.results.length} found</span>
	</header>

	{#if data.results.length > 0}
		<div class="result-list">
			{#each data.results.slice(0, 15) as result, i (result.id)}
				<button class="result-item" in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }} onclick={() => handleOpen(result.id)}>
					<span class="result-icon" aria-hidden="true">{getIcon(result.type)}</span>
					<span class="result-text">
						{result.title || result.text}
						{#if result.list}
							<span class="result-meta">[{result.list}]</span>
						{/if}
					</span>
				</button>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No results</p></div>
	{/if}
</div>

<style>
	.search-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.search-header { display: flex; justify-content: space-between; align-items: center; }
	.search-query { color: var(--text-secondary, #999); font-size: var(--text-sm, 14px); }
	.result-count { color: var(--text-tertiary, #666); font-size: var(--text-sm, 14px); }
	.result-list { display: flex; flex-direction: column; gap: var(--space-1, 4px); }
	.result-item { display: flex; align-items: center; gap: var(--space-2, 8px); padding: var(--space-2, 8px); background: var(--bg-primary, #0a0a0a); border: none; border-radius: var(--radius-sm, 4px); cursor: pointer; text-align: left; width: 100%; transition: all 0.15s ease; }
	.result-item:hover { background: rgba(255, 215, 0, 0.05); }
	.result-item:focus-visible { outline: 2px solid var(--gold, #ffd700); outline-offset: 2px; }
	.result-icon { font-size: var(--text-lg, 18px); }
	.result-text { flex: 1; color: var(--text-primary, #fff); font-size: var(--text-sm, 14px); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.result-meta { color: var(--text-tertiary, #666); font-size: var(--text-sm, 14px); }
	.empty-state { text-align: center; padding: var(--space-4, 16px); color: var(--text-tertiary, #666); }
</style>
