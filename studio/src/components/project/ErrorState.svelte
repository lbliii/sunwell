<!--
  ErrorState — Error state UI (Svelte 5)
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import { goHome } from '../../stores/app.svelte';
  import { agent, resetAgent } from '../../stores/agent.svelte';
  
  function handleBack() {
    resetAgent();
    goHome();
  }
</script>

<div class="error animate-fadeIn" role="alert">
  <div class="error-header">
    <span class="error-icon" aria-hidden="true">⊗</span>
    <span class="error-text">Error</span>
  </div>
  
  <p class="error-message">{agent.error}</p>
  
  <div class="actions">
    <Button variant="secondary" onclick={handleBack}>Go Back</Button>
  </div>
</div>

<style>
  .error { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-4); flex: 1; }
  .error-header { display: flex; align-items: center; gap: var(--space-2); }
  .error-icon { color: var(--error); font-size: var(--text-xl); font-weight: 600; }
  .error-text { font-size: var(--text-lg); font-weight: 500; color: var(--error); }
  .error-message { color: var(--text-secondary); text-align: center; max-width: 400px; margin: 0; }
  .actions { margin-top: var(--space-4); display: flex; justify-content: center; gap: var(--space-4); }
</style>
