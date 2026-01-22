<!--
  ErrorState — Error state UI with structured error display (Svelte 5)
  
  Displays structured errors with recovery hints using the unified error system.
  Falls back gracefully for raw error strings from older code paths.
-->
<script lang="ts">
  import Button from '../Button.svelte';
  import ErrorDisplay from '../ui/ErrorDisplay.svelte';
  import { goHome } from '../../stores/app.svelte';
  import { agent, resetAgent, runGoal } from '../../stores/agent.svelte';
  import { parseError } from '$lib/error';
  
  // Parse the raw error into structured format
  const parsedError = $derived(parseError(agent.error));
  
  // Only show retry if error is recoverable and we have a goal to retry
  const canRetry = $derived(parsedError.recoverable && agent.goal);
  
  function handleBack() {
    resetAgent();
    goHome();
  }
  
  async function handleRetry() {
    if (!agent.goal) return;
    
    const goal = agent.goal;
    resetAgent();
    await runGoal(goal);
  }
</script>

<div class="error-state animate-fadeIn">
  <ErrorDisplay 
    error={parsedError}
    onRetry={canRetry ? handleRetry : undefined}
  />
  
  <div class="actions">
    <Button variant="secondary" onclick={handleBack}>Go Back</Button>
  </div>
</div>

<style>
  .error-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4, 16px);
    flex: 1;
    padding: var(--space-8, 32px);
  }
  
  .actions {
    margin-top: var(--space-4, 16px);
    display: flex;
    justify-content: center;
    gap: var(--space-4, 16px);
  }
</style>
