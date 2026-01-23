<!--
  Label — Holy Light styled form label (Svelte 5)
  
  Features:
  - Associates with form controls via `for`
  - Required indicator
  - Size variants
-->
<script lang="ts">
  import type { Snippet } from 'svelte';
  
  interface Props {
    for?: string;
    required?: boolean;
    size?: 'sm' | 'md';
    children: Snippet;
  }
  
  let {
    for: htmlFor,
    required = false,
    size = 'md',
    children,
  }: Props = $props();
</script>

<label class="label {size}" for={htmlFor}>
  {@render children()}
  {#if required}
    <span class="required" aria-hidden="true">*</span>
  {/if}
</label>

<style>
  .label {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-weight: 500;
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  /* ═══════════════════════════════════════════════════════════════
     SIZES
     ═══════════════════════════════════════════════════════════════ */
  .sm {
    font-size: var(--text-xs);
  }
  
  .md {
    font-size: var(--text-sm);
  }
  
  /* ═══════════════════════════════════════════════════════════════
     REQUIRED
     ═══════════════════════════════════════════════════════════════ */
  .required {
    color: var(--error);
  }
</style>
