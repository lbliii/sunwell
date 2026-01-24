<!--
  Observatory — AI Cognition Visualizations (RFC-112)
  
  Standalone route to visualize Sunwell's cognitive architecture.
  Five cinematic visualizations: ResonanceWave, PrismFracture, MemoryLattice, ExecutionCinema, ModelParadox.
  
  Features:
  - Export to PNG/GIF/JSON
  - Shareable URLs
  - Mobile-responsive layout
-->
<script lang="ts">
  import { ObservatoryPanel } from '../components';
  import { goHome } from '../stores/app.svelte';
  import { parseShareUrl } from '$lib/export';
  import { onMount } from 'svelte';
  
  // Handle share URLs on mount
  onMount(() => {
    if (typeof window !== 'undefined') {
      const shareConfig = parseShareUrl(window.location.href);
      if (shareConfig) {
        // TODO: Apply share config to visualization state
        console.log('Share config detected:', shareConfig);
      }
    }
  });
</script>

<div class="observatory-route">
  <button class="back-button" onclick={goHome} aria-label="Go back to home">
    <span class="back-arrow">←</span>
    <span class="back-text">Back</span>
  </button>
  
  <ObservatoryPanel />
</div>

<style>
  .observatory-route {
    min-height: 100vh;
    min-height: 100dvh; /* Dynamic viewport for mobile */
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
    z-index: 50;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .back-button:hover {
    color: var(--text-primary);
    border-color: var(--border-default);
    background: var(--bg-tertiary);
  }
  
  .back-arrow {
    font-size: var(--text-base);
  }
  
  /* Mobile responsive adjustments */
  @media (max-width: 768px) {
    .back-button {
      top: var(--space-3);
      left: var(--space-3);
      padding: var(--space-2) var(--space-3);
    }
    
    .back-text {
      display: none; /* Just show arrow on mobile */
    }
    
    .back-arrow {
      font-size: var(--text-lg);
    }
  }
  
  /* Reduced motion preference */
  @media (prefers-reduced-motion: reduce) {
    .back-button {
      transition: none;
    }
  }
</style>
