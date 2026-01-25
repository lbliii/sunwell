<!--
  WorkspaceStatusBadge — Small badge showing current workspace (RFC-140)
  
  Shows current workspace with health indicator.
  Click to open switcher.
-->
<script lang="ts">
  import { workspaceManager, getCurrentWorkspace } from '../../stores/workspaceManager.svelte';
  import WorkspaceSwitcher from './WorkspaceSwitcher.svelte';

  interface Props {
    onSwitch?: (workspaceId: string) => void;
  }

  let { onSwitch }: Props = $props();

  let switcherOpen = $state(false);

  // Load current workspace on mount and periodically refresh
  $effect(() => {
    if (!workspaceManager.current) {
      getCurrentWorkspace();
    }
    
    // Refresh current workspace every 30 seconds to detect external changes
    const interval = setInterval(() => {
      getCurrentWorkspace();
    }, 30000);
    
    return () => clearInterval(interval);
  });

  function getStatusEmoji(status: string): string {
    switch (status) {
      case 'valid':
        return '✓';
      case 'invalid':
        return '✗';
      case 'not_found':
        return '?';
      default:
        return '○';
    }
  }

  function getStatusColor(status: string): string {
    switch (status) {
      case 'valid':
        return 'var(--success)';
      case 'invalid':
        return 'var(--error)';
      case 'not_found':
        return 'var(--warning)';
      default:
        return 'var(--text-tertiary)';
    }
  }
</script>

<div class="workspace-badge">
  {#if workspaceManager.current}
    <button
      class="badge-button"
      onclick={() => (switcherOpen = true)}
      title="Switch workspace (Cmd+K)"
    >
      <span class="badge-status" style="color: {getStatusColor(workspaceManager.current.status)}">
        {getStatusEmoji(workspaceManager.current.status)}
      </span>
      <span class="badge-name">{workspaceManager.current.name}</span>
    </button>
  {:else}
    <button class="badge-button" onclick={() => (switcherOpen = true)} title="Select workspace">
      <span class="badge-status">○</span>
      <span class="badge-name">No workspace</span>
    </button>
  {/if}

  <WorkspaceSwitcher bind:isOpen={switcherOpen} onSwitch={onSwitch} />
</div>

<style>
  .workspace-badge {
    display: inline-flex;
  }

  .badge-button {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    font-size: var(--text-sm);
  }

  .badge-button:hover {
    background: var(--bg-tertiary);
    border-color: var(--border-subtle);
  }

  .badge-status {
    font-size: var(--text-xs);
    line-height: 1;
  }

  .badge-name {
    color: var(--text-primary);
    font-weight: 500;
  }
</style>
