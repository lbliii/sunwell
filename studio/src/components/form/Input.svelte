<!--
  Input — Holy Light styled text input (Svelte 5)
  
  Features:
  - Label, hint, and error support
  - Size variants (sm, md, lg)
  - Icon support (leading/trailing)
  - Soft gold focus states
-->
<script lang="ts">
  import { uniqueId } from '$lib/a11y';
  
  interface Props {
    type?: 'text' | 'email' | 'password' | 'search' | 'url' | 'tel' | 'number';
    value?: string;
    placeholder?: string;
    label?: string;
    hint?: string;
    error?: string;
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    required?: boolean;
    leadingIcon?: string;
    trailingIcon?: string;
    onchange?: (value: string) => void;
    oninput?: (value: string) => void;
  }
  
  let {
    type = 'text',
    value = $bindable(''),
    placeholder = '',
    label,
    hint,
    error,
    size = 'md',
    disabled = false,
    required = false,
    leadingIcon,
    trailingIcon,
    onchange,
    oninput,
  }: Props = $props();
  
  const inputId = uniqueId('input');
  const hintId = $derived(hint || error ? `${inputId}-hint` : undefined);
  
  function handleInput(e: Event) {
    const target = e.target as HTMLInputElement;
    value = target.value;
    oninput?.(value);
  }
  
  function handleChange(e: Event) {
    const target = e.target as HTMLInputElement;
    value = target.value;
    onchange?.(value);
  }
</script>

<div class="input-wrapper" class:has-error={!!error} class:disabled>
  {#if label}
    <label for={inputId} class="input-label">
      {label}
      {#if required}<span class="required" aria-hidden="true">*</span>{/if}
    </label>
  {/if}
  
  <div class="input-container {size}">
    {#if leadingIcon}
      <span class="input-icon leading" aria-hidden="true">{leadingIcon}</span>
    {/if}
    
    <input
      id={inputId}
      {type}
      {value}
      {placeholder}
      {disabled}
      {required}
      class="input"
      class:has-leading={!!leadingIcon}
      class:has-trailing={!!trailingIcon}
      aria-invalid={!!error}
      aria-describedby={hintId}
      oninput={handleInput}
      onchange={handleChange}
    />
    
    {#if trailingIcon}
      <span class="input-icon trailing" aria-hidden="true">{trailingIcon}</span>
    {/if}
  </div>
  
  {#if error}
    <p id={hintId} class="input-hint error" role="alert">{error}</p>
  {:else if hint}
    <p id={hintId} class="input-hint">{hint}</p>
  {/if}
</div>

<style>
  .input-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    width: 100%;
  }
  
  .input-wrapper.disabled {
    opacity: 0.5;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     LABEL
     ═══════════════════════════════════════════════════════════════ */
  .input-label {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .required {
    color: var(--error);
    margin-left: var(--space-1);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     INPUT CONTAINER
     ═══════════════════════════════════════════════════════════════ */
  .input-container {
    position: relative;
    display: flex;
    align-items: center;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    transition: 
      border-color var(--transition-fast),
      box-shadow var(--transition-fast);
  }
  
  .input-container:focus-within {
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-inset);
  }
  
  .has-error .input-container {
    border-color: var(--error);
  }
  
  .has-error .input-container:focus-within {
    box-shadow: inset 0 0 12px rgba(239, 68, 68, 0.1);
  }
  
  /* Size variants */
  .input-container.sm {
    height: var(--input-height-sm);
    padding: 0 var(--space-2);
  }
  
  .input-container.md {
    height: var(--input-height);
    padding: 0 var(--space-3);
  }
  
  .input-container.lg {
    height: 56px;
    padding: 0 var(--space-4);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     INPUT
     ═══════════════════════════════════════════════════════════════ */
  .input {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    min-width: 0;
  }
  
  .sm .input {
    font-size: var(--text-sm);
  }
  
  .lg .input {
    font-size: var(--text-lg);
  }
  
  .input::placeholder {
    color: var(--text-tertiary);
  }
  
  .input:disabled {
    cursor: not-allowed;
  }
  
  .input.has-leading {
    padding-left: var(--space-2);
  }
  
  .input.has-trailing {
    padding-right: var(--space-2);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     ICONS
     ═══════════════════════════════════════════════════════════════ */
  .input-icon {
    color: var(--text-tertiary);
    font-size: var(--text-base);
    flex-shrink: 0;
  }
  
  .input-container:focus-within .input-icon {
    color: var(--text-gold);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     HINT / ERROR
     ═══════════════════════════════════════════════════════════════ */
  .input-hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .input-hint.error {
    color: var(--error);
  }
</style>
