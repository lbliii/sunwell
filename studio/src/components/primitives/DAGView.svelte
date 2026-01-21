<!--
  DAGView Primitive (RFC-072)
  
  Execution plan visualization.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="dag-view" data-size={size}>
  <div class="dag-header">
    <span>🔀 Execution DAG</span>
  </div>
  <div class="dag-content">
    <p class="placeholder">No execution plan</p>
  </div>
</div>

<style>
  .dag-view {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .dag-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .dag-content {
    flex: 1;
    padding: var(--spacing-md);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .placeholder {
    color: var(--text-tertiary);
  }
</style>
