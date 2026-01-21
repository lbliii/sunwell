<!--
  Button — Holy Light styled button variants (Svelte 5)
  
  Primary buttons use soft, pallid gold for the UI.
  Loading states show radiant rising motes for magical effect.
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  import { ButtonVariant, Size } from '$lib/constants';
  import RisingMotes from './RisingMotes.svelte';
  import Spinner from './ui/Spinner.svelte';
  
  interface Props {
    variant?: 'primary' | 'secondary' | 'ghost';
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    loading?: boolean;
    icon?: string | null;
    href?: string | null;
    onclick?: (e: MouseEvent) => void;
    children: Snippet;
  }
  
  let { 
    variant = ButtonVariant.PRIMARY, 
    size = Size.MD, 
    disabled = false, 
    loading = false, 
    icon = null, 
    href = null, 
    onclick,
    children 
  }: Props = $props();
  
  function handleClick(e: MouseEvent) {
    if (!disabled && !loading) {
      onclick?.(e);
    }
  }
</script>

{#if href}
  <a 
    {href}
    class="button {variant} {size}"
    class:disabled
    class:loading
    onclick={handleClick}
    role={disabled ? 'link' : undefined}
    aria-disabled={disabled}
  >
    <span class="button-content">
      {#if loading}
        <Spinner style="dots" speed={80} />
      {:else if icon}
        <span class="icon" aria-hidden="true">{icon}</span>
      {/if}
      {@render children()}
    </span>
    {#if variant === 'primary' && loading}
      <RisingMotes count={6} intensity="subtle" />
    {/if}
  </a>
{:else}
  <button
    class="button {variant} {size}"
    {disabled}
    class:loading
    onclick={handleClick}
    type="button"
    aria-busy={loading}
  >
    <span class="button-content">
      {#if loading}
        <Spinner style="dots" speed={80} />
      {:else if icon}
        <span class="icon" aria-hidden="true">{icon}</span>
      {/if}
      {@render children()}
    </span>
    {#if variant === 'primary' && loading}
      <RisingMotes count={6} intensity="subtle" />
    {/if}
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
    transition: all var(--transition-normal);
    cursor: pointer;
    text-decoration: none;
    position: relative;
    overflow: hidden;
  }
  
  .button-content {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    position: relative;
    z-index: 2;
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
  
  /* ═══════════════════════════════════════════════════════════════
     PRIMARY VARIANT — Soft pallid gold (not jarring)
     ═══════════════════════════════════════════════════════════════ */
  .primary {
    background: var(--gradient-ui-gold);
    color: var(--bg-primary);
    border: 1px solid rgba(201, 162, 39, 0.3);
  }
  
  .primary:hover:not(:disabled) {
    background: linear-gradient(
      135deg,
      rgba(212, 176, 70, 0.95),
      rgba(201, 162, 39, 1)
    );
    box-shadow: var(--glow-gold-subtle);
  }
  
  .primary:active:not(:disabled) {
    background: linear-gradient(
      135deg,
      rgba(168, 137, 42, 0.95),
      rgba(180, 145, 35, 1)
    );
  }
  
  .primary:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.5);
    outline-offset: 2px;
    box-shadow: var(--glow-gold-subtle);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     SECONDARY VARIANT — Subtle border, transparent fill
     ═══════════════════════════════════════════════════════════════ */
  .secondary {
    background: transparent;
    color: var(--text-primary);
    border: 1px solid var(--border-default);
  }
  
  .secondary:hover:not(:disabled) {
    background: rgba(201, 162, 39, 0.08);
    border-color: var(--border-emphasis);
  }
  
  .secondary:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.4);
    outline-offset: 2px;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     GHOST VARIANT — Minimal, text-only feel
     ═══════════════════════════════════════════════════════════════ */
  .ghost {
    background: transparent;
    color: var(--text-secondary);
    border: none;
  }
  
  .ghost:hover:not(:disabled) {
    background: rgba(201, 162, 39, 0.06);
    color: var(--text-gold);
  }
  
  .ghost:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.3);
    outline-offset: 2px;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     STATES
     ═══════════════════════════════════════════════════════════════ */
  .button:disabled,
  .button.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .loading {
    pointer-events: none;
  }
  
  .primary.loading {
    animation: softPulse 2s ease-in-out infinite;
  }
  
  /* Icons */
  .icon {
    font-size: 1.2em;
  }
  
  
  @keyframes softPulse {
    0%, 100% { 
      box-shadow: none;
    }
    50% { 
      box-shadow: var(--glow-gold-subtle);
    }
  }
</style>
