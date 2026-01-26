<!--
  WorkspaceDiscovery — Full-page discovery interface (RFC-140)
  
  Shows discovered vs registered workspaces.
  Bulk registration actions.
  Filter by type, location, status.
  Create workspace containers for multi-project grouping.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '../Button.svelte';
  import Input from '../form/Input.svelte';
  import Select from '../form/Select.svelte';
  import Checkbox from '../form/Checkbox.svelte';
  import WorkspaceList from './WorkspaceList.svelte';
  import {
    workspaceManager,
    loadWorkspaces,
    loadContainers,
    discoverWorkspaces,
    switchWorkspace,
    createContainer,
  } from '../../stores/workspaceManager.svelte';
  import type { WorkspaceInfo } from '../../stores/workspaceManager.svelte';

  interface Props {
    onSwitch?: (workspaceId: string) => void;
    onRegister?: (path: string) => void;
  }

  let { onSwitch, onRegister }: Props = $props();

  let searchQuery = $state('');
  let filterType = $state<string>('all');
  let filterStatus = $state<string>('all');
  let isDiscovering = $state(false);
  let discoveryRoot = $state('');

  // Container creation state
  let showCreateContainer = $state(false);
  let newContainerName = $state('');
  let selectedProjects = $state<Map<string, { selected: boolean; role: string; isPrimary: boolean }>>(new Map());
  let isCreatingContainer = $state(false);
  let createError = $state<string | null>(null);

  const roleOptions = [
    { value: 'unknown', label: 'Unknown' },
    { value: 'frontend', label: 'Frontend' },
    { value: 'backend', label: 'Backend' },
    { value: 'api', label: 'API' },
    { value: 'shared', label: 'Shared/Library' },
    { value: 'infra', label: 'Infrastructure' },
    { value: 'docs', label: 'Documentation' },
    { value: 'mobile', label: 'Mobile' },
    { value: 'cli', label: 'CLI' },
  ];

  // Initialize selection map when workspaces change
  $effect(() => {
    const map = new Map<string, { selected: boolean; role: string; isPrimary: boolean }>();
    for (const ws of workspaceManager.workspaces) {
      const existing = selectedProjects.get(ws.id);
      map.set(ws.id, existing || { selected: false, role: 'unknown', isPrimary: false });
    }
    selectedProjects = map;
  });

  function toggleProjectSelection(workspaceId: string) {
    const current = selectedProjects.get(workspaceId);
    if (current) {
      selectedProjects.set(workspaceId, { ...current, selected: !current.selected });
      selectedProjects = new Map(selectedProjects);
    }
  }

  function setProjectRole(workspaceId: string, role: string) {
    const current = selectedProjects.get(workspaceId);
    if (current) {
      selectedProjects.set(workspaceId, { ...current, role });
      selectedProjects = new Map(selectedProjects);
    }
  }

  function setPrimaryProject(workspaceId: string) {
    // Unset all others
    for (const [id, val] of selectedProjects) {
      selectedProjects.set(id, { ...val, isPrimary: id === workspaceId });
    }
    selectedProjects = new Map(selectedProjects);
  }

  const selectedCount = $derived(
    Array.from(selectedProjects.values()).filter(v => v.selected).length
  );

  async function handleCreateContainer() {
    if (!newContainerName.trim() || selectedCount === 0) return;

    isCreatingContainer = true;
    createError = null;

    try {
      const projects = Array.from(selectedProjects.entries())
        .filter(([, val]) => val.selected)
        .map(([id]) => {
          const ws = workspaceManager.workspaces.find(w => w.id === id);
          const val = selectedProjects.get(id)!;
          return {
            id,
            path: ws?.path || '',
            role: val.role,
            isPrimary: val.isPrimary,
          };
        });

      // Ensure at least one primary
      if (!projects.some(p => p.isPrimary) && projects.length > 0) {
        projects[0].isPrimary = true;
      }

      const containerId = newContainerName.toLowerCase().replace(/\s+/g, '-').replace(/[^a-z0-9-]/g, '');

      await createContainer(containerId, newContainerName, projects);

      // Reset form
      newContainerName = '';
      for (const [id] of selectedProjects) {
        selectedProjects.set(id, { selected: false, role: 'unknown', isPrimary: false });
      }
      selectedProjects = new Map(selectedProjects);
      showCreateContainer = false;

      // Reload containers
      await loadContainers();
    } catch (e) {
      createError = e instanceof Error ? e.message : String(e);
      console.error('Failed to create container:', e);
    } finally {
      isCreatingContainer = false;
    }
  }

  const filteredWorkspaces = $derived.by(() => {
    let filtered = workspaceManager.workspaces;

    // Search filter
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      filtered = filtered.filter(
        (w) =>
          w.name.toLowerCase().includes(query) ||
          w.id.toLowerCase().includes(query) ||
          w.path.toLowerCase().includes(query)
      );
    }

    // Type filter
    if (filterType !== 'all') {
      filtered = filtered.filter((w) => {
        if (filterType === 'registered') return w.isRegistered;
        if (filterType === 'discovered') return !w.isRegistered;
        return true;
      });
    }

    // Status filter
    if (filterStatus !== 'all') {
      filtered = filtered.filter((w) => w.status === filterStatus);
    }

    return filtered;
  });

  async function handleDiscover() {
    try {
      isDiscovering = true;
      await discoverWorkspaces(discoveryRoot || undefined);
    } catch (e) {
      console.error('Discovery failed:', e);
    } finally {
      isDiscovering = false;
    }
  }

  async function handleRegister(path: string) {
    try {
      // Use workspaceManager to register via API
      // For now, just reload workspaces - registration can be done via project init
      await loadWorkspaces();
      onRegister?.(path);
    } catch (e) {
      console.error('Registration failed:', e);
    }
  }

  onMount(() => {
    loadWorkspaces();
  });
