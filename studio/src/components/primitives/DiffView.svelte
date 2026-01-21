<!--
  DiffView Primitive (RFC-072)
  
  Show code changes side-by-side or unified.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="diff-view" data-size={size}>
  <div class="diff-header">
    <span>📊 Diff View</span>
  </div>
  <div class="diff-content">
    <p class="placeholder">No changes to display</p>
  </div>
</div>

<style>
  .diff-view {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .diff-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .diff-content {
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
