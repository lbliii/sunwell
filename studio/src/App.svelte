<!--
  App — Root component (Svelte 5)
  
  Handles routing between screens and initializes the app.
-->
<script lang="ts">
  import { untrack, onMount } from 'svelte';
  import { listen } from '@tauri-apps/api/event';
  import Home from './routes/Home.svelte';
  import Project from './routes/Project.svelte';
  import Preview from './routes/Preview.svelte';
  import Planning from './routes/Planning.svelte';
  import Library from './routes/Library.svelte';
  import Interface from './routes/Interface.svelte';
  import Writer from './routes/Writer.svelte';
  import { app, setInitialized, navigate, goToWriter } from './stores/app.svelte';
  import { Route } from '$lib/constants';
  import { setupInferenceListeners } from '$lib/inference';
  import { openProject } from './stores/project.svelte';
  
  // RFC-086: Startup params from CLI
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
    
    // Navigate based on mode
    if (mode === 'writer') {
      goToWriter(undefined, lens ?? undefined);
    } else if (mode === 'planning') {
      navigate(Route.PLANNING, { lens });
    } else {
      // Default: code mode → PROJECT view
      navigate(Route.PROJECT, { lens });
    }
  }
  
  onMount(() => {
    // Set up inference event listeners for real-time model feedback
    setupInferenceListeners().then(cleanup => {
      inferenceCleanup = cleanup;
    });
    
    // RFC-086: Listen for CLI startup params
    listen<StartupParams>('startup-params', (event) => {
      handleStartupParams(event.payload);
    }).then(unlisten => {
      startupCleanup = unlisten;
    });
    
    return () => {
      // Clean up on unmount
      inferenceCleanup?.();
      startupCleanup?.();
    };
  });
  
  $effect(() => {
    untrack(() => { setInitialized(true); });
  });
</script>

<div class="app-container">
  {#if app.route === Route.HOME}
    <Home />
  {:else if app.route === Route.PROJECT}
    <Project />
  {:else if app.route === Route.PREVIEW}
    <Preview />
  {:else if app.route === Route.PLANNING}
    <Planning />
  {:else if app.route === Route.LIBRARY}
    <Library />
  {:else if app.route === Route.INTERFACE}
    <Interface />
  {:else if app.route === Route.WRITER}
    <Writer />
  {/if}
</div>

<style>
  .app-container { min-height: 100vh; display: flex; flex-direction: column; }
</style>
