<!--
  Writer Route — Universal Writing Environment (RFC-086)
  
  Full-screen writing surface with lens-powered expertise.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { fade } from 'svelte/transition';
  import { WriterSurface } from '../components';
  import {
    writerState,
    loadDocument,
    setLens,
    workflowState,
    loadChains,
  } from '../stores';
  import { app } from '../stores/app.svelte';

  // Get params from navigation (type-safe without assertions)
  const filePath = $derived(
    typeof app.params?.filePath === 'string' ? app.params.filePath : undefined
  );
  const lensName = $derived(
    typeof app.params?.lens === 'string' ? app.params.lens : 'tech-writer'
  );

  onMount(async () => {
    // Load workflow chains
    await loadChains();

    // Set lens if specified
    if (lensName) {
      await setLens(lensName);
    }

    // Load document if specified
    if (filePath) {
      await loadDocument(filePath);
    }
  });
</script>

<div class="writer-route" transition:fade={{ duration: 150 }}>
  <WriterSurface
    filePath={filePath}
    lensName={lensName}
  />
</div>

<style>
  .writer-route {
    width: 100%;
    height: 100%;
    background: var(--bg-primary, #0d0d0d);
  }
</style>
