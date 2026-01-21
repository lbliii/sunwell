<!--
  GoalTree Primitive (RFC-072)
  
  Hierarchical goals view.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="goal-tree" data-size={size}>
  <div class="tree-header">
    <span>🎯 Goals</span>
  </div>
  <div class="tree-content">
    <p class="placeholder">No goals defined</p>
  </div>
</div>

<style>
  .goal-tree {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .tree-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .tree-content {
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
