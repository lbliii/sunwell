<!--
  ProjectCard — Individual project card with actions (RFC-096)
-->
<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  import { isSelected, toggleSelection } from '../../stores/projectManager.svelte';
  
  interface Props {
    project: ProjectStatus;
    focused?: boolean;
    onOpen?: (project: ProjectStatus) => void;
    onResume?: (project: ProjectStatus) => void;
    onIterate?: (project: ProjectStatus) => void;
    onArchive?: (project: ProjectStatus) => void;
    onDelete?: (project: ProjectStatus) => void;
  }
  
  let { 
    project, 
    focused = false,
    onOpen, 
    onResume,
    onIterate,
    onArchive,
    onDelete,
  }: Props = $props();
  
  let showMenu = $state(false);
  
  const selected = $derived(isSelected(project.path));
  
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
  
  function handleCheckboxClick(e: Event) {
    e.stopPropagation();
    toggleSelection(project.path);
  }
  
  function handleCardClick() {
    if (showMenu) {
      showMenu = false;
      return;
    }
    onOpen?.(project);
  }
  
  function handleMenuToggle(e: Event) {
    e.stopPropagation();
    showMenu = !showMenu;
  }
  
  function handleAction(e: Event, action: () => void) {
    e.stopPropagation();
    showMenu = false;
    action();
  }
  
  // Close menu when clicking outside
  function handleWindowClick() {
    showMenu = false;
  }
  
  const statusInfo = $derived(getStatusInfo(project.status));
</script>

<svelte:window onclick={handleWindowClick} />

<div 
  class="project-card"
  class:focused
  class:selected
  class:menu-open={showMenu}
  role="listitem"
