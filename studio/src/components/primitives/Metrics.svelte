<!--
  Metrics Primitive (RFC-072)
  
  Progress/velocity widget.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="metrics" data-size={size}>
  <div class="metric-card">
    <span class="metric-value">0</span>
    <span class="metric-label">Tasks Complete</span>
  </div>
</div>

<style>
  .metrics {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  .metric-card {
    text-align: center;
  }
  
  .metric-value {
    display: block;
    font-size: 2rem;
    font-weight: 600;
    color: var(--gold);
  }
  
  .metric-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
</style>
