<!--
  Textarea — Holy Light styled multiline text input (Svelte 5)
  
  Features:
  - Label, hint, and error support
  - Auto-resize option
  - Character count
  - Soft gold focus states
-->
<script lang="ts">
  import { uniqueId } from '$lib/a11y';
  
  interface Props {
    value?: string;
    placeholder?: string;
    label?: string;
    hint?: string;
    error?: string;
    rows?: number;
    maxLength?: number;
    showCount?: boolean;
    autoResize?: boolean;
    disabled?: boolean;
    required?: boolean;
    onchange?: (value: string) => void;
    oninput?: (value: string) => void;
  }
  
  let {
    value = $bindable(''),
    placeholder = '',
    label,
    hint,
    error,
    rows = 4,
    maxLength,
    showCount = false,
    autoResize = false,
    disabled = false,
    required = false,
    onchange,
    oninput,
  }: Props = $props();
  
  const textareaId = uniqueId('textarea');
  const hintId = $derived(hint || error ? `${textareaId}-hint` : undefined);
  let textareaEl: HTMLTextAreaElement | undefined = $state();
  
  // Auto-resize logic
  $effect(() => {
    if (autoResize && textareaEl) {
      textareaEl.style.height = 'auto';
      textareaEl.style.height = `${textareaEl.scrollHeight}px`;
    }
  });
  
  function handleInput(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    value = target.value;
    oninput?.(value);
  }
  
  function handleChange(e: Event) {
    const target = e.target as HTMLTextAreaElement;
    value = target.value;
    onchange?.(value);
  }
</script>

<div class="textarea-wrapper" class:has-error={!!error} class:disabled>
  {#if label}
    <label for={textareaId} class="textarea-label">
      {label}
      {#if required}<span class="required" aria-hidden="true">*</span>{/if}
    </label>
  {/if}
  
  <div class="textarea-container">
    <textarea
      bind:this={textareaEl}
      id={textareaId}
      {value}
      {placeholder}
      {rows}
      {disabled}
      {required}
      maxlength={maxLength}
      class="textarea"
      class:auto-resize={autoResize}
      aria-invalid={!!error}
      aria-describedby={hintId}
      oninput={handleInput}
      onchange={handleChange}
    ></textarea>
  </div>
  
  <div class="textarea-footer">
    {#if error}
      <p id={hintId} class="textarea-hint error" role="alert">{error}</p>
    {:else if hint}
      <p id={hintId} class="textarea-hint">{hint}</p>
    {:else}
      <span></span>
    {/if}
    
    {#if showCount}
      <span class="textarea-count" class:near-limit={maxLength && value.length > maxLength * 0.9}>
        {value.length}{#if maxLength}/{maxLength}{/if}
      </span>
    {/if}
  </div>
</div>

<style>
  .textarea-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    width: 100%;
  }
  
  .textarea-wrapper.disabled {
    opacity: 0.5;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     LABEL
     ═══════════════════════════════════════════════════════════════ */
  .textarea-label {
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
     TEXTAREA CONTAINER
     ═══════════════════════════════════════════════════════════════ */
  .textarea-container {
    position: relative;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     TEXTAREA
     ═══════════════════════════════════════════════════════════════ */
  .textarea {
    width: 100%;
    min-height: 100px;
    padding: var(--space-3);
    background: var(--bg-input);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-primary);
    font-family: var(--font-mono);
    font-size: var(--text-base);
    line-height: var(--leading-relaxed);
    resize: vertical;
    transition: 
      border-color var(--transition-fast),
      box-shadow var(--transition-fast);
  }
  
  .textarea.auto-resize {
    resize: none;
    overflow: hidden;
  }
  
  .textarea:hover:not(:disabled) {
    border-color: var(--border-default);
  }
  
  .textarea:focus {
    outline: none;
    border-color: var(--border-emphasis);
    box-shadow: var(--glow-gold-inset);
  }
  
  .textarea:disabled {
    cursor: not-allowed;
    resize: none;
  }
  
  .textarea::placeholder {
    color: var(--text-tertiary);
  }
  
  .has-error .textarea {
    border-color: var(--error);
  }
  
  .has-error .textarea:focus {
    box-shadow: inset 0 0 12px rgba(239, 68, 68, 0.1);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     FOOTER
     ═══════════════════════════════════════════════════════════════ */
  .textarea-footer {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: var(--space-2);
  }
  
  .textarea-hint {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .textarea-hint.error {
    color: var(--error);
  }
  
  .textarea-count {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
  
  .textarea-count.near-limit {
    color: var(--warning);
  }
</style>
