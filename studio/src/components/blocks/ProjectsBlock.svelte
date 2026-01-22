<!--
  ProjectsBlock — Recent projects with quick actions (RFC-080)
  
  Shows project cards with:
  - Status indicators
  - Progress info
  - Quick open/resume actions
-->
<script lang="ts">
	import { fly } from 'svelte/transition';
	import { staggerDelay } from '$lib/tetris';

	interface Project {
		id?: string;
		name: string;
		path: string;
		status?: 'interrupted' | 'complete' | 'failed' | null;
		last_goal?: string;
		last_activity?: string;
		tasks_completed?: number;
		tasks_total?: number;
	}

	interface Props {
		data: {
			projects: Project[];
			project_count: number;
		};
		onAction?: (actionId: string, projectPath?: string) => void;
	}

	let { data, onAction }: Props = $props();

	function handleOpen(projectPath: string) {
		onAction?.('open', projectPath);
	}

	function handleResume(projectPath: string) {
		onAction?.('resume', projectPath);
	}

	function handleArchive(projectPath: string) {
		onAction?.('archive', projectPath);
	}

	function formatTime(timestamp: string | null | undefined): string {
		if (!timestamp) return '';
		const date = new Date(timestamp);
		const now = Date.now();
		const diff = now - date.getTime();

		const minutes = Math.floor(diff / 60000);
		const hours = Math.floor(diff / 3600000);
		const days = Math.floor(diff / 86400000);

		if (minutes < 60) return `${minutes}m ago`;
		if (hours < 24) return `${hours}h ago`;
		if (days < 7) return `${days}d ago`;

		return date.toLocaleDateString();
	}

	function getStatusInfo(status: string | null | undefined): { icon: string; label: string; class: string } {
		switch (status) {
			case 'interrupted':
				return { icon: '||', label: 'Interrupted', class: 'status-interrupted' };
			case 'complete':
				return { icon: '✓', label: 'Complete', class: 'status-complete' };
			case 'failed':
				return { icon: '✕', label: 'Failed', class: 'status-failed' };
			default:
				return { icon: '○', label: '', class: 'status-none' };
		}
	}
</script>

<div class="projects-view">
	<header class="projects-header">
		<h3 class="projects-title">Projects</h3>
		<span class="projects-count">{data.project_count} total</span>
	</header>

	{#if data.projects.length > 0}
		<div class="project-list">
			{#each data.projects.slice(0, 6) as project, i (project.path)}
				{@const statusInfo = getStatusInfo(project.status)}
				<div
					class="project-card"
					in:fly={{ y: 15, delay: staggerDelay(i), duration: 250 }}
				>
					<button
						class="project-main"
						onclick={() => handleOpen(project.path)}
						aria-label="Open project {project.name}"
					>
						<span class="project-icon {statusInfo.class}" aria-hidden="true">
							{statusInfo.icon}
						</span>
						<div class="project-info">
							<span class="project-name">{project.name}</span>
							{#if project.last_goal}
								<span class="project-goal">
									{project.last_goal.slice(0, 40)}{project.last_goal.length > 40 ? '...' : ''}
								</span>
							{/if}
						</div>
						<div class="project-meta">
							{#if project.tasks_completed != null && project.tasks_total != null}
								<span class="project-progress">
									{project.tasks_completed}/{project.tasks_total}
								</span>
							{/if}
							<span class="project-time">{formatTime(project.last_activity)}</span>
						</div>
					</button>

					{#if project.status === 'interrupted'}
						<button
							class="action-btn resume"
							onclick={() => handleResume(project.path)}
							aria-label="Resume {project.name}"
						>
							Resume
						</button>
					{/if}
				</div>
			{/each}
		</div>
	{:else}
		<div class="empty-state">
			<p>No projects yet</p>
			<p class="hint">Enter a goal above to create your first project</p>
		</div>
	{/if}
</div>

<style>
	.projects-view {
		display: flex;
		flex-direction: column;
		gap: var(--space-4, 16px);
	}

	.projects-header {
		display: flex;
		justify-content: space-between;
		align-items: center;
	}

	.projects-title {
		margin: 0;
		font-size: var(--text-lg, 18px);
		font-weight: 600;
		color: var(--text-primary, #fff);
	}

	.projects-count {
		color: var(--text-tertiary, #666);
		font-size: var(--text-sm, 14px);
	}

	.project-list {
		display: flex;
		flex-direction: column;
		gap: var(--space-2, 8px);
	}

	.project-card {
		display: flex;
		align-items: center;
		gap: var(--space-2, 8px);
		background: var(--bg-secondary, #1e1e1e);
		border: 1px solid var(--border-subtle, #333);
		border-radius: var(--radius-md, 8px);
		transition: all 0.2s ease;
	}

	.project-card:hover {
		background: var(--bg-tertiary, #2a2a2a);
		border-color: var(--border-default, #444);
	}

	.project-main {
		flex: 1;
		display: flex;
		align-items: center;
		gap: var(--space-3, 12px);
		padding: var(--space-3, 12px);
		background: none;
		border: none;
		color: inherit;
		text-align: left;
		cursor: pointer;
		min-width: 0;
	}

	.project-icon {
		width: 24px;
		text-align: center;
		font-size: var(--text-base, 16px);
		flex-shrink: 0;
	}

	.project-icon.status-interrupted {
		color: var(--warning, #f59e0b);
	}

	.project-icon.status-complete {
		color: var(--success, #22c55e);
	}

	.project-icon.status-failed {
		color: var(--error, #ef4444);
	}

	.project-icon.status-none {
		color: var(--text-tertiary, #666);
	}

	.project-info {
		flex: 1;
		display: flex;
		flex-direction: column;
		gap: 2px;
		min-width: 0;
	}

	.project-name {
		color: var(--text-primary, #fff);
		font-weight: 500;
		font-family: var(--font-mono, monospace);
		font-size: var(--text-sm, 14px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.project-card:hover .project-name {
		color: var(--gold, #ffd700);
	}

	.project-goal {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
		white-space: nowrap;
		overflow: hidden;
		text-overflow: ellipsis;
	}

	.project-meta {
		display: flex;
		flex-direction: column;
		align-items: flex-end;
		gap: 2px;
		flex-shrink: 0;
	}

	.project-progress {
		color: var(--text-secondary, #999);
		font-size: var(--text-xs, 12px);
	}

	.project-time {
		color: var(--text-tertiary, #666);
		font-size: var(--text-xs, 12px);
	}

	.action-btn {
		padding: var(--space-1, 4px) var(--space-3, 12px);
		margin-right: var(--space-2, 8px);
		border-radius: var(--radius-sm, 4px);
		font-size: var(--text-xs, 12px);
		font-weight: 500;
		cursor: pointer;
		transition: all 0.15s ease;
	}

	.action-btn.resume {
		background: var(--gradient-ui-gold, linear-gradient(135deg, #d4b046, #c9a227));
		color: var(--bg-primary, #0a0a0a);
		border: 1px solid rgba(201, 162, 39, 0.3);
	}

	.action-btn.resume:hover {
		box-shadow: 0 0 12px rgba(255, 215, 0, 0.3);
	}

	.action-btn:focus-visible {
		outline: 2px solid var(--gold, #ffd700);
		outline-offset: 2px;
	}

	.empty-state {
		text-align: center;
		padding: var(--space-6, 24px);
		color: var(--text-tertiary, #666);
	}

	.empty-state .hint {
		margin-top: var(--space-2, 8px);
		font-size: var(--text-xs, 12px);
	}
</style>
