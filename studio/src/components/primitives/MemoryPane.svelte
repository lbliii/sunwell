<!--
  MemoryPane Primitive (RFC-072)
  
  Decisions, patterns, warnings panel.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="memory-pane" data-size={size}>
  <div class="memory-header">
    <span>🧠 Memory</span>
  </div>
  <div class="memory-content">
    <p class="placeholder">No memories yet</p>
  </div>
</div>

<style>
  .memory-pane {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .memory-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .memory-content {
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
