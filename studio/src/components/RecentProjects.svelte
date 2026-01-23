<!--
  RecentProjects — List of projects with status, Resume, and management actions (Svelte 5)
  
  Shows projects from ~/Sunwell/projects/ with execution status.
  Supports: Resume, Iterate, Archive, Delete actions.
-->
<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  
  interface Props {
    projects?: ProjectStatus[];
    loading?: boolean;
    onselect?: (project: ProjectStatus) => void;
    onresume?: (project: ProjectStatus) => void;
    oniterate?: (project: ProjectStatus) => void;
    onarchive?: (project: ProjectStatus) => void;
    ondelete?: (project: ProjectStatus) => void;
  }
  
  let { 
    projects = [], 
    loading = false,
    onselect,
    onresume,
    oniterate,
    onarchive,
    ondelete,
  }: Props = $props();
  
  // Track which project's menu is open
  let openMenuId = $state<string | null>(null);
  
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
    onselect?.(project);
  }
  
  function handleResume(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    onresume?.(project);
  }
  
  function toggleMenu(event: Event, projectPath: string) {
    event.stopPropagation();
    openMenuId = openMenuId === projectPath ? null : projectPath;
  }
  
  function handleIterate(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    oniterate?.(project);
  }
  
  function handleArchive(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    onarchive?.(project);
  }
  
  function handleDelete(event: Event, project: ProjectStatus) {
    event.stopPropagation();
    openMenuId = null;
    ondelete?.(project);
  }
  
  function handleKeydown(e: KeyboardEvent, project: ProjectStatus) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleSelect(project);
    }
  }
  
  function handleResumeKeydown(e: KeyboardEvent, project: ProjectStatus) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleResume(e, project);
    }
  }
  
  function handleMenuKeydown(e: KeyboardEvent, projectPath: string) {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      toggleMenu(e, projectPath);
    }
  }
  
  // Close menu when clicking outside
  function handleWindowClick(event: MouseEvent) {
    const target = event.target as HTMLElement;
    if (!target.closest('.action-menu') && !target.closest('.menu-trigger')) {
      openMenuId = null;
    }
  }
</script>

<svelte:window onclick={handleWindowClick} />

