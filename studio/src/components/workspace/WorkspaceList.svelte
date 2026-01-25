<!--
  WorkspaceList — Unified workspace listing (RFC-140)
  
  Shows registered + discovered workspaces grouped by status.
  Actions: switch, register, remove
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import { workspaceManager, switchWorkspace, discoverWorkspaces } from '../../stores/workspaceManager.svelte';
  import type { WorkspaceInfo } from '../../stores/workspaceManager.svelte';

  interface Props {
    workspaces?: WorkspaceInfo[];
    onSwitch?: (workspaceId: string) => void;
    onRegister?: (path: string) => void;
  }

  let { workspaces, onSwitch, onRegister }: Props = $props();

  const displayWorkspaces = $derived(workspaces || workspaceManager.workspaces);

  // Group workspaces by status
  const grouped = $derived(() => {
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
</script>

<div class="workspace-list">
  {#if grouped.registered.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">Registered Workspaces ({grouped.registered.length})</h3>
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
            </div>
          </div>
        {/each}
      </div>
    </section>
  {/if}

  {#if grouped.discovered.length > 0}
    <section class="workspace-group">
      <h3 class="group-title">Discovered Workspaces ({grouped.discovered.length})</h3>
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
      <h3 class="group-title">Invalid Workspaces ({grouped.invalid.length})</h3>
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
      <p class="empty-title">No workspaces found</p>
      <p class="empty-description">
        {grouped.registered.length === 0 &&
        grouped.discovered.length === 0 &&
        grouped.invalid.length === 0
          ? 'No workspaces available. Try discovering workspaces or creating a new project.'
          : 'No workspaces match the current filters.'}
      </p>
      <Button variant="primary" onclick={() => discoverWorkspaces()}>
        Discover Workspaces
      </Button>
    </div>
  {/if}
</div>

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
</style>