</script>

<div class="workspace-discovery">
  <header class="discovery-header">
    <h1 class="discovery-title">Link External Codebases</h1>
    <p class="discovery-description">
      Find existing code repositories on your system to link with Sunwell projects.
      Your Sunwell projects are shown below.
    </p>
  </header>

  <div class="discovery-controls">
    <div class="controls-row">
      <Input
        type="search"
        placeholder="Search projects and codebases..."
        bind:value={searchQuery}
        size="md"
      />

      <Select
        value={filterType}
        onchange={(v) => (filterType = v)}
        options={[
          { value: 'all', label: 'All Types' },
          { value: 'registered', label: 'Registered' },
          { value: 'discovered', label: 'Discovered' },
        ]}
      />

      <Select
        value={filterStatus}
        onchange={(v) => (filterStatus = v)}
        options={[
          { value: 'all', label: 'All Status' },
          { value: 'valid', label: 'Valid' },
          { value: 'invalid', label: 'Invalid' },
          { value: 'not_found', label: 'Not Found' },
        ]}
      />
    </div>

    <div class="controls-row">
      <Input
        type="text"
        placeholder="Directory to scan, e.g. ~/Code (optional)"
        bind:value={discoveryRoot}
        size="md"
      />
      <Button variant="primary" onclick={handleDiscover} loading={isDiscovering}>
        {isDiscovering ? 'Scanning...' : 'Scan for Codebases'}
      </Button>
      <Button variant="ghost" onclick={loadWorkspaces} disabled={workspaceManager.isLoading}>
        Refresh
      </Button>
    </div>
  </div>

  {#if workspaceManager.error}
    <div class="discovery-error" role="alert">
      {workspaceManager.error}
    </div>
  {/if}

  <!-- Container Creation Section -->
  <div class="create-container-section">
    <button 
      class="create-container-toggle"
      onclick={() => showCreateContainer = !showCreateContainer}
      type="button"
    >
      <span class="toggle-icon">{showCreateContainer ? '−' : '+'}</span>
      Create Workspace Container
    </button>

    {#if showCreateContainer}
      <div class="create-container-form">
        <p class="form-description">
          Group related projects together into a workspace container for cross-project context and memory sharing.
        </p>

        <div class="form-row">
          <label class="form-label" for="container-name">Container Name</label>
          <Input
            id="container-name"
            type="text"
            placeholder="e.g., My Full-Stack App"
            bind:value={newContainerName}
            size="md"
          />
        </div>

        {#if filteredWorkspaces.length > 0}
          <div class="project-selection">
            <label class="form-label">Select Projects ({selectedCount} selected)</label>
            <div class="project-list">
              {#each filteredWorkspaces as ws (ws.id)}
                {@const selection = selectedProjects.get(ws.id)}
                <div class="project-selection-item" class:selected={selection?.selected}>
                  <div class="project-checkbox">
                    <Checkbox
                      checked={selection?.selected || false}
                      onchange={() => toggleProjectSelection(ws.id)}
                    />
                  </div>
                  <div class="project-info">
                    <span class="project-name">{ws.name}</span>
                    <span class="project-path">{ws.path}</span>
                  </div>
                  {#if selection?.selected}
                    <div class="project-role">
                      <Select
                        value={selection.role}
                        onchange={(v) => setProjectRole(ws.id, v)}
                        options={roleOptions}
                        size="sm"
                      />
                    </div>
                    <div class="project-primary">
                      <label class="primary-label">
                        <input
                          type="radio"
                          name="primary-project"
                          checked={selection.isPrimary}
                          onchange={() => setPrimaryProject(ws.id)}
                        />
                        Primary
                      </label>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <p class="no-projects">No projects available. Scan for codebases first.</p>
        {/if}

        {#if createError}
          <div class="create-error" role="alert">{createError}</div>
        {/if}

        <div class="form-actions">
          <Button
            variant="primary"
            onclick={handleCreateContainer}
            loading={isCreatingContainer}
            disabled={!newContainerName.trim() || selectedCount === 0}
          >
            Create Container
          </Button>
          <Button variant="ghost" onclick={() => showCreateContainer = false}>
            Cancel
          </Button>
        </div>
      </div>
    {/if}
  </div>

  <div class="discovery-content">
    {#if workspaceManager.isLoading}
      <div class="discovery-loading">Loading workspaces...</div>
    {:else}
      <WorkspaceList workspaces={filteredWorkspaces} onSwitch={onSwitch} onRegister={handleRegister} />
    {/if}
  </div>
</div>

<style>
  .workspace-discovery {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    padding: var(--space-6);
    max-width: 1200px;
    margin: 0 auto;
  }

  .discovery-header {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .discovery-title {
    margin: 0;
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--text-primary);
  }

  .discovery-description {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .discovery-controls {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
  }

  .controls-row {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  .discovery-error {
    padding: var(--space-3) var(--space-4);
    background: var(--error-bg);
    color: var(--error);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
  }

  .discovery-content {
    flex: 1;
  }

  .discovery-loading {
    padding: var(--space-8);
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }

  /* Container Creation Styles */
  .create-container-section {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }

  .create-container-toggle {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border: none;
    cursor: pointer;
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
    text-align: left;
  }

  .create-container-toggle:hover {
    background: var(--bg-tertiary);
  }

  .toggle-icon {
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: var(--text-lg);
    font-weight: 600;
  }

  .create-container-form {
    padding: var(--space-4);
    border-top: 1px solid var(--border-color);
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }

  .form-description {
    margin: 0;
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .form-row {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .form-label {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
  }

  .project-selection {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .project-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 300px;
    overflow-y: auto;
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: var(--space-2);
  }

  .project-selection-item {
    display: flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-2);
    border-radius: var(--radius-md);
    background: var(--bg-primary);
  }

  .project-selection-item.selected {
    background: var(--bg-secondary);
  }

  .project-checkbox {
    flex-shrink: 0;
  }

  .project-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .project-name {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
  }

  .project-path {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .project-role {
    flex-shrink: 0;
    width: 120px;
  }

  .project-primary {
    flex-shrink: 0;
  }

  .primary-label {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    cursor: pointer;
  }

  .no-projects {
    padding: var(--space-4);
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }

  .create-error {
    padding: var(--space-2) var(--space-3);
    background: var(--error-bg);
    color: var(--error);
    border-radius: var(--radius-md);
    font-size: var(--text-sm);
  }

  .form-actions {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }
</style>
