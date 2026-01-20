<!--
  InputBar — The main input for goals/prompts
  
  Minimal, focused input with subtle border and glow on focus.
  Used on home screen and project screens.
-->
<script lang="ts">
  import { createEventDispatcher } from 'svelte';
  
  export let value = '';
  export let placeholder = 'What would you like to create?';
  export let disabled = false;
  export let autofocus = false;
  
  const dispatch = createEventDispatcher<{ submit: string }>();
  
  let inputEl: HTMLInputElement;
  
  function handleSubmit() {
    if (value.trim() && !disabled) {
      dispatch('submit', value.trim());
    }
  }
  
  function handleKeydown(e: KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }
  
  export function focus() {
    inputEl?.focus();
  }
</script>

<div class="input-bar" class:disabled>
  <input
    bind:this={inputEl}
    bind:value
    {placeholder}
    {disabled}
    autofocus={autofocus}
    on:keydown={handleKeydown}
    type="text"
    spellcheck="false"
    autocomplete="off"
  />
  <button 
    class="submit-btn" 
    on:click={handleSubmit}
    {disabled}
    aria-label="Submit"
  >
    ⏎
  </button>
</div>

<style>
  .input-bar {
    display: flex;
    align-items: center;
    background: var(--bg-input);
    border: var(--border-width) solid var(--border-color);
    border-radius: var(--radius-md);
    padding: 0 var(--space-4);
    transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
    width: 100%;
    max-width: 600px;
  }
  
  .input-bar:focus-within {
    border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(245, 245, 245, 0.1);
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
    transition: color var(--transition-fast), background var(--transition-fast);
  }
  
  .submit-btn:hover:not(:disabled) {
    color: var(--text-primary);
    background: var(--bg-tertiary);
  }
  
  .submit-btn:disabled {
    cursor: not-allowed;
  }
</style>
