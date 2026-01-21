<!--
  DataTable Primitive (RFC-072)
  
  Spreadsheet view for data.
-->
<script lang="ts">
  import type { DataPrimitiveProps } from './types';
  
  interface Props extends DataPrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="data-table" data-size={size}>
  <div class="table-header">
    <span>📊 Data Table</span>
  </div>
  <div class="table-content">
    <p class="placeholder">No data loaded</p>
  </div>
</div>

<style>
  .data-table {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .table-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .table-content {
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
