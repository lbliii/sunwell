<!--
  NotesBlock — Notes preview with open/create (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface Note { id: string; title: string; content: string; tags?: string[]; modified?: string; }
	interface Props {
		data: { notes: Note[]; mode?: string; };
		onAction?: (actionId: string, noteId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function handleOpen(noteId: string) { onAction?.('open', noteId); }
	function handleCreate() { onAction?.('create'); }

	function getPreview(content: string, maxLen = 100): string {
		if (content.length <= maxLen) return content;
		return content.slice(0, maxLen).trim() + '...';
	}
</script>

<div class="notes-view">
	<header class="notes-header">
		<h3 class="notes-title">Notes</h3>
		<button class="create-btn" onclick={handleCreate} aria-label="Create note">+ New</button>
	</header>

	{#if data.notes.length > 0}
		<div class="note-list">
			{#each data.notes.slice(0, 5) as note, i (note.id)}
				<button class="note-card" in:fly={{ y: 15, delay: staggerDelay(i), duration: 250 }} onclick={() => handleOpen(note.id)}>
					<span class="note-title">{note.title}</span>
					<span class="note-preview">{getPreview(note.content)}</span>
					{#if note.tags && note.tags.length > 0}
						<div class="note-tags">
							{#each note.tags.slice(0, 3) as tag}
								<span class="tag">{tag}</span>
							{/each}
						</div>
					{/if}
				</button>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No notes found</p></div>
	{/if}
</div>

<style>
	.notes-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.notes-header { display: flex; justify-content: space-between; align-items: center; }
	.notes-title { margin: 0; font-size: var(--text-lg, 18px); font-weight: 600; color: var(--text-primary, #fff); }
	.create-btn { padding: var(--space-1, 4px) var(--space-2, 8px); background: rgba(255, 215, 0, 0.1); border: 1px solid rgba(255, 215, 0, 0.2); border-radius: var(--radius-sm, 4px); color: var(--gold, #ffd700); font-size: var(--text-sm, 14px); cursor: pointer; transition: all 0.15s ease; }
	.create-btn:hover { background: rgba(255, 215, 0, 0.2); }
	.note-list { display: flex; flex-direction: column; gap: var(--space-2, 8px); }
	.note-card { display: flex; flex-direction: column; gap: var(--space-1, 4px); padding: var(--space-3, 12px); background: var(--bg-primary, #0a0a0a); border: none; border-radius: var(--radius-md, 8px); cursor: pointer; text-align: left; transition: all 0.2s ease; }
	.note-card:hover { background: rgba(255, 215, 0, 0.05); }
	.note-card:focus-visible { outline: 2px solid var(--gold, #ffd700); outline-offset: 2px; }
	.note-title { color: var(--text-primary, #fff); font-weight: 600; font-size: var(--text-base, 16px); }
	.note-preview { color: var(--text-secondary, #999); font-size: var(--text-sm, 14px); line-height: 1.4; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
	.note-tags { display: flex; gap: var(--space-1, 4px); margin-top: var(--space-1, 4px); }
	.tag { padding: 2px 6px; background: var(--bg-secondary, #1e1e1e); color: var(--text-tertiary, #666); font-size: var(--text-xs, 12px); border-radius: var(--radius-sm, 4px); }
	.empty-state { text-align: center; padding: var(--space-4, 16px); color: var(--text-tertiary, #666); }
</style>
