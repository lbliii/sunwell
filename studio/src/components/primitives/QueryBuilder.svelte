<!--
  QueryBuilder Primitive (RFC-072)
  
  Natural language to query interface.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="query-builder" data-size={size}>
  <div class="query-header">
    <span>🔍 Query Builder</span>
  </div>
  <div class="query-content">
    <input type="text" placeholder="Ask about your data..." />
  </div>
</div>

<style>
  .query-builder {
    height: 100%;
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    display: flex;
    flex-direction: column;
  }
  
  .query-header {
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
  }
  
  .query-content {
    flex: 1;
    padding: var(--spacing-md);
  }
  
  .query-content input {
    width: 100%;
    padding: var(--spacing-sm);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    outline: none;
  }
  
  .query-content input:focus {
    border-color: var(--gold);
  }
</style>
