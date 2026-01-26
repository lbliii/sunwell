<!--
  WorkspaceList — Unified workspace listing (RFC-140, RFC-141)
  
  Shows registered + discovered workspaces grouped by status.
  Supports multi-project workspace containers.
  Actions: switch, register, remove, delete
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import WorkspaceDeleteDialog from './WorkspaceDeleteDialog.svelte';
  import { workspaceManager, switchWorkspace, switchContainer, discoverWorkspaces, loadWorkspaces } from '../../stores/workspaceManager.svelte';
  import type { WorkspaceInfo, WorkspaceContainer } from '../../stores/workspaceManager.svelte';

  interface Props {
    workspaces?: WorkspaceInfo[];
    containers?: WorkspaceContainer[];
    onSwitch?: (workspaceId: string) => void;
    onSwitchContainer?: (containerId: string) => void;
    onRegister?: (path: string) => void;
    onDelete?: (workspaceId: string) => void;
    showContainers?: boolean;
  }

  let { workspaces, containers, onSwitch, onSwitchContainer, onRegister, onDelete, showContainers = true }: Props = $props();

  const displayWorkspaces = $derived(workspaces || workspaceManager.workspaces);
  const displayContainers = $derived(containers || workspaceManager.containers);
  const currentContainer = $derived(workspaceManager.currentContainer);

  // Delete dialog state
  let deleteDialogWorkspace = $state<WorkspaceInfo | null>(null);

  // Group workspaces by status
  const grouped = $derived.by(() => {
    const groups: {
      registered: WorkspaceInfo[];
      discovered: WorkspaceInfo[];
      invalid: WorkspaceInfo[];
    } = {
      registered: [],
      discovered: [],
      invalid: [],
    };

    for (const ws of displayWorkspaces) {
      if (ws.status === 'invalid' || ws.status === 'not_found') {
        groups.invalid.push(ws);
      } else if (ws.isRegistered) {
        groups.registered.push(ws);
      } else {
        groups.discovered.push(ws);
      }
    }

    return groups;
  });

  async function handleSwitch(workspaceId: string) {
    try {
      await switchWorkspace(workspaceId);
      onSwitch?.(workspaceId);
    } catch (e) {
      console.error('Failed to switch workspace:', e);
    }
  }

  async function handleSwitchContainer(containerId: string) {
    try {
      await switchContainer(containerId);
      onSwitchContainer?.(containerId);
    } catch (e) {
      console.error('Failed to switch container:', e);
    }
  }

  async function handleRegister(path: string) {
    // Call API to register workspace
    try {
      // This would call an API endpoint to register
      // For now, just call the callback
      onRegister?.(path);
    } catch (e) {
      console.error('Failed to register workspace:', e);
    }
  }

  function getRoleBadgeClass(role: string): string {
    switch (role) {
      case 'frontend': return 'role-frontend';
      case 'backend': return 'role-backend';
      case 'api': return 'role-api';
      case 'shared': return 'role-shared';
      default: return 'role-default';
    }
  }

  function openDeleteDialog(workspace: WorkspaceInfo) {
    deleteDialogWorkspace = workspace;
  }

  function closeDeleteDialog() {
    deleteDialogWorkspace = null;
  }

  async function handleDeleted() {
    // Reload workspace list after deletion
    await loadWorkspaces();
    onDelete?.(deleteDialogWorkspace?.id ?? '');
    closeDeleteDialog();
  }
</script>

