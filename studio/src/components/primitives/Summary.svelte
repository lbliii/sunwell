<!--
  Summary Primitive (RFC-072)
  
  AI-generated insights widget.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="summary" data-size={size}>
  <span class="summary-icon">💡</span>
  <span class="summary-text">No insights available</span>
</div>

<style>
  .summary {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
  }
  
  .summary-icon {
    font-size: 1.25rem;
  }
  
  .summary-text {
    font-size: 0.875rem;
    color: var(--text-secondary);
  }
</style>
