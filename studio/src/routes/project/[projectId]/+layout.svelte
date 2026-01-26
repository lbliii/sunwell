<!--
  Project Layout — Loads project context for all project-scoped routes
  
  Uses SvelteKit's native page store for reactive routing.
  No history API patches needed - the page store handles navigation reactively.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { untrack } from 'svelte';
  import { project, openProjectById } from '$stores/project.svelte';
  import Spinner from '$lib/components/ui/Spinner.svelte';
  
  interface Props {
    children: Snippet;
  }
  
  let { children }: Props = $props();
  
  // Reactive project ID from URL params
  const projectId = $derived($page.params.projectId);
  
  // Loading state
  let isLoading = $state(true);
  let loadError = $state<string | null>(null);
  
  // Track which project ID we've loaded to avoid redundant loads
  let loadedProjectId = $state<string | null>(null);
  
  // Load project when projectId changes
  $effect(() => {
    const id = projectId;
    
    // Skip if already loaded this project
    if (id === loadedProjectId && project.current) {
      isLoading = false;
      return;
    }
    
    if (id) {
      untrack(async () => {
        isLoading = true;
        loadError = null;
        
        try {
          const loaded = await openProjectById(id);
          if (loaded) {
            loadedProjectId = id;
          } else {
            loadError = `Project "${id}" not found`;
          }
        } catch (e) {
          loadError = e instanceof Error ? e.message : 'Failed to load project';
        } finally {
          isLoading = false;
        }
      });
    }
  });
  
  function goHome() {
    goto('/');
  }
</script>

{#if isLoading}
  <div class="loading-state">
    <Spinner style="moon" speed={100} />
    <p>Loading project...</p>
  </div>
{:else if loadError}
  <div class="error-state">
    <h2>Project Not Found</h2>
    <p>{loadError}</p>
    <button class="home-btn" onclick={goHome}>Go Home</button>
  </div>
{:else if project.current}
  {@render children()}
{:else}
  <div class="error-state">
    <h2>No Project</h2>
    <p>No project is currently loaded.</p>
    <button class="home-btn" onclick={goHome}>Go Home</button>
  </div>
{/if}

<style>
  .loading-state,
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    height: 100vh;
    gap: var(--space-4);
    color: var(--text-secondary);
  }
  
  .loading-state p {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .error-state h2 {
    color: var(--text-primary);
    font-size: var(--text-xl);
    margin: 0;
  }
  
  .error-state p {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  .home-btn {
    margin-top: var(--space-4);
    padding: var(--space-2) var(--space-4);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .home-btn:hover {
    background: var(--bg-secondary);
    border-color: var(--border-emphasis);
  }
</style>