<div class="workspace-list">
  {#if showContainers && displayContainers.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">Workspaces ({displayContainers.length})</h3>
      <div class="workspace-items">
        {#each displayContainers as container (container.id)}
          <div class="workspace-item container-item" class:current={currentContainer?.id === container.id}>
            <div class="workspace-item-content">
              <div class="workspace-item-header">
                <span class="workspace-item-name">{container.name}</span>
                {#if currentContainer?.id === container.id}
                  <span class="current-badge">Current</span>
                {/if}
                <span class="project-count">{container.projects.length} projects</span>
              </div>
              <div class="container-projects">
                {#each container.projects.slice(0, 3) as project (project.id)}
                  <span class="project-chip" class:primary={project.isPrimary}>
                    <span class="role-badge {getRoleBadgeClass(project.role)}">{project.role}</span>
                    {project.id}
                  </span>
                {/each}
                {#if container.projects.length > 3}
                  <span class="more-projects">+{container.projects.length - 3} more</span>
                {/if}
              </div>
            </div>
            <div class="workspace-item-actions">
              {#if currentContainer?.id !== container.id}
                <Button variant="ghost" size="sm" onclick={() => handleSwitchContainer(container.id)}>
                  Open
                </Button>
              {/if}
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if grouped.registered.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">Sunwell Projects ({grouped.registered.length})</h3>
      <div class="workspace-items">
        {#each grouped.registered as workspace (workspace.id)}
          <div class="workspace-item" class:current={workspace.isCurrent}>
            <div class="workspace-item-content">
              <div class="workspace-item-header">
                <span class="workspace-item-name">{workspace.name}</span>
                {#if workspace.isCurrent}
                  <span class="current-badge">Current</span>
                {/if}
              </div>
              <div class="workspace-item-meta">
                <span class="workspace-item-id">{workspace.id}</span>
                <span class="workspace-item-path">{workspace.path}</span>
              </div>
            </div>
            <div class="workspace-item-actions">
              {#if !workspace.isCurrent}
                <Button variant="ghost" size="sm" onclick={() => handleSwitch(workspace.id)}>
                  Switch
                </Button>
              {/if}
              <Button variant="ghost" size="sm" onclick={() => openDeleteDialog(workspace)}>
                Delete
              </Button>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if grouped.discovered.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">External Codebases ({grouped.discovered.length})</h3>
      <div class="workspace-items">
        {#each grouped.discovered as workspace (workspace.id)}
          <div class="workspace-item" class:current={workspace.isCurrent}>
            <div class="workspace-item-content">
              <div class="workspace-item-header">
                <span class="workspace-item-name">{workspace.name}</span>
                {#if workspace.isCurrent}
                  <span class="current-badge">Current</span>
                {/if}
              </div>
              <div class="workspace-item-meta">
                <span class="workspace-item-id">{workspace.id}</span>
                <span class="workspace-item-path">{workspace.path}</span>
              </div>
            </div>
            <div class="workspace-item-actions">
              {#if !workspace.isCurrent}
                <Button variant="ghost" size="sm" onclick={() => handleSwitch(workspace.id)}>
                  Switch
                </Button>
              {/if}
              <Button variant="ghost" size="sm" onclick={() => handleRegister(workspace.path)}>
                Register
              </Button>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if grouped.invalid.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">Invalid ({grouped.invalid.length})</h3>
      <div class="workspace-items">
        {#each grouped.invalid as workspace (workspace.id)}
          <div class="workspace-item invalid">
            <div class="workspace-item-content">
              <div class="workspace-item-header">
                <span class="workspace-item-name">{workspace.name}</span>
                <span class="status-badge invalid">{workspace.status}</span>
              </div>
              <div class="workspace-item-meta">
                <span class="workspace-item-id">{workspace.id}</span>
                <span class="workspace-item-path">{workspace.path}</span>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if displayWorkspaces.length === 0}
    <div class="empty-state">
      <p class="empty-title">No projects found</p>
      <p class="empty-description">
        {grouped.registered.length === 0 &&
        grouped.discovered.length === 0 &&
        grouped.invalid.length === 0
          ? 'No projects available. Create a new project from the home screen, or scan for external codebases.'
          : 'No items match the current filters.'}
      </p>
      <Button variant="primary" onclick={() => discoverWorkspaces()}>
        Scan for Codebases
      </Button>
    </div>
  {/if}
</div>

{#if deleteDialogWorkspace}
  <WorkspaceDeleteDialog
    workspace={deleteDialogWorkspace}
    onClose={closeDeleteDialog}
    onDeleted={handleDeleted}
  />
{/if}

<style>
  .workspace-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
  }

  .workspace-group {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .group-title {
    margin: 0;
    font-size: var(--text-base);
    font-weight: 600;
    color: var(--text-primary);
  }

  .workspace-items {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .workspace-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
  }

  .workspace-item:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-subtle);
  }

  .workspace-item.current {
    background: var(--bg-tertiary);
    border-color: var(--gold);
  }

  .workspace-item.invalid {
    opacity: 0.6;
  }

  .workspace-item-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .workspace-item-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .workspace-item-name {
    font-weight: 500;
    color: var(--text-primary);
  }

  .current-badge {
    padding: 2px 6px;
    background: var(--success-bg);
    color: var(--success);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .status-badge {
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .status-badge.invalid {
    background: var(--error-bg);
    color: var(--error);
  }

  .workspace-item-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .workspace-item-id {
    font-family: var(--font-mono);
  }

  .workspace-item-path {
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 400px;
  }

  .workspace-item-actions {
    display: flex;
    gap: var(--space-2);
  }

  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8);
    text-align: center;
  }

  .empty-title {
    margin: 0 0 var(--space-2);
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--text-primary);
  }

  .empty-description {
    margin: 0 0 var(--space-4);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }

  /* Container-specific styles */
  .container-item {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-3);
  }

  .container-item .workspace-item-content {
    width: 100%;
  }

  .container-item .workspace-item-actions {
    align-self: flex-end;
  }

  .project-count {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
  }

  .container-projects {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .project-chip {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    padding: 2px 8px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    color: var(--text-secondary);
  }

  .project-chip.primary {
    border-color: var(--gold);
    background: var(--gold-bg);
  }

  .role-badge {
    padding: 1px 4px;
    border-radius: var(--radius-xs);
    font-size: 10px;
    font-weight: 500;
    text-transform: uppercase;
  }

  .role-frontend {
    background: #e0f2fe;
    color: #0369a1;
  }

  .role-backend {
    background: #dcfce7;
    color: #15803d;
  }

  .role-api {
    background: #fef3c7;
    color: #b45309;
  }

  .role-shared {
    background: #f3e8ff;
    color: #7c3aed;
  }

  .role-default {
    background: var(--bg-secondary);
    color: var(--text-tertiary);
  }

  .more-projects {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-style: italic;
  }
</style>
