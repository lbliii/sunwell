<!--
  ErrorDisplay — Structured error display with recovery hints
  
  Displays SunwellError objects with:
  - Error ID and category icon
  - User-friendly message
  - Recovery hints (expandable)
  - Retry button (if recoverable)
  
  Usage:
    <ErrorDisplay error={parsedError} onRetry={handleRetry} onDismiss={handleDismiss} />
    <ErrorDisplay error={parsedError} compact />
-->
<script lang="ts">
  import { type SunwellError, getCategoryIcon } from '$lib/error';
  import { fly } from 'svelte/transition';
  
  interface Props {
    error: SunwellError;
    onDismiss?: () => void;
    onRetry?: () => void;
    compact?: boolean;
  }
  
  let { error, onDismiss, onRetry, compact = false }: Props = $props();
  
  const icon = $derived(getCategoryIcon(error.category));
  const hasHints = $derived(error.recovery_hints && error.recovery_hints.length > 0);
</script>

<div 
  class="error-display" 
  class:compact
  class:recoverable={error.recoverable}
  role="alert" 
  transition:fly={{ y: -20, duration: 200 }}
>
  <header class="error-header">
    <span class="error-icon" aria-hidden="true">{icon}</span>
    <span class="error-id">{error.error_id}</span>
    {#if onDismiss}
      <button class="dismiss" onclick={onDismiss} aria-label="Dismiss">✕</button>
    {/if}
  </header>
  
  {#if compact}
    <p class="error-message-inline">{error.message}</p>
  {:else}
    <p class="error-message">{error.message}</p>
    
    {#if hasHints}
      <div class="recovery-hints">
        <strong>What you can do:</strong>
        <ol>
          {#each error.recovery_hints ?? [] as hint, i (i)}
            <li>{hint}</li>
          {/each}
        </ol>
      </div>
    {/if}
    
    {#if error.recoverable && onRetry}
      <footer class="error-actions">
        <button class="retry" onclick={onRetry}>Try Again</button>
      </footer>
    {/if}
  {/if}
</div>

<style>
  .error-display {
    background: var(--surface-error, hsl(0 20% 12%));
    border: 1px solid var(--error);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    max-width: 480px;
    font-family: var(--font-sans, system-ui);
  }
  
  .error-display.compact {
    padding: var(--space-2) var(--space-3);
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  
  .error-display.recoverable {
    border-color: var(--warning);
  }
  
  .error-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    margin-bottom: var(--space-2);
  }
  
  .compact .error-header {
    margin-bottom: 0;
    flex-shrink: 0;
  }
  
  .error-icon { 
    font-size: 1.25rem; 
    line-height: 1;
  }
  
  .compact .error-icon { 
    font-size: 1rem; 
  }
  
  .error-id {
    font-family: var(--font-mono, ui-monospace, monospace);
    font-size: var(--text-sm);
    color: var(--error);
    font-weight: 600;
  }
  
  .recoverable .error-id {
    color: var(--warning);
  }
  
  .dismiss {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    padding: var(--space-1);
    border-radius: var(--radius-sm);
    font-size: var(--text-sm);
    line-height: 1;
    transition: background 0.15s, color 0.15s;
  }
  
  .dismiss:hover {
    background: var(--surface-2, hsl(0 0% 20%));
    color: var(--text-primary);
  }
  
  .error-message {
    color: var(--text-primary);
    margin: 0 0 var(--space-3);
    line-height: 1.5;
    font-size: var(--text-base);
  }
  
  .error-message-inline {
    color: var(--text-primary);
    margin: 0;
    line-height: 1.4;
    font-size: var(--text-sm);
    flex: 1;
  }
  
  .recovery-hints {
    background: var(--surface-1, hsl(0 0% 15%));
    border-radius: var(--radius-sm);
    padding: var(--space-3);
    font-size: var(--text-sm);
    margin-bottom: var(--space-3);
  }
  
  .recovery-hints strong {
    color: var(--text-primary);
    display: block;
    margin-bottom: var(--space-2);
  }
  
  .recovery-hints ol {
    margin: 0;
    padding-left: var(--space-4);
  }
  
  .recovery-hints li {
    margin: var(--space-1) 0;
    color: var(--text-secondary);
    line-height: 1.4;
  }
  
  .error-actions {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }
  
  .retry {
    background: var(--error);
    color: white;
    border: none;
    padding: var(--space-2) var(--space-4);
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-weight: 500;
    font-size: var(--text-sm);
    transition: opacity 0.15s, transform 0.1s;
  }
  
  .recoverable .retry {
    background: var(--warning);
    color: var(--surface-1, hsl(0 0% 15%));
  }
  
  .retry:hover {
    opacity: 0.9;
  }
  
  .retry:active {
    transform: scale(0.98);
  }
</style>
