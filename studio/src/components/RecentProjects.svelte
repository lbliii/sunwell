<!--
  RecentProjects — List of recently opened projects
  
  Shown on the home screen with project type, name, and metadata.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { RecentProject } from '$lib/types';
  import { getProjectTypeEmoji } from '../stores/project';
  
  export let projects: RecentProject[] = [];
  
  const dispatch = createEventDispatcher<{ select: RecentProject }>();
  
  function formatTime(timestamp: number): string {
    const now = Date.now();
    const diff = now - timestamp;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 60) return `${minutes}m ago`;
    if (hours < 24) return `${hours}h ago`;
    if (days < 7) return `${days}d ago`;
    
    return new Date(timestamp).toLocaleDateString();
  }
  
  function handleSelect(project: RecentProject) {
    dispatch('select', project);
  }
</script>

{#if projects.length > 0}
  <div class="recent-projects">
    <h3 class="section-title">Recent</h3>
    <div class="project-list">
      {#each projects as project}
        <button 
          class="project-item"
          on:click={() => handleSelect(project)}
          type="button"
        >
          <span class="project-icon">{getProjectTypeEmoji(project.project_type)}</span>
          <span class="project-name">{project.name}</span>
          <span class="project-meta">{project.description}</span>
          <span class="project-time">{formatTime(project.last_opened)}</span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .recent-projects {
    width: 100%;
    max-width: 600px;
  }
  
  .section-title {
    color: var(--text-secondary);
    font-size: var(--text-sm);
    font-weight: 400;
    margin-bottom: var(--space-3);
  }
  
  .project-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .project-item {
    display: grid;
    grid-template-columns: auto 1fr auto auto;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: none;
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    text-align: left;
    cursor: pointer;
    transition: background var(--transition-fast), color var(--transition-fast);
  }
  
  .project-item:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
  }
  
  .project-icon {
    font-size: var(--text-base);
  }
  
  .project-name {
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .project-meta {
    color: var(--text-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 200px;
  }
  
  .project-time {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
</style>
