<!--
  ProjectDetail — Detail panel for a selected project (RFC-096)
-->
<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  import Button from '../Button.svelte';
  
  interface Props {
    project: ProjectStatus | null;
    onOpenProject?: (path: string) => void;
    onResumeProject?: (path: string) => void;
    onIterateProject?: (path: string) => void;
    onArchiveProject?: (path: string) => void;
    onDeleteProject?: (path: string) => void;
  }
  
  let { 
    project, 
    onOpenProject,
    onResumeProject,
    onIterateProject,
    onArchiveProject,
    onDeleteProject,
  }: Props = $props();
  
  function getStatusInfo(status: string | null | undefined): { icon: string; label: string; class: string } {
    switch (status) {
      case 'interrupted':
        return { icon: '▸▸', label: 'Interrupted', class: 'status-interrupted' };
      case 'complete':
        return { icon: '✓', label: 'Complete', class: 'status-complete' };
      case 'failed':
        return { icon: '✕', label: 'Failed', class: 'status-failed' };
      default:
        return { icon: '○', label: 'Active', class: 'status-active' };
    }
  }
  
  function formatTime(timestamp: string | null | undefined): string {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    return date.toLocaleString();
  }
  
  const statusInfo = $derived(project ? getStatusInfo(project.status) : null);
</script>

{#if project}
  <div class="project-detail">
    <header class="detail-header">
      <span class="status-icon {statusInfo?.class}" aria-hidden="true">
        {statusInfo?.icon}
      </span>
      <div class="header-info">
        <h3 class="project-name">{project.name}</h3>
        {#if project.id}
          <span class="project-id">#{project.id.slice(0, 8)}</span>
        {/if}
      </div>
      {#if statusInfo?.label}
        <span class="status-badge {statusInfo.class}">{statusInfo.label}</span>
      {/if}
    </header>
    
    {#if project.last_goal}
      <section class="detail-section">
        <h4 class="section-label">Goal</h4>
        <p class="goal-text">{project.last_goal}</p>
      </section>
    {/if}
    
    <section class="detail-section">
      <h4 class="section-label">Progress</h4>
      <div class="progress-info">
        {#if project.tasks_completed != null && project.tasks_total != null}
          <div class="progress-bar">
            <div 
              class="progress-fill"
              style="width: {project.tasks_total > 0 ? (project.tasks_completed / project.tasks_total * 100) : 0}%"
            ></div>
          </div>
          <span class="progress-text">
            {project.tasks_completed} / {project.tasks_total} tasks
          </span>
        {:else}
          <span class="progress-text">No tasks tracked</span>
        {/if}
      </div>
    </section>
    
    <section class="detail-section">
      <h4 class="section-label">Location</h4>
      <code class="path-text">{project.display_path || project.path}</code>
    </section>
    
    <section class="detail-section">
      <h4 class="section-label">Last Activity</h4>
      <span class="time-text">{formatTime(project.last_activity)}</span>
    </section>
    
    <footer class="detail-actions">
      <Button 
        variant="primary"
        onclick={() => onOpenProject?.(project.path)}
      >
        Open Project
      </Button>
      
      {#if project.status === 'interrupted'}
        <Button 
          variant="secondary"
          onclick={() => onResumeProject?.(project.path)}
        >
          Resume
        </Button>
      {/if}
      
      <div class="secondary-actions">
        <Button 
          variant="ghost"
          size="sm"
          onclick={() => onIterateProject?.(project.path)}
        >
          ↻ Iterate
        </Button>
        <Button 
          variant="ghost"
          size="sm"
          onclick={() => onArchiveProject?.(project.path)}
        >
          ⌂ Archive
        </Button>
        <Button 
          variant="ghost"
          size="sm"
          onclick={() => onDeleteProject?.(project.path)}
        >
          ✕ Delete
        </Button>
      </div>
    </footer>
  </div>
{:else}
  <div class="no-selection">
    <p>Select a project to view details</p>
  </div>
{/if}

<style>
  .project-detail {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
  }
  
  .detail-header {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .status-icon {
    font-size: var(--text-lg);
  }
  
  .status-icon.status-interrupted { color: var(--warning); }
  .status-icon.status-complete { color: var(--success); }
  .status-icon.status-failed { color: var(--error); }
  .status-icon.status-active { color: var(--text-tertiary); }
  
  .header-info {
    flex: 1;
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
  }
  
  .project-name {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    font-family: var(--font-mono);
    color: var(--text-primary);
  }
  
  .project-id {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .status-badge {
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .status-badge.status-interrupted {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
  }
  
  .status-badge.status-complete {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
  }
  
  .status-badge.status-failed {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }
  
  .detail-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .section-label {
    margin: 0;
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .goal-text {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.5;
  }
  
  .progress-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .progress-bar {
    height: 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--gradient-ui-gold, linear-gradient(135deg, #d4b046, #c9a227));
    border-radius: var(--radius-sm);
    transition: width 0.3s ease;
  }
  
  .progress-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .path-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    word-break: break-all;
  }
  
  .time-text {
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }
  
  .detail-actions {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-top: var(--space-2);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-subtle);
  }
  
  .secondary-actions {
    display: flex;
    gap: var(--space-2);
  }
  
  .no-selection {
    padding: var(--space-8);
    text-align: center;
    color: var(--text-tertiary);
  }
</style>
