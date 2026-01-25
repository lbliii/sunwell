<!--
  ProjectGate — Validates project context before showing app (RFC-132)
  
  Gates the main app behind project validation. If no valid project is
  available, shows a project picker/creator modal.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { apiGet, apiPost, apiPut } from '$lib/socket';
  import { project, openProject } from '../stores/project.svelte';
  import Button from './Button.svelte';
  import Modal from './Modal.svelte';
  import Spinner from './ui/Spinner.svelte';
  
  interface Props {
    children: Snippet;
  }
  
  let { children }: Props = $props();
  
  // Gate state
  let isValidating = $state(true);
  let needsProject = $state(false);
  let validationError = $state<string | null>(null);
  let suggestion = $state<string | null>(null);
  
  // Project list for picker
  interface ProjectItem {
    id: string;
    name: string;
    root: string;
    valid: boolean;
    isDefault: boolean;
    lastUsed: string | null;
  }
  let projects = $state<ProjectItem[]>([]);
  let isLoadingProjects = $state(false);
  
  // Creation state
  let showCreator = $state(false);
  let newProjectName = $state('');
  let isCreating = $state(false);
  let createError = $state<string | null>(null);
  
  // Modal state (always open when needsProject is true)
  function handleModalClose() {
    // Don't allow closing without selecting a project
    // This is intentional - user must select or create a project
  }
  
  onMount(async () => {
    await validateCurrentProject();
  });
  
  async function validateCurrentProject() {
    isValidating = true;
    validationError = null;
    suggestion = null;
    
    try {
      // Check for default project first
      const defaultResp = await apiGet<{project: {id: string; name: string; root: string} | null; warning?: string}>('/api/project/default');
      
      if (defaultResp.project) {
        // Validate it's still valid
        const validation = await apiPost<{valid: boolean; errorCode?: string; suggestion?: string}>(
          '/api/project/validate',
          { path: defaultResp.project.root }
        );
        
        if (validation.valid) {
          await openProject(defaultResp.project.root);
          needsProject = false;
          return;
        }
      }
      
      // Check current project (from URL or prior session)
      if (project.current?.path) {
        const validation = await apiPost<{valid: boolean; errorCode?: string; errorMessage?: string; suggestion?: string}>(
          '/api/project/validate',
          { path: project.current.path }
        );
        
        if (validation.valid) {
          needsProject = false;
          return;
        }
        
        // Current project invalid
        validationError = validation.errorCode ?? null;
        suggestion = validation.suggestion ?? null;
      }
      
      // Need to select or create a project
      needsProject = true;
      await loadProjects();
      
    } finally {
      isValidating = false;
    }
  }
  
  async function loadProjects() {
    isLoadingProjects = true;
    try {
      const resp = await apiGet<{projects: ProjectItem[]}>('/api/project/list');
      projects = resp.projects ?? [];
    } finally {
      isLoadingProjects = false;
    }
  }
  
  async function selectProject(proj: ProjectItem) {
    await openProject(proj.root);
    needsProject = false;
  }
  
  async function makeDefault(proj: ProjectItem, e: MouseEvent) {
    e.stopPropagation();
    await apiPut('/api/project/default', { project_id: proj.id });
    await loadProjects();
  }
  
  function getSlug(name: string): string {
    return name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || '...';
  }
  
  async function createProject() {
    if (!newProjectName.trim()) return;
    
    isCreating = true;
    createError = null;
    
    try {
      const resp = await apiPost<{project: {id: string; name: string; root: string}; path: string; error?: string; message?: string}>(
        '/api/project/create',
        { name: newProjectName }
      );
      
      if (resp.error) {
        createError = resp.message ?? 'Failed to create project';
        return;
      }
      
      await openProject(resp.path);
      showCreator = false;
      needsProject = false;
    } finally {
      isCreating = false;
    }
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && newProjectName.trim() && !isCreating) {
      createProject();
    }
  }
</script>

