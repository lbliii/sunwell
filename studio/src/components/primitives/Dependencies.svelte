<!--
  Dependencies Primitive (RFC-072)
  
  Package/import visualization.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="dependencies" data-size={size}>
  <div class="deps-header">
    <span>📦 Dependencies</span>
  </div>
  <div class="deps-content">
    <p class="placeholder">No dependencies loaded</p>
  </div>
</div>

<style>
  .dependencies {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .deps-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .deps-content {
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
