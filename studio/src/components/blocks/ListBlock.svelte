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
	.list-view { display: flex; flex-direction: column; gap: var(--space-4); }
	.list-header { display: flex; justify-content: space-between; align-items: center; }
	.list-title { margin: 0; font-size: var(--text-lg); font-weight: 600; color: var(--gold); text-transform: capitalize; }
	.add-btn { padding: var(--space-1) var(--space-2); background: var(--radiant-gold-10); border: 1px solid var(--radiant-gold-20); border-radius: var(--radius-sm); color: var(--gold); font-size: var(--text-sm); cursor: pointer; transition: all 0.15s ease; }
	.add-btn:hover { background: var(--radiant-gold-20); }
	.item-list { display: flex; flex-direction: column; gap: var(--space-1); }
	.list-item { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); background: var(--bg-primary); border-radius: var(--radius-sm); transition: all 0.15s ease; }
	.list-item:hover { background: var(--radiant-gold-5); }
	.list-item.completed { opacity: 0.6; }
	.check-btn { background: none; border: none; cursor: pointer; padding: 0; display: flex; align-items: center; justify-content: center; }
	.check-icon { font-size: var(--text-lg); color: var(--text-tertiary); transition: color 0.15s ease; }
	.list-item.completed .check-icon { color: var(--success); }
	.item-text { flex: 1; color: var(--text-primary); font-size: var(--text-sm); }
	.list-item.completed .item-text { text-decoration: line-through; color: var(--text-tertiary); }
	.delete-btn { background: none; border: none; color: var(--text-tertiary); cursor: pointer; padding: var(--space-1); opacity: 0; transition: all 0.15s ease; }
	.list-item:hover .delete-btn { opacity: 1; }
	.delete-btn:hover { color: var(--error); }
	.empty-state { text-align: center; padding: var(--space-4); color: var(--text-tertiary); }
</style>
