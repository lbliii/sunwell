<!--
  Demo — The Prism Principle Demonstration (RFC-095)
  
  Standalone route to showcase Sunwell's cognitive architecture.
-->
<script lang="ts">
  import { DemoPanel } from '../components';
  import { goHome } from '../stores/app.svelte';
  
  function handleRunTask(goal: string) {
    // Navigate to home with the goal pre-filled
    goHome();
    // TODO: Pre-fill the goal in the input bar
  }
</script>

<div class="demo-route">
  <button class="back-button" onclick={goHome}>
    ← Back
  </button>
  
  <DemoPanel onRunTask={handleRunTask} />
</div>

<style>
  .demo-route {
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
