<!--
  TaskList Primitive (RFC-072)
  
  Linear task list for today/priority tasks.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="task-list" data-size={size}>
  <div class="list-header">
    <span>✅ Tasks</span>
  </div>
  <div class="list-content">
    <p class="placeholder">No tasks</p>
  </div>
</div>

<style>
  .task-list {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .list-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .list-content {
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
