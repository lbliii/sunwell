<!--
  Select — Holy Light styled select dropdown (Svelte 5)
  
  Features:
  - Label, hint, and error support
  - Size variants (sm, md, lg)
  - Custom chevron icon
  - Soft gold focus states
-->
<script lang="ts">
  import { uniqueId } from '$lib/a11y';
  
  interface Option {
    value: string;
    label: string;
    disabled?: boolean;
  }
  
  interface Props {
    value?: string;
    options: Option[];
    placeholder?: string;
    label?: string;
    hint?: string;
    error?: string;
    size?: 'sm' | 'md' | 'lg';
    disabled?: boolean;
    required?: boolean;
    onchange?: (value: string) => void;
  }
  
  let {
    value = $bindable(''),
    options,
    placeholder,
    label,
    hint,
    error,
    size = 'md',
    disabled = false,
    required = false,
    onchange,
  }: Props = $props();
  
  const selectId = uniqueId('select');
  const hintId = $derived(hint || error ? `${selectId}-hint` : undefined);
  
  function handleChange(e: Event) {
    const target = e.target as HTMLSelectElement;
    value = target.value;
    onchange?.(value);
  }
</script>

<div class="select-wrapper" class:has-error={!!error} class:disabled>
  {#if label}
    <label for={selectId} class="select-label">
      {label}
      {#if required}<span class="required" aria-hidden="true">*</span>{/if}
    </label>
  {/if}
  
  <div class="select-container {size}">
    <select
      id={selectId}
      {value}
      {disabled}
      {required}
      class="select"
      aria-invalid={!!error}
      aria-describedby={hintId}
      onchange={handleChange}
    >
      {#if placeholder}
        <option value="" disabled selected={!value}>{placeholder}</option>
      {/if}
      {#each options as opt (opt.value)}
        <option value={opt.value} disabled={opt.disabled}>{opt.label}</option>
      {/each}
    </select>
    <span class="select-chevron" aria-hidden="true">▾</span>
  </div>
  
  {#if error}
    <p id={hintId} class="select-hint error" role="alert">{error}</p>
  {:else if hint}
    <p id={hintId} class="select-hint">{hint}</p>
  {/if}
</div>

<style>
  .select-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    width: 100%;
  }
  
  .select-wrapper.disabled {
    opacity: 0.5;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     LABEL
     ═══════════════════════════════════════════════════════════════ */
  .select-label {
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
     SELECT CONTAINER
     ═══════════════════════════════════════════════════════════════ */
  .select-container {
    position: relative;
    display: flex;
    align-items: center;
  }
  
  /* Size variants */
  .select-container.sm .select {
    height: var(--input-height-sm);
    padding: 0 var(--space-6) 0 var(--space-2);
    font-size: var(--text-sm);
  }
  
  .select-container.md .select {
    height: var(--input-height);
    padding: 0 var(--space-8) 0 var(--space-3);
    font-size: var(--text-base);
  }
  
  .select-container.lg .select {
    height: 56px;
    padding: 0 var(--space-10) 0 var(--space-4);
    font-size: var(--text-lg);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     SELECT
     ═══════════════════════════════════════════════════════════════ */
  .select {
    width: 100%;
    appearance: none;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono);
    cursor: pointer;
    transition: 
      border-color var(--transition-fast),
      box-shadow var(--transition-fast);
  }
  
  .select:hover:not(:disabled) {
    border-color: var(--border-default);
  }
  
  .select:focus {
    outline: none;
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-inset);
  }
  
  .select:disabled {
    cursor: not-allowed;
  }
  
  .has-error .select {
    border-color: var(--error);
  }
  
  .has-error .select:focus {
    box-shadow: inset 0 0 12px rgba(239, 68, 68, 0.1);
  }
  
  .select option {
    background: var(--bg-primary);
    color: var(--text-primary);
    padding: var(--space-2);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     CHEVRON
     ═══════════════════════════════════════════════════════════════ */
  .select-chevron {
    position: absolute;
    right: var(--space-3);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    pointer-events: none;
    transition: color var(--transition-fast);
  }
  
  .select-container:focus-within .select-chevron {
    color: var(--text-gold);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     HINT / ERROR
     ═══════════════════════════════════════════════════════════════ */
  .select-hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .select-hint.error {
    color: var(--error);
  }
</style>
