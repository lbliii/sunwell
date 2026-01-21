<!--
  App — Root component (Svelte 5)
  
  Handles routing between screens and initializes the app.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import Home from './routes/Home.svelte';
  import Project from './routes/Project.svelte';
  import Preview from './routes/Preview.svelte';
  import Planning from './routes/Planning.svelte';
  import Library from './routes/Library.svelte';
  import Interface from './routes/Interface.svelte';
  import { app, setInitialized } from './stores/app.svelte';
  import { Route } from '$lib/constants';
  
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
  {/if}
</div>

<style>
  .app-container { min-height: 100vh; display: flex; flex-direction: column; }
</style>
