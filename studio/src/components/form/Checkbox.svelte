<!--
  Checkbox — Holy Light styled checkbox (Svelte 5)
  
  Features:
  - Custom styled checkbox with gold check
  - Label and hint support
  - Indeterminate state
-->
<script lang="ts">
  import { uniqueId } from '$lib/a11y';
  
  interface Props {
    checked?: boolean;
    indeterminate?: boolean;
    label?: string;
    hint?: string;
    disabled?: boolean;
    onchange?: (checked: boolean) => void;
  }
  
  let {
    checked = $bindable(false),
    indeterminate = false,
    label,
    hint,
    disabled = false,
    onchange,
  }: Props = $props();
  
  const checkboxId = uniqueId('checkbox');
  let inputEl: HTMLInputElement | undefined = $state();
  
  // Sync indeterminate state (can't be set via attribute)
  $effect(() => {
    if (inputEl) {
      inputEl.indeterminate = indeterminate;
    }
  });
  
  function handleChange(e: Event) {
    const target = e.target as HTMLInputElement;
    checked = target.checked;
    onchange?.(checked);
  }
</script>

<div class="checkbox-wrapper" class:disabled>
  <label class="checkbox-label" for={checkboxId}>
    <input
      bind:this={inputEl}
      id={checkboxId}
      type="checkbox"
      {checked}
      {disabled}
      class="checkbox-input"
      onchange={handleChange}
    />
    <span class="checkbox-box" aria-hidden="true">
      {#if checked}
        <span class="checkbox-check">✓</span>
      {:else if indeterminate}
        <span class="checkbox-indeterminate">−</span>
      {/if}
    </span>
    {#if label}
      <span class="checkbox-text">{label}</span>
    {/if}
  </label>
  {#if hint}
    <p class="checkbox-hint">{hint}</p>
  {/if}
</div>

<style>
  .checkbox-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .checkbox-wrapper.disabled {
    opacity: 0.5;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     LABEL
     ═══════════════════════════════════════════════════════════════ */
  .checkbox-label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    cursor: pointer;
    user-select: none;
  }
  
  .disabled .checkbox-label {
    cursor: not-allowed;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     HIDDEN INPUT
     ═══════════════════════════════════════════════════════════════ */
  .checkbox-input {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
    pointer-events: none;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     CUSTOM BOX
     ═══════════════════════════════════════════════════════════════ */
  .checkbox-box {
    width: 18px;
    height: 18px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    transition: 
      border-color var(--transition-fast),
      background var(--transition-fast),
      box-shadow var(--transition-fast);
    flex-shrink: 0;
  }
  
  .checkbox-label:hover .checkbox-box {
    border-color: var(--border-default);
  }
  
  .checkbox-input:focus-visible + .checkbox-box {
    border-color: var(--border-emphasis);
    box-shadow: 0 0 0 2px var(--border-emphasis);
  }
  
  .checkbox-input:checked + .checkbox-box {
    background: var(--ui-gold);
    border-color: var(--ui-gold);
  }
  
  .checkbox-input:checked:focus-visible + .checkbox-box {
    box-shadow: 0 0 0 2px var(--border-emphasis);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     CHECK MARK
     ═══════════════════════════════════════════════════════════════ */
  .checkbox-check,
  .checkbox-indeterminate {
    color: var(--bg-primary);
    font-size: 12px;
    font-weight: 700;
    line-height: 1;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     TEXT & HINT
     ═══════════════════════════════════════════════════════════════ */
  .checkbox-text {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .checkbox-hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
    padding-left: calc(18px + var(--space-2));
  }
</style>