<div class="projects-section">
  <div class="section-header">
    <h3 class="section-title">Projects</h3>
    <span class="section-path">~/Sunwell/projects/</span>
  </div>
  
  {#if loading}
    <div class="loading" role="status" aria-live="polite">Scanning projects...</div>
  {:else if projects.length === 0}
    <div class="empty">
      <p>No projects yet</p>
      <p class="hint">Enter a goal above to create your first project</p>
    </div>
  {:else}
    <div class="project-list" role="list">
      {#each projects as project (project.path)}
        {@const statusInfo = getStatusInfo(project.status)}
        <div 
          class="project-item"
          class:menu-open={openMenuId === project.path}
          role="listitem"
        >
          <button
            class="project-button"
            onclick={() => handleSelect(project)}
            onkeydown={(e) => handleKeydown(e, project)}
            aria-label="Open project {project.name}"
          >
            <div class="project-main">
              <span class="project-icon" aria-hidden="true">{statusInfo.icon}</span>
              <span class="project-name">{project.name}</span>
              {#if project.id}
                <span class="project-id" title="Project ID: {project.id}">#{project.id.slice(0, 8)}</span>
              {/if}
              {#if statusInfo.label}
                <span class="project-status {statusInfo.class}">{statusInfo.label}</span>
              {/if}
            </div>
            
            <div class="project-details">
              {#if project.last_goal}
                <span class="project-goal" title={project.last_goal}>
                  {project.last_goal.slice(0, 40)}{project.last_goal.length > 40 ? '...' : ''}
                </span>
              {:else}
                <span class="project-goal-empty">No goal set</span>
              {/if}
              
              {#if project.tasks_completed !== null && project.tasks_total !== null}
                <span class="project-progress">
                  {project.tasks_completed}/{project.tasks_total} tasks
                </span>
              {/if}
              
              <span class="project-time">{formatTime(project.last_activity)}</span>
            </div>
          </button>
          
          <!-- Action buttons -->
          <div class="project-actions">
            {#if project.status === 'interrupted'}
              <button 
                class="action-button resume-button"
                onclick={(e) => handleResume(e, project)}
                onkeydown={(e) => handleResumeKeydown(e, project)}
                aria-label="Resume project {project.name}"
              >
                Resume
              </button>
            {/if}
            
            <!-- More actions menu trigger -->
            <button
              class="action-button menu-trigger"
              onclick={(e) => toggleMenu(e, project.path)}
              onkeydown={(e) => handleMenuKeydown(e, project.path)}
              aria-label="More actions for {project.name}"
              aria-expanded={openMenuId === project.path}
              aria-haspopup="menu"
            >
              ···
            </button>
            
            <!-- Dropdown menu -->
            {#if openMenuId === project.path}
              <div class="action-menu" role="menu">
                <button 
                  class="menu-item iterate"
                  onclick={(e) => handleIterate(e, project)}
                  title="New version from learnings"
                  role="menuitem"
                >
                  <span class="menu-icon" aria-hidden="true">↻</span>
                  <span class="menu-label">Iterate</span>
                </button>
                
                <button 
                  class="menu-item archive"
                  onclick={(e) => handleArchive(e, project)}
                  title="Move to ~/Sunwell/archived/"
                  role="menuitem"
                >
                  <span class="menu-icon" aria-hidden="true">⌂</span>
                  <span class="menu-label">Archive</span>
                </button>
                
                <button 
                  class="menu-item delete"
                  onclick={(e) => handleDelete(e, project)}
                  title="Remove permanently"
                  role="menuitem"
                >
                  <span class="menu-icon" aria-hidden="true">✕</span>
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
    position: relative;
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
  }
  
  .project-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .project-item.menu-open {
    z-index: 50;
  }
  
  .project-button {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    width: 100%;
    padding: var(--space-3);
    background: transparent;
    border: none;
    color: var(--text-secondary);
    text-align: left;
    cursor: pointer;
    transition: color var(--transition-fast);
  }
  
  .project-item:hover .project-button {
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
    transition: color var(--transition-fast);
  }
  
  .project-item:hover .project-name {
    color: var(--text-gold);
  }
  
  .project-id {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    opacity: 0.6;
    margin-left: var(--space-1);
  }
  
  .project-status {
    font-size: var(--text-xs);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    margin-left: auto;
  }
  
  .status-interrupted {
    background: rgba(var(--warning-rgb), 0.15);
    color: var(--warning);
  }
  
  .status-complete {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .status-failed {
    background: rgba(var(--error-rgb), 0.15);
    color: var(--error);
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
  
  .project-goal-empty {
    flex: 1;
    color: var(--text-tertiary);
    font-style: italic;
    font-size: var(--text-xs);
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
  
  .project-item:hover .project-actions,
  .project-item:focus-within .project-actions {
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
  
  .action-button:hover,
  .action-button:focus {
    background: var(--bg-secondary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-button:focus {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  
  .resume-button {
    background: var(--gradient-ui-gold);
    color: var(--bg-primary);
    border-color: var(--border-emphasis);
  }
  
  .resume-button:hover,
  .resume-button:focus {
    background: linear-gradient(
      135deg,
      rgba(212, 176, 70, 0.95),
      rgba(201, 162, 39, 1)
    );
    box-shadow: var(--glow-gold-subtle);
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
  
  .menu-item:hover,
  .menu-item:focus {
    color: var(--text-primary);
  }
  
  .menu-item:focus {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  
  .menu-item .menu-icon {
    font-size: var(--text-sm);
  }
  
  .menu-item .menu-label {
    font-weight: 500;
  }
  
  .menu-item.iterate:hover,
  .menu-item.iterate:focus {
    background: rgba(var(--info-rgb), 0.1);
    color: var(--info);
  }
  
  .menu-item.archive:hover,
  .menu-item.archive:focus {
    background: rgba(var(--warning-rgb), 0.1);
    color: var(--warning);
  }
  
  .menu-item.delete:hover,
  .menu-item.delete:focus {
    background: rgba(var(--error-rgb), 0.1);
    color: var(--error);
  }
</style>
