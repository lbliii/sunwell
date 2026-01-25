<!--
  WorkspaceDiscovery — Full-page discovery interface (RFC-140)
  
  Shows discovered vs registered workspaces.
  Bulk registration actions.
  Filter by type, location, status.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Button from '../Button.svelte';
  import Input from '../form/Input.svelte';
  import Select from '../form/Select.svelte';
  import WorkspaceList from './WorkspaceList.svelte';
  import {
    workspaceManager,
    loadWorkspaces,
    discoverWorkspaces,
    switchWorkspace,
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

  const filteredWorkspaces = $derived(() => {
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
    <h1 class="discovery-title">Workspace Discovery</h1>
    <p class="discovery-description">
      Discover and manage workspaces across your filesystem. Register workspaces to track them in
      your project registry.
    </p>
  </header>

  <div class="discovery-controls">
    <div class="controls-row">
      <Input
        type="search"
        placeholder="Search workspaces..."
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
        placeholder="Root directory to scan (optional)"
        bind:value={discoveryRoot}
        size="md"
      />
      <Button variant="primary" onclick={handleDiscover} loading={isDiscovering}>
        {isDiscovering ? 'Discovering...' : 'Discover Workspaces'}
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

  .controls-row > :first-child:is(input) {
    flex: 1;
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
</style>
