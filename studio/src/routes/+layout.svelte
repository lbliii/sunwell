<!--
  Root Layout — SvelteKit root layout
  
  Handles global initialization and shared layout.
  
  Note: SvelteKit handles routing via file-based routes in src/routes/.
  Project context is now handled by /project/[projectId]/+layout.svelte
  using native SvelteKit dynamic routing.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';
  import { setInitialized } from '$stores/app.svelte';
  import { setupInferenceListeners } from '$lib/inference.svelte';
  import { getProjectSlug } from '$stores/project.svelte';
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
    
    if (!project) {
      // No project - go home
      goto('/');
      return;
    }
    
    // Get slug for project path
    const slug = await getProjectSlug(project);
    if (!slug) {
      // Couldn't resolve slug - go home
      goto('/');
      return;
    }
    
    // Navigate to project using new routing
    const lensQuery = lens ? `?lens=${encodeURIComponent(lens)}` : '';
    if (mode === 'writer') {
      goto(`/project/${slug}/writer${lensQuery}`);
    } else if (mode === 'planning') {
      goto(`/project/${slug}/planning${lensQuery}`);
    } else {
      // Default: project home view
      goto(`/project/${slug}${lensQuery}`);
    }
  }
  
  onMount(() => {
    // Set up inference event listeners for real-time model feedback
    inferenceCleanup = setupInferenceListeners();
    
    // RFC-086: Listen for startup params via WebSocket
    // Note: 'startup_params' is a custom event type not in AgentEventType
    startupCleanup = onEvent((event) => {
      if ((event.type as string) === 'startup_params') {
        handleStartupParams(event.data as unknown as StartupParams);
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

<div class="app-container">
  {@render children?.()}
</div>

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
