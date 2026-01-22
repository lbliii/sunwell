<!--
  ListBlock — Todo/shopping list with check/add/delete (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface ListItem { id: string; text: string; completed: boolean; }
	interface Props {
		data: { items: ListItem[]; list_name?: string; };
		onAction?: (actionId: string, itemId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function handleCheck(itemId: string) { onAction?.('check', itemId); }
	function handleAdd() { onAction?.('add'); }
	function handleDelete(itemId: string) { onAction?.('delete', itemId); }
</script>

<div class="list-view">
	<header class="list-header">
		<h3 class="list-title">{data.list_name || 'List'}</h3>
		<button class="add-btn" onclick={handleAdd} aria-label="Add item">+ Add</button>
	</header>

	{#if data.items.length > 0}
		<div class="item-list">
			{#each data.items as item, i (item.id)}
				<div class="list-item" class:completed={item.completed} in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }}>
					<button class="check-btn" onclick={() => handleCheck(item.id)} aria-label={item.completed ? 'Uncheck' : 'Check'}>
						<span class="check-icon" aria-hidden="true">{item.completed ? '✓' : '○'}</span>
					</button>
					<span class="item-text">{item.text}</span>
					<button class="delete-btn" onclick={() => handleDelete(item.id)} aria-label="Delete item">✕</button>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No items</p></div>
	{/if}
</div>

<style>
	.list-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.list-header { display: flex; justify-content: space-between; align-items: center; }
	.list-title { margin: 0; font-size: var(--text-lg, 18px); font-weight: 600; color: var(--gold, #ffd700); text-transform: capitalize; }
	.add-btn { padding: var(--space-1, 4px) var(--space-2, 8px); background: rgba(255, 215, 0, 0.1); border: 1px solid rgba(255, 215, 0, 0.2); border-radius: var(--radius-sm, 4px); color: var(--gold, #ffd700); font-size: var(--text-sm, 14px); cursor: pointer; transition: all 0.15s ease; }
	.add-btn:hover { background: rgba(255, 215, 0, 0.2); }
	.item-list { display: flex; flex-direction: column; gap: var(--space-1, 4px); }
	.list-item { display: flex; align-items: center; gap: var(--space-2, 8px); padding: var(--space-2, 8px); background: var(--bg-primary, #0a0a0a); border-radius: var(--radius-sm, 4px); transition: all 0.15s ease; }
	.list-item:hover { background: rgba(255, 215, 0, 0.05); }
	.list-item.completed { opacity: 0.6; }
	.check-btn { background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; justify-content: center; }
	.check-icon { font-size: var(--text-lg, 18px); color: var(--text-tertiary, #666); transition: color 0.15s ease; }
	.list-item.completed .check-icon { color: var(--success, #22c55e); }
	.item-text { flex: 1; color: var(--text-primary, #fff); font-size: var(--text-sm, 14px); }
	.list-item.completed .item-text { text-decoration: line-through; color: var(--text-tertiary, #666); }
	.delete-btn { background: none; border: none; color: var(--text-tertiary, #666); cursor: pointer; padding: var(--space-1, 4px); opacity: 0; transition: all 0.15s ease; }
	.list-item:hover .delete-btn { opacity: 1; }
	.delete-btn:hover { color: var(--error, #ef4444); }
	.empty-state { text-align: center; padding: var(--space-4, 16px); color: var(--text-tertiary, #666); }
</style>
