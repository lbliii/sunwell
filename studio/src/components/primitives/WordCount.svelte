<!--
  WordCount Primitive (RFC-072)
  
  Writing stats widget.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="word-count" data-size={size}>
  <span class="count">0</span>
  <span class="label">words</span>
</div>

<style>
  .word-count {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    display: flex;
    align-items: baseline;
    gap: var(--spacing-xs);
  }
  
  .count {
    font-size: 1.25rem;
    font-weight: 600;
    color: var(--gold);
  }
  
  .label {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
</style>
