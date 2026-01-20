<!--
  Home — Launch screen
  
  The minimal, beautiful entry point. Just a logo, input, and projects list.
  Shows all projects from ~/Sunwell/projects/ with status and resume capability.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Logo from '../components/Logo.svelte';
  import InputBar from '../components/InputBar.svelte';
  import RecentProjects from '../components/RecentProjects.svelte';
  import { goToProject } from '../stores/app';
  import { 
    discoveredProjects,
    isScanning,
    scanProjects, 
    createProject,
    openProject,
    resumeProject,
    deleteProject,
    archiveProject,
    iterateProject,
  } from '../stores/project';
  import { runGoal, agentState } from '../stores/agent';
  import type { ProjectStatus } from '$lib/types';
  
  let inputValue = '';
  let inputBar: InputBar;
  
  // Confirmation modal state
  let confirmModal: { 
    show: boolean; 
    title: string; 
    message: string; 
    action: 'delete' | 'archive'; 
    project: ProjectStatus | null;
    destructive: boolean;
  } = { show: false, title: '', message: '', action: 'delete', project: null, destructive: false };
  
  function showConfirm(action: 'delete' | 'archive', project: ProjectStatus) {
    if (action === 'delete') {
      confirmModal = {
        show: true,
        title: 'Delete Project',
        message: `Delete "${project.name}" permanently? This cannot be undone.`,
        action: 'delete',
        project,
        destructive: true,
      };
    } else {
      confirmModal = {
        show: true,
        title: 'Archive Project',
        message: `Archive "${project.name}"? This will move it to ~/Sunwell/archived/`,
        action: 'archive',
        project,
        destructive: false,
      };
    }
  }
  
  async function handleConfirm() {
    if (!confirmModal.project) return;
    
    const project = confirmModal.project;
    const action = confirmModal.action;
    confirmModal = { ...confirmModal, show: false };
    
    if (action === 'delete') {
      await deleteProject(project.path);
    } else {
      await archiveProject(project.path);
    }
  }
  
  function handleCancel() {
    confirmModal = { ...confirmModal, show: false };
  }
  
  onMount(() => {
    scanProjects();
    inputBar?.focus();
  });
  
  async function handleSubmit(event: CustomEvent<string>) {
    const goal = event.detail;
    if (!goal) return;
    
    // Create a new project from the goal
    createProject(goal);
    
    // Start the agent
    await runGoal(goal);
    
    // Navigate to project view
    goToProject();
  }
  
  async function handleSelectProject(event: CustomEvent<ProjectStatus>) {
    const project = event.detail;
    await openProject(project.path);
    goToProject();
  }
  
  async function handleResumeProject(event: CustomEvent<ProjectStatus>) {
    const project = event.detail;
    
    // Open the project first
    await openProject(project.path);
    
    // Navigate to project view
    goToProject();
    
    // Resume the agent
    await resumeProject(project.path);
  }
  
  async function handleIterateProject(event: CustomEvent<ProjectStatus>) {
    const project = event.detail;
    
    // Create a new iteration and start the agent
    const result = await iterateProject(project.path);
    
    if (result.success && result.new_path) {
      // Open the new project
      await openProject(result.new_path);
      goToProject();
    }
  }
  
  function handleArchiveProject(event: CustomEvent<ProjectStatus>) {
    showConfirm('archive', event.detail);
  }
  
  function handleDeleteProject(event: CustomEvent<ProjectStatus>) {
    showConfirm('delete', event.detail);
  }
</script>

<div class="home">
  <div class="hero">
    <Logo size="lg" />
    
    <div class="input-section">
      <InputBar
        bind:this={inputBar}
        bind:value={inputValue}
        placeholder="What would you like to create?"
        autofocus
        on:submit={handleSubmit}
      />
    </div>
    
    <RecentProjects 
      projects={$discoveredProjects}
      loading={$isScanning}
      on:select={handleSelectProject}
      on:resume={handleResumeProject}
      on:iterate={handleIterateProject}
      on:archive={handleArchiveProject}
      on:delete={handleDeleteProject}
    />
  </div>
  
  <footer class="version">
    v0.1.0
  </footer>
</div>

<!-- Confirmation Modal -->
{#if confirmModal.show}
  <div class="modal-backdrop" on:click={handleCancel} role="presentation">
    <div class="modal" on:click|stopPropagation role="dialog" aria-modal="true">
      <h3 class="modal-title">{confirmModal.title}</h3>
      <p class="modal-message">{confirmModal.message}</p>
      <div class="modal-actions">
        <button class="modal-btn cancel" on:click={handleCancel}>Cancel</button>
        <button 
          class="modal-btn confirm" 
          class:destructive={confirmModal.destructive}
          on:click={handleConfirm}
        >
          {confirmModal.action === 'delete' ? 'Delete' : 'Archive'}
        </button>
      </div>
    </div>
  </div>
{/if}

<style>
  .home {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-8);
  }
  
  .hero {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
    animation: fadeIn 0.3s ease;
  }
  
  .input-section {
    width: 100%;
    display: flex;
    justify-content: center;
    margin-top: var(--space-8);
  }
  
  .version {
    text-align: right;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  @keyframes fadeIn {
    from { 
      opacity: 0;
      transform: translateY(10px);
    }
    to { 
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* Confirmation Modal */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
    animation: fadeIn 0.15s ease;
  }
  
  .modal {
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    max-width: 400px;
    width: 90%;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    animation: modalSlide 0.15s ease;
  }
  
  @keyframes modalSlide {
    from {
      opacity: 0;
      transform: scale(0.95) translateY(-10px);
    }
    to {
      opacity: 1;
      transform: scale(1) translateY(0);
    }
  }
  
  .modal-title {
    margin: 0 0 var(--space-3);
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .modal-message {
    margin: 0 0 var(--space-6);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    line-height: 1.5;
  }
  
  .modal-actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
  }
  
  .modal-btn {
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
    font-weight: 500;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .modal-btn.cancel {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    color: var(--text-secondary);
  }
  
  .modal-btn.cancel:hover {
    background: var(--bg-primary);
    color: var(--text-primary);
  }
  
  .modal-btn.confirm {
    background: var(--accent-primary);
    border: 1px solid var(--accent-primary);
    color: var(--text-primary);
  }
  
  .modal-btn.confirm:hover {
    background: var(--accent-hover);
    border-color: var(--accent-hover);
  }
  
  .modal-btn.confirm.destructive {
    background: #c53030;
    border-color: #c53030;
  }
  
  .modal-btn.confirm.destructive:hover {
    background: #e53e3e;
    border-color: #e53e3e;
  }
</style>
