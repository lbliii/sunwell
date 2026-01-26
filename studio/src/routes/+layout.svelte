<!--
  Root Layout — SvelteKit root layout
  
  Handles global initialization and shared layout.
  ProjectGate ensures valid project before showing app routes.
  
  Note: SvelteKit handles routing via file-based routes in src/routes/.
  The old hash-based router (initRouter) is no longer used.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import ProjectGate from '$components/ProjectGate.svelte';
  import { setInitialized } from '$stores/app.svelte';
  import { setupInferenceListeners } from '$lib/inference';
  import { openProject } from '$stores/project.svelte';
  import { onEvent } from '$lib/socket';
  import '../styles/global.css';
  
  interface Props {
    children: import('svelte').Snippet;
  }
  
  let { children }: Props = $props();
  
  // RFC-086: Startup params from CLI (via WebSocket event)
  interface StartupParams {
    project: string | null;
    lens: string | null;
    mode: string | null;
  }
  
  // RFC-081: Wire up inference visibility listeners
  let inferenceCleanup: (() => void) | null = null;
  let startupCleanup: (() => void) | null = null;
  
  async function handleStartupParams(params: StartupParams): Promise<void> {
    const { project, lens, mode } = params;
    
    // Open project in store if provided
    if (project) {
      await openProject(project);
    }
    
    // Navigate based on mode (using SvelteKit's goto)
    const lensQuery = lens ? `?lens=${encodeURIComponent(lens)}` : '';
    if (mode === 'writer') {
      goto(`/writer${lensQuery}`);
    } else if (mode === 'planning') {
      goto(`/planning${lensQuery}`);
    } else {
      // Default: code mode → PROJECT view
      goto(`/project${lensQuery}`);
    }
  }
  
  onMount(() => {
    // Set up inference event listeners for real-time model feedback
    inferenceCleanup = setupInferenceListeners();
    
    // RFC-086: Listen for startup params via WebSocket
    startupCleanup = onEvent((event) => {
      if (event.type === 'startup_params') {
        handleStartupParams(event.data as StartupParams);
      }
    });
    
    // Mark as initialized
    setInitialized(true);
    
    return () => {
      // Clean up on unmount
      inferenceCleanup?.();
      startupCleanup?.();
    };
  });
</script>

<ProjectGate>
  {#snippet children()}
    <div class="app-container">
      {@render children?.()}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .app-container {
    width: 100%;
    height: 100vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    background-color: var(--bg-primary, #121212);
    color: var(--text-primary, #ffffff);
  }
</style>
