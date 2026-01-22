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
          {#each error.recovery_hints ?? [] as hint}
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
    border: 1px solid var(--error, #e53935);
    border-radius: var(--radius-md, 8px);
    padding: var(--space-4, 16px);
    max-width: 480px;
    font-family: var(--font-sans, system-ui);
  }
  
  .error-display.compact {
    padding: var(--space-2, 8px) var(--space-3, 12px);
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    flex-wrap: wrap;
  }
  
  .error-display.recoverable {
    border-color: var(--warning, #ff9800);
  }
  
  .error-header {
    display: flex;
    align-items: center;
    gap: var(--space-2, 8px);
    margin-bottom: var(--space-2, 8px);
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
    font-size: var(--text-sm, 0.875rem);
    color: var(--error, #e53935);
    font-weight: 600;
  }
  
  .recoverable .error-id {
    color: var(--warning, #ff9800);
  }
  
  .dismiss {
    margin-left: auto;
    background: none;
    border: none;
    color: var(--text-secondary, hsl(0 0% 60%));
    cursor: pointer;
    padding: var(--space-1, 4px);
    border-radius: var(--radius-sm, 4px);
    font-size: var(--text-sm, 0.875rem);
    line-height: 1;
    transition: background 0.15s, color 0.15s;
  }
  
  .dismiss:hover {
    background: var(--surface-2, hsl(0 0% 20%));
    color: var(--text-primary, hsl(0 0% 90%));
  }
  
  .error-message {
    color: var(--text-primary, hsl(0 0% 90%));
    margin: 0 0 var(--space-3, 12px);
    line-height: 1.5;
    font-size: var(--text-base, 1rem);
  }
  
  .error-message-inline {
    color: var(--text-primary, hsl(0 0% 90%));
    margin: 0;
    line-height: 1.4;
    font-size: var(--text-sm, 0.875rem);
    flex: 1;
  }
  
  .recovery-hints {
    background: var(--surface-1, hsl(0 0% 15%));
    border-radius: var(--radius-sm, 4px);
    padding: var(--space-3, 12px);
    font-size: var(--text-sm, 0.875rem);
    margin-bottom: var(--space-3, 12px);
  }
  
  .recovery-hints strong {
    color: var(--text-primary, hsl(0 0% 90%));
    display: block;
    margin-bottom: var(--space-2, 8px);
  }
  
  .recovery-hints ol {
    margin: 0;
    padding-left: var(--space-4, 16px);
  }
  
  .recovery-hints li {
    margin: var(--space-1, 4px) 0;
    color: var(--text-secondary, hsl(0 0% 60%));
    line-height: 1.4;
  }
  
  .error-actions {
    display: flex;
    gap: var(--space-2, 8px);
    justify-content: flex-end;
  }
  
  .retry {
    background: var(--error, #e53935);
    color: white;
    border: none;
    padding: var(--space-2, 8px) var(--space-4, 16px);
    border-radius: var(--radius-sm, 4px);
    cursor: pointer;
    font-weight: 500;
    font-size: var(--text-sm, 0.875rem);
    transition: opacity 0.15s, transform 0.1s;
  }
  
  .recoverable .retry {
    background: var(--warning, #ff9800);
    color: var(--surface-1, hsl(0 0% 15%));
  }
  
  .retry:hover {
    opacity: 0.9;
  }
  
  .retry:active {
    transform: scale(0.98);
  }
</style>
