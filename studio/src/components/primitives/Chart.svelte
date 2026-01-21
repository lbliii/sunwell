<!--
  Chart Primitive (RFC-072)
  
  Data visualizations.
-->
<script lang="ts">
  import type { DataPrimitiveProps } from './types';
  
  interface Props extends DataPrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="chart" data-size={size}>
  <div class="chart-header">
    <span>📈 Chart</span>
  </div>
  <div class="chart-content">
    <p class="placeholder">No chart data</p>
  </div>
</div>

<style>
  .chart {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .chart-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .chart-content {
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