>
  <!-- Checkbox for bulk selection -->
  <button 
    class="checkbox"
    class:checked={selected}
    onclick={handleCheckboxClick}
    aria-label={selected ? 'Deselect project' : 'Select project'}
    aria-pressed={selected}
  >
    {selected ? '☑' : '☐'}
  </button>
  
  <!-- Main clickable area -->
  <button
    class="card-main"
    onclick={handleCardClick}
    aria-label="Open project {project.name}"
  >
    <span class="status-icon {statusInfo.class}" aria-hidden="true">
      {statusInfo.icon}
    </span>
    
    <div class="project-info">
      <span class="project-name">{project.name}</span>
      {#if project.last_goal}
        <span class="project-goal">
          {project.last_goal.slice(0, 50)}{project.last_goal.length > 50 ? '...' : ''}
        </span>
      {/if}
    </div>
    
    <div class="project-meta">
      {#if statusInfo.label}
        <span class="status-label {statusInfo.class}">{statusInfo.label}</span>
      {/if}
      {#if project.tasks_completed != null && project.tasks_total != null}
        <span class="progress">{project.tasks_completed}/{project.tasks_total}</span>
      {/if}
      <span class="time">{formatTime(project.last_activity)}</span>
    </div>
  </button>
  
  <!-- Action buttons -->
  <div class="card-actions">
    {#if project.status === 'interrupted'}
      <button 
        class="action-btn resume"
        onclick={(e) => handleAction(e, () => onResume?.(project))}
        aria-label="Resume project"
      >
        Resume
      </button>
    {/if}
    
    <button
      class="action-btn menu-trigger"
      onclick={handleMenuToggle}
      aria-label="More actions"
      aria-expanded={showMenu}
      aria-haspopup="menu"
    >
      ···
    </button>
    
    {#if showMenu}
      <div class="action-menu" role="menu">
        <button 
          class="menu-item"
          onclick={(e) => handleAction(e, () => onIterate?.(project))}
          role="menuitem"
        >
          <span class="menu-icon">↻</span>
          <span>Iterate</span>
        </button>
        <button 
          class="menu-item"
          onclick={(e) => handleAction(e, () => onArchive?.(project))}
          role="menuitem"
        >
          <span class="menu-icon">⌂</span>
          <span>Archive</span>
        </button>
        <button 
          class="menu-item delete"
          onclick={(e) => handleAction(e, () => onDelete?.(project))}
          role="menuitem"
        >
          <span class="menu-icon">✕</span>
          <span>Delete</span>
        </button>
      </div>
    {/if}
  </div>
</div>

<style>
  .project-card {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    transition: all 0.15s ease;
  }
  
  .project-card:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-default);
  }
  
  .project-card.focused {
    border-color: var(--gold);
    box-shadow: 0 0 0 1px var(--gold);
  }
  
  .project-card.selected {
    background: var(--radiant-gold-5);
    border-color: var(--radiant-gold-30);
  }
  
  .project-card.menu-open {
    z-index: 10;
  }
  
  .checkbox {
    flex-shrink: 0;
    width: 32px;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-base);
    cursor: pointer;
    transition: color 0.15s ease;
    padding-left: var(--space-2);
  }
  
  .checkbox:hover,
  .checkbox.checked {
    color: var(--gold);
  }
  
  .checkbox:focus {
    outline: none;
  }
  
  .card-main {
    flex: 1;
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-3) 0;
    background: transparent;
    border: none;
    color: inherit;
    text-align: left;
    cursor: pointer;
    min-width: 0;
  }
  
  .status-icon {
    width: 24px;
    text-align: center;
    font-size: var(--text-sm);
    flex-shrink: 0;
  }
  
  .status-icon.status-interrupted { color: var(--warning); }
  .status-icon.status-complete { color: var(--success); }
  .status-icon.status-failed { color: var(--error); }
  .status-icon.status-active { color: var(--text-tertiary); }
  
  .project-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }
  
  .project-name {
    color: var(--text-primary);
    font-weight: 500;
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    transition: color 0.15s ease;
  }
  
  .project-card:hover .project-name {
    color: var(--gold);
  }
  
  .project-goal {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .project-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-shrink: 0;
    padding-right: var(--space-2);
  }
  
  .status-label {
    font-size: var(--text-xs);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
  }
  
  .status-label.status-interrupted {
    background: rgba(245, 158, 11, 0.15);
    color: var(--warning);
  }
  
  .status-label.status-complete {
    background: rgba(34, 197, 94, 0.15);
    color: var(--success);
  }
  
  .status-label.status-failed {
    background: rgba(239, 68, 68, 0.15);
    color: var(--error);
  }
  
  .progress {
    color: var(--text-secondary);
    font-size: var(--text-xs);
  }
  
  .time {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    min-width: 50px;
    text-align: right;
  }
  
  .card-actions {
    position: relative;
    display: flex;
    align-items: center;
    gap: var(--space-1);
    padding-right: var(--space-2);
    opacity: 0;
    transition: opacity 0.15s ease;
  }
  
  .project-card:hover .card-actions,
  .project-card:focus-within .card-actions,
  .project-card.menu-open .card-actions {
    opacity: 1;
  }
  
  .action-btn {
    padding: var(--space-1) var(--space-2);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .action-btn:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
  }
  
  .action-btn:focus {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
  
  .action-btn.resume {
    background: var(--gradient-ui-gold, linear-gradient(135deg, #d4b046, #c9a227));
    color: var(--bg-primary);
    border-color: var(--border-emphasis);
  }
  
  .action-btn.resume:hover {
    box-shadow: 0 0 12px var(--radiant-gold-30);
  }
  
  .action-btn.menu-trigger {
    min-width: 28px;
    text-align: center;
    letter-spacing: 1px;
  }
  
  .action-menu {
    position: absolute;
    top: calc(100% + var(--space-1));
    right: 0;
    display: flex;
    flex-direction: column;
    gap: 1px;
    background: var(--border-subtle);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    overflow: hidden;
    animation: menuSlide 0.12s ease;
    z-index: 100;
  }
  
  @keyframes menuSlide {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  .menu-item {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: none;
    color: var(--text-secondary);
    font-size: var(--text-xs);
    cursor: pointer;
    transition: all 0.15s ease;
    white-space: nowrap;
  }
  
  .menu-item:hover {
    background: var(--bg-secondary);
    color: var(--text-primary);
  }
  
  .menu-item:focus {
    outline: 2px solid var(--gold);
    outline-offset: -2px;
  }
  
  .menu-item.delete:hover {
    background: rgba(239, 68, 68, 0.1);
    color: var(--error);
  }
  
  .menu-icon {
    width: 16px;
    text-align: center;
  }
</style>
