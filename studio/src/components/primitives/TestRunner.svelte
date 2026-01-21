<!--
  TestRunner Primitive (RFC-072)
  
  Execute and view test results.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="test-runner" data-size={size}>
  <div class="test-header">
    <span class="test-title">🧪 Test Runner</span>
    <button class="run-btn">Run All</button>
  </div>
  <div class="test-content">
    <p class="placeholder">No tests running</p>
  </div>
</div>

<style>
  .test-runner {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .test-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .test-title {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .run-btn {
    padding: 4px 12px;
    background: var(--gold);
    color: var(--obsidian);
    border: none;
    border-radius: var(--radius-sm);
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 500;
  }
  
  .test-content {
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
