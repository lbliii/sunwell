<!--
  ProjectList — Project list with keyboard navigation (RFC-096)
-->
<script lang="ts">
  import { fly } from 'svelte/transition';
  import type { ProjectStatus } from '$lib/types';
  import ProjectCard from './ProjectCard.svelte';
  import {
    projectManager,
    getFilteredProjects,
    setFocusedIndex,
    focusUp,
    focusDown,
    toggleSelection,
    selectAll,
    clearSelection,
  } from '../../stores/projectManager.svelte';
  import { staggerDelay } from '$lib/tetris';
  
  interface Props {
    limit?: number;
    onOpenProject?: (project: ProjectStatus) => void;
    onResumeProject?: (project: ProjectStatus) => void;
    onIterateProject?: (project: ProjectStatus) => void;
    onArchiveProject?: (project: ProjectStatus) => void;
    onDeleteProject?: (project: ProjectStatus) => void;
  }
  
  let { 
    limit,
    onOpenProject, 
    onResumeProject,
    onIterateProject,
    onArchiveProject,
    onDeleteProject,
  }: Props = $props();
  
  const allFilteredProjects = $derived(getFilteredProjects());
  const filteredProjects = $derived(
    limit ? allFilteredProjects.slice(0, limit) : allFilteredProjects
  );
  
  function handleKeydown(e: KeyboardEvent) {
    // Use all filtered projects for navigation, not limited
    const projects = allFilteredProjects;
    if (projects.length === 0) return;
    
    switch (e.key) {
      case 'j':
      case 'ArrowDown':
        e.preventDefault();
        focusDown();
        break;
        
      case 'k':
      case 'ArrowUp':
        e.preventDefault();
        focusUp();
        break;
        
      case 'Enter':
        e.preventDefault();
        if (projects[projectManager.focusedIndex]) {
          onOpenProject?.(projects[projectManager.focusedIndex]);
        }
        break;
        
      case ' ':
        e.preventDefault();
        if (projects[projectManager.focusedIndex]) {
          toggleSelection(projects[projectManager.focusedIndex].path);
        }
        break;
        
      case 'a':
        if (e.ctrlKey || e.metaKey) {
          e.preventDefault();
          selectAll();
        }
        break;
        
      case 'Escape':
        e.preventDefault();
        clearSelection();
        break;
    }
  }
  
  function handleFocus() {
    // Ensure we have a valid focused index
    if (projectManager.focusedIndex >= filteredProjects.length) {
      setFocusedIndex(Math.max(0, filteredProjects.length - 1));
    }
  }
</script>

<!-- svelte-ignore a11y_no_noninteractive_tabindex -->
<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div 
  class="project-list"
  role="listbox"
  tabindex="0"
  onkeydown={handleKeydown}
  onfocus={handleFocus}
  aria-label="Projects list"
  aria-activedescendant={filteredProjects[projectManager.focusedIndex]?.path ?? undefined}
>
  {#if filteredProjects.length === 0}
    <div class="empty-state">
      {#if projectManager.search || projectManager.filter !== 'all'}
        <p>No projects match your filters</p>
        <p class="hint">Try adjusting your search or filter</p>
      {:else}
        <p>No projects yet</p>
        <p class="hint">Enter a goal above to create your first project</p>
      {/if}
    </div>
  {:else}
    {#each filteredProjects as project, i (project.path)}
      <div
        in:fly={{ y: 15, delay: staggerDelay(i), duration: 200 }}
        id={project.path}
        role="option"
        aria-selected={i === projectManager.focusedIndex}
      >
        <ProjectCard
          {project}
          focused={i === projectManager.focusedIndex}
          onOpen={onOpenProject}
          onResume={onResumeProject}
          onIterate={onIterateProject}
          onArchive={onArchiveProject}
          onDelete={onDeleteProject}
        />
      </div>
    {/each}
  {/if}
</div>

<style>
  .project-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2, 8px);
    outline: none;
  }
  
  .project-list:focus-visible {
    outline: 2px solid var(--gold, #ffd700);
    outline-offset: 4px;
    border-radius: var(--radius-md, 8px);
  }
  
  .empty-state {
    text-align: center;
    padding: var(--space-8, 32px) var(--space-4, 16px);
    color: var(--text-tertiary, #666);
  }
  
  .empty-state p {
    margin: 0;
  }
  
  .empty-state .hint {
    margin-top: var(--space-2, 8px);
    font-size: var(--text-xs, 12px);
  }
</style>
