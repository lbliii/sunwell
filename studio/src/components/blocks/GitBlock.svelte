<!--
  GitBlock — Git status/log/branches display (RFC-080)
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface GitFile { path: string; status: string; }
	interface Commit { hash: string; message: string; author: string; date: string; }
	interface Props {
		data: {
			branch?: string;
			files?: GitFile[];
			commits?: Commit[];
			local?: string[];
			remote?: string[];
			current?: string;
			is_clean?: boolean;
		};
		onAction?: (actionId: string, item?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function getStatusIcon(status: string): string {
		const icons: Record<string, string> = { modified: '✎', added: '+', deleted: '−', untracked: '?', renamed: '→' };
		return icons[status] || '•';
	}

	function handleStage(path: string) { onAction?.('stage', path); }
	function handleCommit() { onAction?.('commit'); }
	function handlePush() { onAction?.('push'); }
</script>

<div class="git-view">
	{#if data.branch}
		<header class="git-header">
			<div class="branch-info">
				<span class="branch-icon" aria-hidden="true">⎇</span>
				<span class="branch-name">{data.branch}</span>
				{#if data.is_clean}
					<span class="clean-badge">Clean</span>
				{/if}
			</div>
			<div class="git-actions">
				{#if !data.is_clean}
					<button class="action-btn" onclick={handleCommit}>Commit</button>
				{/if}
				<button class="action-btn" onclick={handlePush}>Push</button>
			</div>
		</header>
	{/if}

	{#if data.files && data.files.length > 0}
		<div class="file-list">
			<h4 class="section-title">Changed Files</h4>
			{#each data.files.slice(0, 8) as file, i (file.path)}
				<div class="git-file" in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }}>
					<span class="status-icon status-{file.status}" aria-hidden="true">{getStatusIcon(file.status)}</span>
					<span class="file-path">{file.path}</span>
					<button class="stage-btn" onclick={() => handleStage(file.path)} aria-label="Stage {file.path}">Stage</button>
				</div>
			{/each}
		</div>
	{/if}

	{#if data.commits && data.commits.length > 0}
		<div class="commit-list">
			<h4 class="section-title">Recent Commits</h4>
			{#each data.commits.slice(0, 5) as commit, i (commit.hash)}
				<div class="commit-item" in:fly={{ y: 10, delay: staggerDelay(i, 30), duration: 200 }}>
					<span class="commit-hash">{commit.hash.slice(0, 7)}</span>
					<span class="commit-message">{commit.message}</span>
				</div>
			{/each}
		</div>
	{/if}

	{#if !data.files?.length && !data.commits?.length && data.is_clean}
		<div class="empty-state"><p>Working tree clean</p></div>
	{/if}
</div>

<style>
	.git-view { display: flex; flex-direction: column; gap: var(--space-4); }
	.git-header { display: flex; justify-content: space-between; align-items: center; }
	.branch-info { display: flex; align-items: center; gap: var(--space-2); }
	.branch-icon { color: var(--gold); }
	.branch-name { color: var(--text-primary); font-weight: 600; font-family: var(--font-mono); }
	.clean-badge { padding: 2px 6px; background: rgba(34, 197, 94, 0.15); color: var(--success); font-size: var(--text-xs); border-radius: var(--radius-sm); }
	.git-actions { display: flex; gap: var(--space-2); }
	.action-btn { padding: var(--space-1) var(--space-2); background: var(--radiant-gold-10); border: 1px solid var(--radiant-gold-20); border-radius: var(--radius-sm); color: var(--gold); font-size: var(--text-xs); cursor: pointer; transition: all 0.15s ease; }
	.action-btn:hover { background: var(--radiant-gold-20); }
	.section-title { margin: 0 0 var(--space-2) 0; color: var(--text-secondary); font-size: var(--text-sm); font-weight: 500; }
	.file-list, .commit-list { display: flex; flex-direction: column; gap: var(--space-1); }
	.git-file { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); background: var(--bg-primary); border-radius: var(--radius-sm); }
	.status-icon { width: 16px; text-align: center; font-weight: bold; }
	.status-icon.status-modified { color: var(--warning); }
	.status-icon.status-added { color: var(--success); }
	.status-icon.status-deleted { color: var(--error); }
	.status-icon.status-untracked { color: var(--text-tertiary); }
	.file-path { flex: 1; color: var(--text-primary); font-family: var(--font-mono); font-size: var(--text-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.stage-btn { padding: 2px 8px; background: none; border: 1px solid var(--border-subtle); border-radius: var(--radius-sm); color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer; opacity: 0; transition: all 0.15s ease; }
	.git-file:hover .stage-btn { opacity: 1; }
	.stage-btn:hover { border-color: var(--gold); color: var(--gold); }
	.commit-item { display: flex; align-items: center; gap: var(--space-2); padding: var(--space-2); background: var(--bg-primary); border-radius: var(--radius-sm); }
	.commit-hash { color: var(--gold); font-family: var(--font-mono); font-size: var(--text-xs); }
	.commit-message { flex: 1; color: var(--text-primary); font-size: var(--text-sm); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.empty-state { text-align: center; padding: var(--space-4); color: var(--text-tertiary); }
</style>
