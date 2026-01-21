<!--
  Library — Lens Library Page (RFC-070)
  
  Full-page lens library browser with management capabilities.
-->
<script lang="ts">
  import { LensLibrary } from '../components';
  import Button from '../components/Button.svelte';
  import { goHome } from '../stores/app.svelte';
  
  function handleLensSelect(lensName: string) {
    // Could navigate back home with lens selected
    console.log('Selected lens:', lensName);
    goHome();
  }
</script>

<div class="library-page">
  <header class="page-header">
    <Button variant="ghost" onclick={goHome}>
      ← Back to Home
    </Button>
  </header>
  
  <main class="page-content">
    <LensLibrary 
      onSelect={handleLensSelect}
      showSelectButton={false}
    />
  </main>
</div>

<style>
  .library-page {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-primary);
  }
  
  .page-header {
    padding: var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
    background: var(--bg-secondary);
  }
  
  .page-content {
    flex: 1;
    overflow: hidden;
  }
</style>
