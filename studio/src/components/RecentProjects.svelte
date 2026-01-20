<!--
  RecentProjects — List of projects with status and Resume capability
  
  Shows projects from ~/Sunwell/projects/ with execution status.
  Interrupted projects can be resumed directly.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { createEventDispatcher } from 'svelte';
  import type { ProjectStatus } from '$lib/types';
  
  export let projects: ProjectStatus[] = [];
  export let loading = false;
  
  const dispatch = createEventDispatcher<{ 
    select: ProjectStatus;
    resume: ProjectStatus;
  }>();
  
  function formatTime(timestamp: string | null): string {
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
  
  function getStatusInfo(status: string): { icon: string; label: string; class: string } {
    switch (status) {
      case 'interrupted':
        return { icon: '||', label: 'Interrupted', class: 'status-interrupted' };
      case 'complete':
        return { icon: '[ok]', label: 'Complete', class: 'status-complete' };
      case 'failed':
        return { icon: '[x]', label: 'Failed', class: 'status-failed' };
      default:
        return { icon: '--', label: '', class: 'status-none' };
    }
  }
  
  function handleSelect(project: ProjectStatus) {
    dispatch('select', project);
  }
  
  function handleResume(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    dispatch('resume', project);
  }
</script>

<div class="projects-section">
  <div class="section-header">
    <h3 class="section-title">Projects</h3>
    <span class="section-path">~/Sunwell/projects/</span>
  </div>
  
  {#if loading}
    <div class="loading">Scanning projects...</div>
  {:else if projects.length === 0}
    <div class="empty">
      <p>No projects yet</p>
      <p class="hint">Enter a goal above to create your first project</p>
    </div>
  {:else}
    <div class="project-list">
      {#each projects as project}
        {@const statusInfo = getStatusInfo(project.status)}
        <button 
          class="project-item"
          on:click={() => handleSelect(project)}
          type="button"
        >
          <div class="project-main">
            <span class="project-icon">{statusInfo.icon}</span>
            <span class="project-name">{project.name}</span>
            {#if statusInfo.label}
              <span class="project-status {statusInfo.class}">{statusInfo.label}</span>
            {/if}
          </div>
          
          <div class="project-details">
            {#if project.last_goal}
              <span class="project-goal" title={project.last_goal}>
                {project.last_goal.slice(0, 40)}{project.last_goal.length > 40 ? '...' : ''}
              </span>
            {/if}
            
            {#if project.tasks_completed !== null && project.tasks_total !== null}
              <span class="project-progress">
                {project.tasks_completed}/{project.tasks_total} tasks
              </span>
            {/if}
            
            <span class="project-time">{formatTime(project.last_activity)}</span>
          </div>
          
          {#if project.status === 'interrupted'}
            <button 
              class="resume-button"
              on:click={(e) => handleResume(e, project)}
              type="button"
            >
              Resume
            </button>
          {/if}
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .projects-section {
    width: 100%;
    max-width: 700px;
  }
  
  .section-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin-bottom: var(--space-3);
  }
  
  .section-title {
    color: var(--text-primary);
    font-size: var(--text-base);
    font-weight: 500;
    margin: 0;
  }
  
  .section-path {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-family: var(--font-mono);
  }
  
  .loading, .empty {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    text-align: center;
    padding: var(--space-6) var(--space-4);
  }
  
  .empty .hint {
    margin-top: var(--space-2);
    font-size: var(--text-xs);
  }
  
  .project-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .project-item {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    text-align: left;
    cursor: pointer;
    transition: all var(--transition-fast);
    position: relative;
  }
  
  .project-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
    color: var(--text-primary);
  }
  
  .project-main {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .project-icon {
    font-size: var(--text-base);
    width: 24px;
    text-align: center;
  }
  
  .project-name {
    font-weight: 500;
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }
  
  .project-status {
    font-size: var(--text-xs);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    margin-left: auto;
  }
  
  .status-interrupted {
    background: rgba(255, 170, 0, 0.15);
    color: #ffaa00;
  }
  
  .status-complete {
    background: rgba(0, 200, 100, 0.15);
    color: #00c864;
  }
  
  .status-failed {
    background: rgba(255, 80, 80, 0.15);
    color: #ff5050;
  }
  
  .project-details {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding-left: calc(24px + var(--space-2));
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .project-goal {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .project-progress {
    color: var(--text-secondary);
  }
  
  .project-time {
    white-space: nowrap;
  }
  
  .resume-button {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    background: var(--accent-primary);
    color: var(--text-primary);
    border: none;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
    opacity: 0;
  }
  
  .project-item:hover .resume-button {
    opacity: 1;
  }
  
  .resume-button:hover {
    background: var(--accent-hover);
  }
</style>
