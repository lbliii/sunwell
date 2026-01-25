<!--
  CurrentWorkspaceIndicator — Header component showing current workspace (RFC-140)
  
  Breadcrumb-style navigation with quick actions menu.
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import WorkspaceSwitcher from './WorkspaceSwitcher.svelte';
  import { workspaceManager, getCurrentWorkspace } from '../../stores/workspaceManager.svelte';

  interface Props {
    onSwitch?: (workspaceId: string) => void;
  }

  let { onSwitch }: Props = $props();

  let switcherOpen = $state(false);
  let menuOpen = $state(false);

  // Load current workspace on mount
  $effect(() => {
    if (!workspaceManager.current) {
      getCurrentWorkspace();
    }
  });

  function handleSwitch(workspaceId: string) {
    switcherOpen = false;
    onSwitch?.(workspaceId);
  }
</script>

<div class="workspace-indicator">
  {#if workspaceManager.current}
    <div class="indicator-content">
      <div class="indicator-breadcrumb">
        <span class="breadcrumb-label">Workspace:</span>
        <button class="breadcrumb-value" onclick={() => (switcherOpen = true)}>
          {workspaceManager.current.name}
        </button>
        <span class="breadcrumb-separator">/</span>
        <span class="breadcrumb-path">{workspaceManager.current.path}</span>
      </div>

      <div class="indicator-status">
        <span
          class="status-dot"
          class:valid={workspaceManager.current.status === 'valid'}
          class:invalid={workspaceManager.current.status === 'invalid'}
          title="Workspace status: {workspaceManager.current.status}"
        ></span>
        <span class="status-text">{workspaceManager.current.status}</span>
      </div>
    </div>
  {:else}
    <div class="indicator-content">
      <div class="indicator-breadcrumb">
        <span class="breadcrumb-label">Workspace:</span>
        <button class="breadcrumb-value" onclick={() => (switcherOpen = true)}>
          No workspace selected
        </button>
      </div>
    </div>
  {/if}

  <WorkspaceSwitcher bind:isOpen={switcherOpen} onSwitch={handleSwitch} />
</div>

<style>
  .workspace-indicator {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }

  .indicator-content {
    display: flex;
    align-items: center;
    gap: var(--space-4);
  }

  .indicator-breadcrumb {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
  }

  .breadcrumb-label {
    font-weight: 500;
  }

  .breadcrumb-value {
    background: none;
    border: none;
    padding: 0;
    color: var(--text-primary);
    font-weight: 500;
    cursor: pointer;
    text-decoration: underline;
    text-decoration-color: transparent;
    transition: text-decoration-color var(--transition-fast);
  }

  .breadcrumb-value:hover {
    text-decoration-color: var(--text-primary);
  }

  .breadcrumb-separator {
    color: var(--text-tertiary);
  }

  .breadcrumb-path {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    max-width: 300px;
  }

  .indicator-status {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-tertiary);
  }

  .status-dot.valid {
    background: var(--success);
  }

  .status-dot.invalid {
    background: var(--error);
  }

  .status-text {
    text-transform: capitalize;
  }
</style>
