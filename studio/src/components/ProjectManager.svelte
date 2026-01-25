<!--
  ProjectManager — Scalable project lifecycle control (RFC-096, RFC-140)
  
  Provides full project management with:
  - List view with filtering, sorting, search
  - Detail view with project info
  - Workspace discovery view (RFC-140)
  - Full CRUD: Open, Resume, Iterate, Archive, Delete
  - Bulk operations with multi-select
  - Keyboard navigation (j/k/Enter/Space)
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Modal from './Modal.svelte';
  import Button from './Button.svelte';
  import {
    ProjectList,
    ProjectDetail,
    ProjectFilters,
    ProjectBulkActions,
    ProjectStats,
  } from './project-manager';
  import { WorkspaceDiscovery } from './workspace';
  import {
    projectManager,
    loadProjects,
    backToList,
    clearSelection,
    archiveProject,
    deleteProject,
    archiveSelected,
    deleteSelected,
    openProjectAction,
    resumeProjectAction,
    iterateProjectAction,
    getFilteredProjects,
  } from '../stores/projectManager.svelte';
  import { workspaceManager, switchWorkspace } from '../stores/workspaceManager.svelte';
  import { goToProject, goToProjects } from '../stores/app.svelte';
  import type { ProjectStatus } from '$lib/types';

  let showWorkspaceDiscovery = $state(false);
  
  interface Props {
    mode?: 'inline' | 'modal' | 'page';
    onClose?: () => void;
    onOpenProject?: (path: string) => void;
  }
  
  let { mode = 'inline', onClose, onOpenProject }: Props = $props();
  
  // In inline mode, limit displayed projects
  const INLINE_LIMIT = 6;
  const filteredProjects = $derived(getFilteredProjects());
  const hasMore = $derived(mode === 'inline' && filteredProjects.length > INLINE_LIMIT);
  
  // Confirmation modal state
  let confirmModal = $state<{
    show: boolean;
    title: string;
    message: string;
    action: () => Promise<void>;
    destructive: boolean;
  }>({ show: false, title: '', message: '', action: async () => {}, destructive: false });
  
  // Accessibility: announce filter results
  let announceMessage = $state('');
  
  $effect(() => {
    const count = projectManager.projects.length;
    announceMessage = `${count} project${count !== 1 ? 's' : ''}`;
  });
  
  onMount(() => {
    if (projectManager.projects.length === 0) {
      loadProjects();
    }
  });
  
  // Project actions
  async function handleOpenProject(project: ProjectStatus) {
    const success = await openProjectAction(project.path);
    if (success) {
      onOpenProject?.(project.path);
      goToProject();
    }
  }
  
  async function handleResumeProject(project: ProjectStatus) {
    const success = await resumeProjectAction(project.path);
    if (success) {
      onOpenProject?.(project.path);
      goToProject();
    }
  }
  
  async function handleIterateProject(project: ProjectStatus) {
    const result = await iterateProjectAction(project.path);
    if (result.success && result.new_path) {
      onOpenProject?.(result.new_path);
      goToProject();
    }
  }
  
  function handleArchiveProject(project: ProjectStatus) {
    confirmModal = {
      show: true,
      title: 'Archive Project',
      message: `Archive "${project.name}"? This will move it to ~/Sunwell/archived/`,
      action: async () => {
        await archiveProject(project.path);
      },
      destructive: false,
    };
  }
  
  function handleDeleteProject(project: ProjectStatus) {
    confirmModal = {
      show: true,
      title: 'Delete Project',
      message: `Delete "${project.name}" permanently? This cannot be undone.`,
      action: async () => {
        await deleteProject(project.path);
      },
      destructive: true,
    };
  }
  
  // Bulk actions
  function handleBulkArchive() {
    const count = projectManager.selectedCount;
    confirmModal = {
      show: true,
      title: 'Archive Projects',
      message: `Archive ${count} project${count !== 1 ? 's' : ''}? This will move them to ~/Sunwell/archived/`,
      action: async () => {
        await archiveSelected();
      },
      destructive: false,
    };
  }
  
  function handleBulkDelete() {
    const count = projectManager.selectedCount;
    confirmModal = {
      show: true,
      title: 'Delete Projects',
      message: `Delete ${count} project${count !== 1 ? 's' : ''} permanently? This cannot be undone.`,
      action: async () => {
        await deleteSelected();
      },
      destructive: true,
    };
  }
  
  async function handleConfirm() {
    await confirmModal.action();
    confirmModal = { ...confirmModal, show: false };
  }
  
  function handleCancel() {
    confirmModal = { ...confirmModal, show: false };
  }
  
  // Detail view handlers (use path instead of ProjectStatus)
  function handleDetailOpen(path: string) {
    onOpenProject?.(path);
    goToProject();
  }
  
  async function handleDetailResume(path: string) {
    const success = await resumeProjectAction(path);
    if (success) {
      onOpenProject?.(path);
      goToProject();
    }
  }
  
  async function handleDetailIterate(path: string) {
    const result = await iterateProjectAction(path);
    if (result.success && result.new_path) {
      onOpenProject?.(result.new_path);
      goToProject();
    }
  }
  
  function handleDetailArchive(path: string) {
    const project = projectManager.projects.find(p => p.path === path);
    if (project) handleArchiveProject(project);
  }
  
  function handleDetailDelete(path: string) {
    const project = projectManager.projects.find(p => p.path === path);
    if (project) handleDeleteProject(project);
  }
