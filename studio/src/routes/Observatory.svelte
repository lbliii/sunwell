<!--
  Observatory — AI Cognition Visualizations (RFC-112)
  
  Standalone route to visualize Sunwell's cognitive architecture.
  Five cinematic visualizations: ResonanceWave, PrismFracture, MemoryLattice, ExecutionCinema, ModelParadox.
-->
<script lang="ts">
  import { ObservatoryPanel } from '../components';
  import { goHome } from '../stores/app.svelte';
</script>

<div class="observatory-route">
  <button class="back-button" onclick={goHome}>
    ← Back
  </button>
  
  <ObservatoryPanel />
</div>

<style>
  .observatory-route {
    min-height: 100vh;
    background: var(--bg-primary);
    position: relative;
  }
  
  .back-button {
    position: fixed;
    top: var(--space-4);
    left: var(--space-4);
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    z-index: 10;
  }
  
  .back-button:hover {
    color: var(--text-primary);
    border-color: var(--border-default);
  }
</style>
