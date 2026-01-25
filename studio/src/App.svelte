<!--
  App — Root component (Svelte 5)
  
  Handles routing between screens and initializes the app.
  RFC-132: ProjectGate ensures valid project before showing app.
-->
<script lang="ts">
  import { untrack, onMount } from 'svelte';
  import Home from './routes/Home.svelte';
  import Project from './routes/Project.svelte';
  import Projects from './routes/Projects.svelte';
  import Preview from './routes/Preview.svelte';
  import Planning from './routes/Planning.svelte';
  import Library from './routes/Library.svelte';
  import Interface from './routes/Interface.svelte';
  import Writer from './routes/Writer.svelte';
  import Demo from './routes/Demo.svelte';
  import Gallery from './routes/Gallery.svelte';  // RFC-097
  import Evaluation from './routes/Evaluation.svelte';  // RFC-098
  import Observatory from './routes/Observatory.svelte';  // RFC-112
  import ProjectGate from './components/ProjectGate.svelte';  // RFC-132
  import { app, setInitialized, navigate, goToWriter } from './stores/app.svelte';
  import { Route } from '$lib/constants';
  import { setupInferenceListeners } from '$lib/inference';
  import { openProject } from './stores/project.svelte';
  import { onEvent } from '$lib/socket';
  
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
    inferenceCleanup = setupInferenceListeners();
    
    // RFC-086: Listen for startup params via WebSocket
    startupCleanup = onEvent((event) => {
      if (event.type === 'startup_params') {
        handleStartupParams(event.data as StartupParams);
      }
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

<ProjectGate>
  {#snippet children()}
    <div class="app-container">
      {#if app.route === Route.HOME}
        <Home />
      {:else if app.route === Route.PROJECT}
        <Project />
      {:else if app.route === Route.PROJECTS}
        <Projects />
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
      {:else if app.route === Route.DEMO}
        <Demo />
      {:else if app.route === Route.GALLERY}
        <Gallery />
      {:else if app.route === Route.EVALUATION}
        <Evaluation />
      {:else if app.route === Route.OBSERVATORY}
        <Observatory />
      {/if}
    </div>
  {/snippet}
</ProjectGate>

<style>
  .app-container { min-height: 100vh; display: flex; flex-direction: column; }
</style>