</script>

<div 
  class="project-manager" 
  class:modal-mode={mode === 'modal'} 
  class:page-mode={mode === 'page'}
>
  <!-- Screen reader announcements -->
  <div class="sr-only" aria-live="polite" aria-atomic="true">{announceMessage}</div>
  
  <header class="manager-header">
    <div class="header-left">
      {#if projectManager.view === 'detail'}
        <Button variant="ghost" size="sm" onclick={backToList}>
          ← Back
        </Button>
      {/if}
      <h2 class="manager-title">
        {#if showWorkspaceDiscovery}
          Link External Codebase
        {:else if projectManager.view === 'detail'}
          {projectManager.selectedProject?.name}
        {:else}
          Projects
        {/if}
      </h2>
      {#if projectManager.view === 'list' && !showWorkspaceDiscovery}
        <ProjectStats />
      {/if}
    </div>
    
    <div class="header-right">
      {#if !showWorkspaceDiscovery}
        <Button variant="ghost" size="sm" onclick={() => (showWorkspaceDiscovery = true)}>
          Link Codebase
        </Button>
      {:else}
        <Button variant="ghost" size="sm" onclick={() => (showWorkspaceDiscovery = false)}>
          Back to Projects
        </Button>
      {/if}
      {#if mode === 'inline' && projectManager.projects.length > 0 && !showWorkspaceDiscovery}
        <Button variant="ghost" size="sm" onclick={goToProjects}>
          Manage All →
        </Button>
      {/if}
      {#if mode === 'modal' && onClose}
        <Button variant="ghost" size="sm" onclick={onClose}>✕</Button>
      {/if}
    </div>
  </header>
  
  {#if showWorkspaceDiscovery}
    <div class="manager-content">
      <WorkspaceDiscovery
        onSwitch={async (workspaceId) => {
          await switchWorkspace(workspaceId);
          showWorkspaceDiscovery = false;
        }}
        onRegister={(path) => {
          // Workspace registered, refresh projects
          loadProjects();
        }}
      />
    </div>
  {:else if projectManager.view === 'list'}
    <div class="manager-toolbar">
      <ProjectFilters />
      {#if projectManager.selectedCount > 0}
        <ProjectBulkActions 
          count={projectManager.selectedCount}
          onArchive={handleBulkArchive}
          onDelete={handleBulkDelete}
          onClear={clearSelection}
        />
      {/if}
    </div>
    
    <div class="manager-content">
      <ProjectList 
        limit={mode === 'inline' ? INLINE_LIMIT : undefined}
        onOpenProject={handleOpenProject}
        onResumeProject={handleResumeProject}
        onIterateProject={handleIterateProject}
        onArchiveProject={handleArchiveProject}
        onDeleteProject={handleDeleteProject}
      />
      {#if hasMore}
        <button class="view-all-link" onclick={goToProjects}>
          View all {filteredProjects.length} projects →
        </button>
      {/if}
    </div>
  {:else if projectManager.view === 'detail'}
    <div class="manager-content">
      <ProjectDetail 
        project={projectManager.selectedProject}
        onOpenProject={handleDetailOpen}
        onResumeProject={handleDetailResume}
        onIterateProject={handleDetailIterate}
        onArchiveProject={handleDetailArchive}
        onDeleteProject={handleDetailDelete}
      />
    </div>
  {/if}
</div>

<!-- Confirmation Modal -->
<Modal
  isOpen={confirmModal.show}
  onClose={handleCancel}
  title={confirmModal.title}
  description={confirmModal.message}
>
  <div class="modal-actions">
    <Button variant="ghost" onclick={handleCancel}>Cancel</Button>
    <Button 
      variant={confirmModal.destructive ? 'secondary' : 'primary'}
      onclick={handleConfirm}
    >
      {confirmModal.destructive ? 'Delete' : 'Archive'}
    </Button>
  </div>
</Modal>

<style>
  .project-manager {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    width: 100%;
    max-width: 700px;
  }
  
  .project-manager.modal-mode {
    max-width: 100%;
    height: 100%;
    max-height: 70vh;
  }
  
  .project-manager.page-mode {
    max-width: 900px;
    margin: 0 auto;
    padding: var(--space-6);
  }
  
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border: 0;
  }
  
  .manager-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-3);
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
  
  .manager-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .manager-toolbar {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  
  .manager-content {
    flex: 1;
    overflow-y: auto;
  }
  
  .view-all-link {
    display: block;
    width: 100%;
    padding: var(--space-3);
    margin-top: var(--space-2);
    background: transparent;
    border: 1px dashed var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: var(--text-sm);
    text-align: center;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .view-all-link:hover {
    background: var(--radiant-gold-5);
    border-color: var(--radiant-gold-30);
    color: var(--gold);
  }
  
  .view-all-link:focus {
    outline: 2px solid var(--gold);
    outline-offset: 2px;
  }
</style>
