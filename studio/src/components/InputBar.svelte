<!--
  InputBar — Holy Light styled input for goals/prompts (Svelte 5)
  
  Uses soft, opacity-based gold for focus states.
  The glow is subtle warmth, not jarring brightness.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import RisingMotes from './RisingMotes.svelte';
  
  interface Props {
    value?: string;
    placeholder?: string;
    disabled?: boolean;
    autofocus?: boolean;
    showMotes?: boolean;
    loading?: boolean;
    onsubmit?: (value: string) => void;
  }
  
  let { 
    value = $bindable(''), 
    placeholder = 'What would you like to create?', 
    disabled = false, 
    autofocus = false, 
    showMotes = false,
    loading = false,
    onsubmit 
  }: Props = $props();
  
  // Effective disabled state considers loading
  let isDisabled = $derived(disabled || loading);
  
  let inputEl: HTMLInputElement | undefined = $state();
  let focused = $state(false);
  
  // Programmatic autofocus to avoid browser conflicts
  onMount(() => {
    if (autofocus && inputEl) {
      inputEl.focus();
    }
  });
  
  function handleSubmit() {
    if (value.trim() && !isDisabled) {
      onsubmit?.(value.trim());
    }
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
  
  function handleFocus() {
    focused = true;
  }
  
  function handleBlur() {
    focused = false;
  }
  
  export function focus() {
    inputEl?.focus();
  }
</script>

<div class="input-bar" class:disabled={isDisabled} class:focused class:loading>
  <input
    bind:this={inputEl}
    bind:value
    {placeholder}
    disabled={isDisabled}
    onkeydown={handleKeydown}
    onfocus={handleFocus}
    onblur={handleBlur}
    type="text"
    spellcheck="false"
    autocomplete="off"
    aria-label={placeholder}
  />
  <button 
    class="submit-btn" 
    onclick={handleSubmit}
    disabled={isDisabled}
    aria-label={loading ? 'Processing...' : 'Submit'}
    type="button"
  >
    {#if loading}
      <span class="loading-spinner" aria-hidden="true">⟳</span>
    {:else}
      ⏎
    {/if}
  </button>
  
  {#if showMotes}
    <RisingMotes count={5} intensity="subtle" active={focused} />
  {/if}
</div>

<style>
  .input-bar {
    display: flex;
    align-items: center;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: 0 var(--space-4);
    transition: 
      border-color var(--transition-normal), 
      box-shadow var(--transition-normal),
      background var(--transition-normal);
    width: 100%;
    max-width: 600px;
    position: relative;
    overflow: visible; /* Allow motes to float above */
  }
  
  .input-bar:focus-within,
  .input-bar.focused {
    border-color: var(--border-emphasis);
    background: rgba(20, 20, 20, 1);
    box-shadow: 
      0 0 0 1px var(--border-default),
      var(--glow-gold-inset);
  }
  
  .input-bar.disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    padding: var(--space-4) 0;
    min-width: 0;
    position: relative;
    z-index: 2;
  }
  
  input::placeholder {
    color: var(--text-tertiary);
  }
  
  input:disabled {
    cursor: not-allowed;
  }
  
  .submit-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 32px;
    height: 32px;
    margin-left: var(--space-2);
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    border-radius: var(--radius-sm);
    transition: 
      color var(--transition-fast), 
      background var(--transition-fast);
    position: relative;
    z-index: 2;
  }
  
  .submit-btn:hover:not(:disabled) {
    color: var(--text-gold);
    background: var(--ui-gold-10);
  }
  
  .submit-btn:disabled {
    cursor: not-allowed;
  }
  
  .submit-btn:focus-visible {
    outline: 2px solid var(--border-emphasis);
    outline-offset: 2px;
  }
  
  .loading-spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
    color: var(--text-gold);
  }
  
  .input-bar.loading {
    border-color: var(--radiant-gold-30);
  }
  
  @keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
  }
</style>
