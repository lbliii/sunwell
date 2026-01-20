<!--
  RecentProjects — List of projects with status, Resume, and management actions
  
  Shows projects from ~/Sunwell/projects/ with execution status.
  Supports: Resume, Iterate, Archive, Delete actions.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  import type { ProjectStatus } from '$lib/types';
  
  export let projects: ProjectStatus[] = [];
  export let loading = false;
  
  const dispatch = createEventDispatcher<{ 
    select: ProjectStatus;
    resume: ProjectStatus;
    iterate: ProjectStatus;
    archive: ProjectStatus;
    delete: ProjectStatus;
  }>();
  
  // Track which project's menu is open
  let openMenuId: string | null = null;
  
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
    if (openMenuId) {
      openMenuId = null;
      return;
    }
    dispatch('select', project);
  }
  
  function handleResume(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    dispatch('resume', project);
  }
  
  function toggleMenu(event: Event, projectPath: string) {
    event.stopPropagation();
    openMenuId = openMenuId === projectPath ? null : projectPath;
  }
  
  function handleIterate(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    dispatch('iterate', project);
  }
  
  function handleArchive(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    dispatch('archive', project);
  }
  
  function handleDelete(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    dispatch('delete', project);
  }
  
  // Close menu when clicking outside
  function handleClickOutside(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.action-menu') && !target.closest('.menu-trigger')) {
      openMenuId = null;
    }
  }
</script>

<svelte:window on:click={handleClickOutside} />

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
        <div 
          class="project-item"
          class:menu-open={openMenuId === project.path}
          role="button"
          tabindex="0"
          on:click={() => handleSelect(project)}
          on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && handleSelect(project)}
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
          
          <!-- Action buttons -->
          <div class="project-actions">
            {#if project.status === 'interrupted'}
              <span 
                class="action-button resume-button"
                role="button"
                tabindex="0"
                on:click={(e) => handleResume(e, project)}
                on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && handleResume(e, project)}
              >
                Resume
              </span>
            {/if}
            
            <!-- More actions menu trigger -->
            <span
              class="action-button menu-trigger"
              role="button"
              tabindex="0"
              on:click={(e) => toggleMenu(e, project.path)}
              on:keydown={(e) => (e.key === 'Enter' || e.key === ' ') && toggleMenu(e, project.path)}
              title="More actions"
            >
              ···
            </span>
            
            <!-- Dropdown menu -->
            {#if openMenuId === project.path}
              <div class="action-menu">
                <button 
                  class="menu-item iterate"
                  on:click={(e) => handleIterate(e, project)}
                  title="New version from learnings"
                >
                  <span class="menu-icon">↻</span>
                  <span class="menu-label">Iterate</span>
                </button>
                
                <button 
                  class="menu-item archive"
                  on:click={(e) => handleArchive(e, project)}
                  title="Move to ~/Sunwell/archived/"
                >
                  <span class="menu-icon">⌂</span>
                  <span class="menu-label">Archive</span>
                </button>
                
                <button 
                  class="menu-item delete"
                  on:click={(e) => handleDelete(e, project)}
                  title="Remove permanently"
                >
                  <span class="menu-icon">✕</span>
                  <span class="menu-label">Delete</span>
                </button>
              </div>
            {/if}
          </div>
        </div>
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
  
  .project-item.menu-open {
    z-index: 50;
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
  
  /* Action buttons container */
  .project-actions {
    position: absolute;
    right: var(--space-3);
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    opacity: 0;
    transition: opacity var(--transition-fast);
  }
  
  .project-item:hover .project-actions {
    opacity: 1;
  }
  
  .action-button {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    font-size: var(--text-xs);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .action-button:hover {
    background: var(--bg-secondary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .resume-button {
    background: var(--accent-primary);
    color: var(--text-primary);
    border-color: var(--accent-primary);
  }
  
  .resume-button:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
  }
  
  .menu-trigger {
    min-width: 28px;
    text-align: center;
    letter-spacing: 1px;
    font-size: var(--text-sm);
  }
  
  /* Dropdown menu - compact horizontal */
  .action-menu {
    position: absolute;
    top: calc(100% + var(--space-1));
    right: 0;
    display: flex;
    align-items: center;
    gap: 1px;
    background: var(--border-subtle);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    z-index: 100;
    overflow: hidden;
    animation: menuSlide 0.12s ease;
  }
  
  @keyframes menuSlide {
    from {
      opacity: 0;
      transform: translateY(-2px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .menu-item {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all var(--transition-fast);
    white-space: nowrap;
  }
  
  .menu-item:hover {
    color: var(--text-primary);
  }
  
  .menu-item .menu-icon {
    font-size: var(--text-sm);
  }
  
  .menu-item .menu-label {
    font-weight: 500;
  }
  
  .menu-item.iterate:hover {
    background: rgba(100, 180, 255, 0.1);
    color: #64b4ff;
  }
  
  .menu-item.archive:hover {
    background: rgba(255, 180, 100, 0.1);
    color: #ffb464;
  }
  
  .menu-item.delete:hover {
    background: rgba(255, 100, 100, 0.1);
    color: #ff6464;
  }
</style>
