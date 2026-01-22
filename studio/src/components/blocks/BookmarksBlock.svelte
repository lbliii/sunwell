<!--
  BookmarksBlock — Bookmarks with quick open/delete (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface Bookmark { id: string; title: string; url: string; tags?: string[]; }
	interface Props {
		data: { bookmarks: Bookmark[]; all_tags?: string[]; };
		onAction?: (actionId: string, bookmarkId?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function getDomain(url: string): string {
		try { return new URL(url).hostname.replace('www.', ''); }
		catch { return url.slice(0, 30); }
	}

	function handleOpen(bookmarkId: string) { onAction?.('open', bookmarkId); }
	function handleDelete(bookmarkId: string) { onAction?.('delete', bookmarkId); }
</script>

<div class="bookmarks-view">
	<header class="bookmarks-header">
		<h3 class="bookmarks-title">Bookmarks</h3>
		<span class="bookmarks-count">{data.bookmarks.length} saved</span>
	</header>

	{#if data.bookmarks.length > 0}
		<div class="bookmark-list">
			{#each data.bookmarks.slice(0, 8) as bookmark, i (bookmark.id)}
				<div class="bookmark-item" in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }}>
					<button class="bookmark-main" onclick={() => handleOpen(bookmark.id)}>
						<span class="bookmark-icon" aria-hidden="true">🔗</span>
						<div class="bookmark-info">
							<span class="bookmark-title">{bookmark.title}</span>
							<span class="bookmark-domain">{getDomain(bookmark.url)}</span>
						</div>
					</button>
					<button class="delete-btn" onclick={() => handleDelete(bookmark.id)} aria-label="Delete {bookmark.title}">✕</button>
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No bookmarks saved</p></div>
	{/if}
</div>

<style>
	.bookmarks-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.bookmarks-header { display: flex; justify-content: space-between; align-items: center; }
	.bookmarks-title { margin: 0; font-size: var(--text-lg, 18px); font-weight: 600; color: var(--text-primary, #fff); }
	.bookmarks-count { color: var(--text-tertiary, #666); font-size: var(--text-sm, 14px); }
	.bookmark-list { display: flex; flex-direction: column; gap: var(--space-1, 4px); }
	.bookmark-item { display: flex; align-items: center; background: var(--bg-primary, #0a0a0a); border-radius: var(--radius-sm, 4px); transition: all 0.15s ease; }
	.bookmark-item:hover { background: rgba(255, 215, 0, 0.05); }
	.bookmark-main { flex: 1; display: flex; align-items: center; gap: var(--space-2, 8px); padding: var(--space-2, 8px); background: none; border: none; cursor: pointer; text-align: left; }
	.bookmark-icon { font-size: var(--text-base, 16px); }
	.bookmark-info { flex: 1; display: flex; flex-direction: column; min-width: 0; }
	.bookmark-title { color: var(--text-primary, #fff); font-size: var(--text-sm, 14px); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.bookmark-domain { color: var(--text-tertiary, #666); font-size: var(--text-xs, 12px); }
	.delete-btn { background: none; border: none; color: var(--text-tertiary, #666); cursor: pointer; padding: var(--space-2, 8px); opacity: 0; transition: all 0.15s ease; }
	.bookmark-item:hover .delete-btn { opacity: 1; }
	.delete-btn:hover { color: var(--error, #ef4444); }
	.empty-state { text-align: center; padding: var(--space-4, 16px); color: var(--text-tertiary, #666); }
</style>
