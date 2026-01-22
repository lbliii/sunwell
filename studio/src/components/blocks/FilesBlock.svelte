<!--
  FilesBlock — File list with quick open/preview (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface FileInfo {
		name: string;
		path: string;
		type: 'file' | 'directory';
		size?: number;
		modified?: string;
	}

	interface Props {
		data: {
			files: FileInfo[];
			path: string;
			file_count: number;
		};
		onAction?: (actionId: string, filePath?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function getFileIcon(file: FileInfo): string {
		if (file.type === 'directory') return '📁';
		const ext = file.name.split('.').pop()?.toLowerCase();
		const icons: Record<string, string> = {
			py: '🐍', js: '📜', ts: '📘', md: '📝', json: '📋',
			html: '🌐', css: '🎨', svg: '🖼️', png: '🖼️', jpg: '🖼️',
		};
		return icons[ext || ''] || '📄';
	}

	function formatSize(bytes?: number): string {
		if (!bytes) return '';
		if (bytes < 1024) return `${bytes} B`;
		if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
		return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
	}

	function handleOpen(filePath: string) { onAction?.('open', filePath); }
	function handlePreview(filePath: string) { onAction?.('preview', filePath); }
</script>

<div class="files-view">
	<header class="files-header">
		<h3 class="files-title">Files</h3>
		<span class="files-path">{data.path}</span>
	</header>

	{#if data.files.length > 0}
		<div class="file-list">
			{#each data.files.slice(0, 10) as file, i (file.path)}
				<button
					class="file-item"
					in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }}
					onclick={() => handleOpen(file.path)}
				>
					<span class="file-icon" aria-hidden="true">{getFileIcon(file)}</span>
					<span class="file-name">{file.name}</span>
					{#if file.size}
						<span class="file-size">{formatSize(file.size)}</span>
					{/if}
				</button>
			{/each}
		</div>
	{:else}
		<div class="empty-state"><p>No files</p></div>
	{/if}
</div>

<style>
	.files-view { display: flex; flex-direction: column; gap: var(--space-4, 16px); }
	.files-header { display: flex; justify-content: space-between; align-items: center; }
	.files-title { margin: 0; font-size: var(--text-lg, 18px); font-weight: 600; color: var(--text-primary, #fff); }
	.files-path { color: var(--text-tertiary, #666); font-size: var(--text-xs, 12px); font-family: var(--font-mono, monospace); }
	.file-list { display: flex; flex-direction: column; gap: var(--space-1, 4px); }
	.file-item {
		display: flex; align-items: center; gap: var(--space-2, 8px);
		padding: var(--space-2, 8px); background: var(--bg-primary, #0a0a0a);
		border: none; border-radius: var(--radius-sm, 4px);
		cursor: pointer; transition: all 0.15s ease; text-align: left; width: 100%;
	}
	.file-item:hover { background: rgba(255, 215, 0, 0.05); }
	.file-item:focus-visible { outline: 2px solid var(--gold, #ffd700); outline-offset: 2px; }
	.file-icon { font-size: var(--text-base, 16px); }
	.file-name { flex: 1; color: var(--text-primary, #fff); font-family: var(--font-mono, monospace); font-size: var(--text-sm, 14px); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.file-size { color: var(--text-tertiary, #666); font-size: var(--text-xs, 12px); }
	.empty-state { text-align: center; padding: var(--space-4, 16px); color: var(--text-tertiary, #666); }
</style>
