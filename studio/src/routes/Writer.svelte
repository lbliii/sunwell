<!--
  Writer Route — Universal Writing Environment (RFC-086)
  
  Full-screen writing surface with lens-powered expertise.
  RFC-133: URL params for deep linking (#/writer?lens=coder&file=/path/to/file)
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

  // RFC-133: Get params from URL (type-safe)
  // URL format: #/writer?lens=<name>&file=<path>
  const filePath = $derived(
    typeof app.params?.file === 'string' ? app.params.file : undefined
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
