<!--
  ProjectGate — Validates project context before showing app (RFC-132, RFC-133 Phase 2)
  
  Gates the main app behind project validation. If no valid project is
  available, shows a project picker/creator modal.
  
  RFC-133 Phase 2: URL-first project resolution
  - Checks URL for project slug (#/p/{slug}/...)
  - Resolves slug via API
  - Falls back to default project if no URL context
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { onMount } from 'svelte';
  import { apiGet, apiPost, apiPut } from '$lib/socket';
  import { project, openProject } from '../stores/project.svelte';
  import { app, setProjectSlug } from '../stores/app.svelte';
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
  
  // RFC-133: Slug resolution error state
  let slugNotFound = $state<string | null>(null);
  
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
    slugNotFound = null;
    
    try {
      // RFC-133 Phase 2: Check URL for project slug first
      const urlSlug = app.projectSlug;
      
      if (urlSlug) {
        // Try to resolve slug from URL
        const resolved = await apiPost<{
          project: ProjectItem | null;
          ambiguous: ProjectItem[] | null;
          error: string | null;
        }>('/api/project/resolve', { slug: urlSlug });
        
        if (resolved.project) {
          // Found project - open it and sync slug
          if (resolved.project.valid) {
            await openProjectWithSlug(resolved.project.root, urlSlug);
            needsProject = false;
            return;
          } else {
            // Project exists in registry but is invalid (e.g., unmounted drive)
            validationError = 'project_invalid';
            slugNotFound = urlSlug;
          }
        } else if (resolved.error === 'not_found') {
          // Slug not found - show error and fall through to picker
          slugNotFound = urlSlug;
        }
        // If ambiguous (shouldn't happen with proper registry), fall through to picker
      }
      
      // Check for default project
      const defaultResp = await apiGet<{project: {id: string; name: string; root: string} | null; warning?: string}>('/api/project/default');
      
      if (defaultResp.project) {
        // Validate it's still valid
        const validation = await apiPost<{valid: boolean; errorCode?: string; suggestion?: string}>(
          '/api/project/validate',
          { path: defaultResp.project.root }
        );
        
        if (validation.valid) {
          // Open default project and update URL with its slug
          await openProjectAndSyncSlug(defaultResp.project.root);
          needsProject = false;
          return;
        }
      }
      
      // Check current project (from prior session, not URL)
      if (project.current?.path) {
        const validation = await apiPost<{valid: boolean; errorCode?: string; errorMessage?: string; suggestion?: string}>(
          '/api/project/validate',
          { path: project.current.path }
        );
        
        if (validation.valid) {
          // Sync URL with current project's slug
          await syncProjectSlug(project.current.path);
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
  
  /**
   * Open project and set the slug in app state.
   */
  async function openProjectWithSlug(path: string, slug: string): Promise<void> {
    await openProject(path);
    setProjectSlug(slug);
  }
  
  /**
   * Open project and fetch/sync its slug from the backend.
   */
  async function openProjectAndSyncSlug(path: string): Promise<void> {
    await openProject(path);
    await syncProjectSlug(path);
  }
  
  /**
   * Fetch project slug from backend and update URL.
   */
  async function syncProjectSlug(path: string): Promise<void> {
    try {
      const resp = await apiPost<{slug: string | null; projectId: string | null; error: string | null}>(
        '/api/project/slug',
        { path }
      );
      if (resp.slug) {
        setProjectSlug(resp.slug);
      }
    } catch (e) {
      // Non-critical - URL won't have slug but app still works
      console.warn('Failed to sync project slug:', e);
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
    // RFC-133: Open project and sync slug to URL
    await openProjectAndSyncSlug(proj.root);
    slugNotFound = null;
    needsProject = false;
  }
  
  async function makeDefault(proj: ProjectItem, e: MouseEvent | KeyboardEvent) {
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
      
      // RFC-133: Open project and sync slug to URL
      await openProjectAndSyncSlug(resp.path);
      showCreator = false;
      slugNotFound = null;
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
    {#if slugNotFound}
      <div class="error-banner slug-error">
        <p><strong>Project not found:</strong> <code>{slugNotFound}</code></p>
        <p class="suggestion">The project "{slugNotFound}" doesn't exist or has been removed. Please select a different project.</p>
      </div>
    {/if}
    
    {#if validationError === 'sunwell_repo'}
      <div class="error-banner">
        <p>Cannot use Sunwell's source repository as workspace.</p>
        {#if suggestion}
          <p class="suggestion">Suggested location: <code>{suggestion}</code></p>
        {/if}
      </div>
    {:else if validationError === 'project_invalid'}
      <div class="error-banner">
        <p>The project workspace is no longer accessible (drive unmounted or folder deleted).</p>
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
                  <span 
                    class="make-default-btn"
                    role="button"
                    tabindex="0"
                    onclick={(e) => makeDefault(proj, e)}
                    onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') makeDefault(proj, e); }}
                    title="Set as default"
                  >
                    ★
                  </span>
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
  
  .error-banner.slug-error {
    background: rgba(var(--warning-rgb, 255, 193, 7), 0.1);
    border-color: var(--status-warning, #ffc107);
  }
  
  .error-banner code {
    background: var(--bg-tertiary);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
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
