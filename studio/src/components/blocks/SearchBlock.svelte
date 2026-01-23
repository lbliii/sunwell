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
	.search-view { display: flex; flex-direction: column; gap: var(--space-4); }
	.search-header { display: flex; justify-content: space-between; align-items: center; }
	.search-query { color: var(--text-secondary); font-size: var(--text-sm); }
	.result-count { color: var(--text-tertiary); font-size: var(--text-sm); }
	.result-list { display: flex; flex-direction: column; gap: var(--space-1); }
	.result-item { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); background: var(--bg-primary); border: none; border-radius: var(--radius-sm); cursor: pointer; text-align: left; width: 100%; transition: all 0.15s ease; }
	.result-item:hover { background: var(--radiant-gold-5); }
	.result-item:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
	.result-icon { font-size: var(--text-lg); }
	.result-text { flex: 1; color: var(--text-primary); font-size: var(--text-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.result-meta { color: var(--text-tertiary); font-size: var(--text-sm); }
	.empty-state { text-align: center; padding: var(--space-4); color: var(--text-tertiary); }
</style>
