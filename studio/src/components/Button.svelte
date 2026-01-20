<!--
  Button — Primary and secondary button variants
  
  Follows the design system with high contrast on primary,
  subtle styling on secondary.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let variant: 'primary' | 'secondary' | 'ghost' = 'primary';
  export let size: 'sm' | 'md' | 'lg' = 'md';
  export let disabled = false;
  export let loading = false;
  export let icon: string | null = null;
  export let href: string | null = null;
  
  const dispatch = createEventDispatcher<{ click: MouseEvent }>();
  
  function handleClick(e: MouseEvent) {
    if (!disabled && !loading) {
      dispatch('click', e);
    }
  }
</script>

{#if href}
  <a 
    {href}
    class="button {variant} {size}"
    class:disabled
    class:loading
    on:click={handleClick}
  >
    {#if loading}
      <span class="spinner">⟳</span>
    {:else if icon}
      <span class="icon">{icon}</span>
    {/if}
    <slot />
  </a>
{:else}
  <button
    class="button {variant} {size}"
    {disabled}
    class:loading
    on:click={handleClick}
    type="button"
  >
    {#if loading}
      <span class="spinner">⟳</span>
    {:else if icon}
      <span class="icon">{icon}</span>
    {/if}
    <slot />
  </button>
{/if}

<style>
  .button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-family: var(--font-mono);
    font-weight: 500;
    border-radius: var(--radius-md);
    transition: all var(--transition-fast);
    cursor: pointer;
    text-decoration: none;
  }
  
  /* Sizes */
  .sm {
    height: var(--button-height-sm);
    padding: 0 var(--space-3);
    font-size: var(--text-sm);
  }
  
  .md {
    height: var(--button-height);
    padding: 0 var(--space-6);
    font-size: var(--text-base);
  }
  
  .lg {
    height: 56px;
    padding: 0 var(--space-8);
    font-size: var(--text-lg);
    min-width: 180px;
  }
  
  /* Variants */
  .primary {
    background: var(--accent);
    color: var(--text-inverse);
    border: none;
  }
  
  .primary:hover:not(:disabled) {
    background: #fff;
    box-shadow: var(--shadow-glow);
  }
  
  .secondary {
    background: var(--bg-secondary);
    color: var(--text-primary);
    border: var(--border-width) solid var(--border-color);
  }
  
  .secondary:hover:not(:disabled) {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
  }
  
  .ghost {
    background: transparent;
    color: var(--text-secondary);
    border: none;
  }
  
  .ghost:hover:not(:disabled) {
    background: var(--bg-tertiary);
    color: var(--text-primary);
  }
  
  /* States */
  .button:disabled,
  .button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .loading {
    pointer-events: none;
  }
  
  /* Icons */
  .icon {
    font-size: 1.2em;
  }
  
  .spinner {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
