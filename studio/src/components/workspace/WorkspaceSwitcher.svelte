<!--
  WorkspaceSwitcher — Quick workspace switching dropdown (RFC-140)
  
  Provides:
  - Dropdown/popover for quick workspace switching
  - Shows current workspace with indicator
  - Lists recent workspaces
  - Search/filter capability
  - Keyboard shortcuts (Cmd+K to open)
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '../Button.svelte';
  import Input from '../form/Input.svelte';
  import { workspaceManager, loadWorkspaces, switchWorkspace } from '../../stores/workspaceManager.svelte';

  interface Props {
    isOpen?: boolean;
    onClose?: () => void;
    onSwitch?: (workspaceId: string) => void;
  }

  let { isOpen = $bindable(false), onClose, onSwitch }: Props = $props();

  let searchQuery = $state('');
  let isLoading = $state(false);
  let error = $state<string | null>(null);

  const filteredWorkspaces = $derived(() => {
    if (!searchQuery.trim()) {
      return workspaceManager.workspaces;
    }

    const query = searchQuery.toLowerCase();
    return workspaceManager.workspaces.filter(
      (w) =>
        w.name.toLowerCase().includes(query) ||
        w.id.toLowerCase().includes(query) ||
        w.path.toLowerCase().includes(query)
    );
  });

  // Load workspaces when opened
  $effect(() => {
    if (isOpen && workspaceManager.workspaces.length === 0) {
      loadWorkspaces();
    }
  });

  // Keyboard shortcuts
  function handleKeydown(e: KeyboardEvent) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      isOpen = !isOpen;
      return;
    }

    if (!isOpen) return;

    if (e.key === 'Escape') {
      e.preventDefault();
      isOpen = false;
      onClose?.();
      return;
    }

    // Arrow key navigation could be added here
  }

  async function handleSwitch(workspaceId: string) {
    try {
      isLoading = true;
      error = null;
      await switchWorkspace(workspaceId);
      isOpen = false;
      onSwitch?.(workspaceId);
      onClose?.();
      // Reload workspaces to update current status
      await loadWorkspaces();
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      // Keep switcher open on error so user can try again
    } finally {
      isLoading = false;
    }
  }

  onMount(() => {
    window.addEventListener('keydown', handleKeydown);
    return () => {
      window.removeEventListener('keydown', handleKeydown);
    };
  });
</script>

{#if isOpen}
  <div
    class="switcher-overlay"
    role="presentation"
    onclick={(e) => e.target === e.currentTarget && (isOpen = false)}
  >
    <div class="switcher-popover" role="dialog" aria-label="Workspace Switcher">
      <div class="switcher-header">
        <h3 class="switcher-title">Switch Workspace</h3>
        <Button variant="ghost" size="sm" onclick={() => (isOpen = false)}>✕</Button>
      </div>

      <div class="switcher-search">
        <Input
          type="text"
          placeholder="Search workspaces..."
          bind:value={searchQuery}
          autofocus
        />
      </div>

      {#if error}
        <div class="switcher-error" role="alert">
          {error}
        </div>
      {/if}

      <div class="switcher-list">
        {#if isLoading}
          <div class="switcher-loading">Loading workspaces...</div>
        {:else if filteredWorkspaces.length === 0}
          <div class="switcher-empty">
            {searchQuery ? 'No workspaces match your search' : 'No workspaces found'}
          </div>
        {:else}
          {#each filteredWorkspaces as workspace (workspace.id)}
            <button
              class="switcher-item"
              class:current={workspace.isCurrent}
              onclick={() => handleSwitch(workspace.id)}
              disabled={isLoading || workspace.isCurrent}
            >
              <div class="switcher-item-content">
                <div class="switcher-item-header">
                  <span class="switcher-item-name">{workspace.name}</span>
                  {#if workspace.isCurrent}
                    <span class="switcher-current-badge">Current</span>
                  {/if}
                </div>
                <div class="switcher-item-meta">
                  <span class="switcher-item-id">{workspace.id}</span>
                  <span class="switcher-item-status" class:valid={workspace.status === 'valid'}>
                    {workspace.status}
                  </span>
                </div>
                <div class="switcher-item-path">{workspace.path}</div>
              </div>
            </button>
          {/each}
        {/if}
      </div>

      <div class="switcher-footer">
        <div class="switcher-hint">
          Press <kbd>Esc</kbd> to close • <kbd>Cmd+K</kbd> to toggle
        </div>
      </div>
    </div>
  </div>
{/if}

<style>
  .switcher-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.5);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding-top: 10vh;
    z-index: 1000;
  }

  .switcher-popover {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    width: 90%;
    max-width: 600px;
    max-height: 70vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .switcher-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-color);
  }

  .switcher-title {
    margin: 0;
    font-size: var(--text-lg);
    font-weight: 600;
    color: var(--text-primary);
  }

  .switcher-search {
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-color);
  }

  .switcher-error {
    padding: var(--space-3) var(--space-4);
    background: var(--error-bg);
    color: var(--error);
    font-size: var(--text-sm);
  }

  .switcher-list {
    flex: 1;
    overflow-y: auto;
    padding: var(--space-2);
  }

  .switcher-loading,
  .switcher-empty {
    padding: var(--space-8);
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }

  .switcher-item {
    width: 100%;
    padding: var(--space-3) var(--space-4);
    border: none;
    background: transparent;
    text-align: left;
    cursor: pointer;
    border-radius: var(--radius-md);
    transition: background var(--transition-fast);
  }

  .switcher-item:hover:not(:disabled) {
    background: var(--bg-secondary);
  }

  .switcher-item:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .switcher-item.current {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
  }

  .switcher-item-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .switcher-item-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .switcher-item-name {
    font-weight: 500;
    color: var(--text-primary);
  }

  .switcher-current-badge {
    padding: 2px 6px;
    background: var(--success-bg);
    color: var(--success);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: 500;
  }

  .switcher-item-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .switcher-item-id {
    font-family: var(--font-mono);
  }

  .switcher-item-status {
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
  }

  .switcher-item-status.valid {
    background: var(--success-bg);
    color: var(--success);
  }

  .switcher-item-path {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .switcher-footer {
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--border-color);
    background: var(--bg-secondary);
  }

  .switcher-hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-align: center;
  }

  .switcher-hint kbd {
    padding: 2px 6px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
    font-size: 10px;
  }
</style>
