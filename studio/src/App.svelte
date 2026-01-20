<!--
  App — Root component
  
  Handles routing between screens and initializes the app.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import Home from './routes/Home.svelte';
  import Project from './routes/Project.svelte';
  import Preview from './routes/Preview.svelte';
  import { currentRoute, isInitialized } from './stores/app';
  
  onMount(() => {
    isInitialized.set(true);
  });
</script>

<div class="app-container">
  {#if $currentRoute === 'home'}
    <Home />
  {:else if $currentRoute === 'project'}
    <Project />
  {:else if $currentRoute === 'preview'}
    <Preview />
  {/if}
</div>

<style>
  .app-container {
    min-height: 100vh;
    display: flex;
    flex-direction: column;
  }
</style>