{#if isValidating}
  <div class="gate-loading">
    <Spinner style="moon" speed={100} />
    <p>Checking project...</p>
  </div>
{:else if needsProject}
  <Modal 
    isOpen={true} 
    title="Select Project" 
    onClose={handleModalClose}
  >
    {#if validationError === 'sunwell_repo'}
      <div class="error-banner">
        <p>Cannot use Sunwell's source repository as workspace.</p>
        {#if suggestion}
          <p class="suggestion">Suggested location: <code>{suggestion}</code></p>
        {/if}
      </div>
    {/if}
    
    {#if isLoadingProjects}
      <div class="loading-projects">
        <Spinner style="dots" speed={80} />
        <span>Loading projects...</span>
      </div>
    {:else if projects.length > 0}
      <div class="section">
        <h3 class="section-title">Your Projects</h3>
        <ul class="project-list">
          {#each projects as proj (proj.id)}
            <li>
              <button 
                class="project-item"
                class:invalid={!proj.valid}
                onclick={() => selectProject(proj)}
                disabled={!proj.valid}
              >
                <div class="project-info">
                  <strong class="project-name">
                    {proj.name}
                    {#if proj.isDefault}
                      <span class="default-badge">default</span>
                    {/if}
                  </strong>
                  <span class="project-path">{proj.root}</span>
                  {#if !proj.valid}
                    <span class="invalid-badge">Invalid</span>
                  {/if}
                </div>
                {#if proj.valid && !proj.isDefault}
                  <button 
                    class="make-default-btn"
                    onclick={(e) => makeDefault(proj, e)}
                    title="Set as default"
                  >
                    ★
                  </button>
                {/if}
              </button>
            </li>
          {/each}
        </ul>
      </div>
      <hr class="divider" />
    {/if}
    
    {#if showCreator}
      <div class="creator">
        <h3 class="section-title">Create New Project</h3>
        <input 
          type="text" 
          class="name-input"
          placeholder="Project name" 
          bind:value={newProjectName}
          onkeydown={handleKeydown}
          autofocus
        />
        <p class="path-preview">
          Will create: ~/Sunwell/projects/{getSlug(newProjectName)}
        </p>
        {#if createError}
          <p class="create-error">{createError}</p>
        {/if}
        <div class="actions">
          <Button variant="ghost" onclick={() => { showCreator = false; createError = null; }}>
            Cancel
          </Button>
          <Button 
            onclick={createProject} 
            disabled={isCreating || !newProjectName.trim()}
            loading={isCreating}
          >
            Create Project
          </Button>
        </div>
      </div>
    {:else}
      <Button variant="secondary" onclick={() => showCreator = true}>
        + Create New Project
      </Button>
    {/if}
  </Modal>
{:else}
  {@render children()}
{/if}

<style>
  .gate-loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: var(--space-4);
    color: var(--text-secondary);
  }
  
  .gate-loading p {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .error-banner {
    background: rgba(var(--error-rgb), 0.1);
    border: 1px solid var(--status-error);
    padding: var(--space-4);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }
  
  .error-banner p {
    margin: 0;
    color: var(--text-primary);
  }
  
  .suggestion {
    font-size: var(--text-sm);
    margin-top: var(--space-2) !important;
    color: var(--text-secondary);
  }
  
  .suggestion code {
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  
  .loading-projects {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-4);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .section {
    margin-bottom: var(--space-4);
  }
  
  .section-title {
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin: 0 0 var(--space-3) 0;
  }
  
  .project-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  
  .project-item {
    width: 100%;
    text-align: left;
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-2);
    cursor: pointer;
    transition: all var(--transition-fast);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  
  .project-item:hover:not(:disabled) {
    background: var(--bg-tertiary);
    border-color: var(--border-emphasis);
  }
  
  .project-item:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .project-item.invalid {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .project-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .project-name {
    color: var(--text-primary);
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .default-badge {
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-gold);
    background: rgba(var(--gold-rgb), 0.15);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
  }
  
  .invalid-badge {
    font-size: var(--text-xs);
    color: var(--status-error);
  }
  
  .project-path {
    display: block;
    font-size: var(--text-xs);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
  }
  
  .make-default-btn {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    cursor: pointer;
    padding: var(--space-2);
    border-radius: var(--radius-sm);
    transition: all var(--transition-fast);
  }
  
  .make-default-btn:hover {
    color: var(--text-gold);
    background: rgba(var(--gold-rgb), 0.1);
  }
  
  .divider {
    border: none;
    border-top: 1px solid var(--border-default);
    margin: var(--space-4) 0;
  }
  
  .creator {
    padding: var(--space-2) 0;
  }
  
  .name-input {
    width: 100%;
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    margin-bottom: var(--space-2);
    transition: border-color var(--transition-fast);
  }
  
  .name-input:focus {
    outline: none;
    border-color: var(--border-emphasis);
  }
  
  .name-input::placeholder {
    color: var(--text-tertiary);
  }
  
  .path-preview {
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
    margin: 0 0 var(--space-4) 0;
  }
  
  .create-error {
    font-size: var(--text-sm);
    color: var(--status-error);
    margin: 0 0 var(--space-3) 0;
  }
  
  .actions {
    display: flex;
    gap: var(--space-3);
    justify-content: flex-end;
  }
</style>
