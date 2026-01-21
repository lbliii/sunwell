<!--
  BriefingCard Primitive (RFC-072)
  
  Session orientation widget.
-->
<script lang="ts">
  import type { PrimitiveProps } from './types';
  
  interface Props extends PrimitiveProps {}
  
  let { size }: Props = $props();
</script>

<div class="briefing-card" data-size={size}>
  <div class="briefing-icon">📋</div>
  <div class="briefing-content">
    <span class="briefing-title">Session Briefing</span>
    <span class="briefing-status">No active session</span>
  </div>
</div>

<style>
  .briefing-card {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    padding: var(--spacing-sm) var(--spacing-md);
    display: flex;
    align-items: center;
    gap: var(--spacing-sm);
    border: 1px solid var(--border-subtle);
  }
  
  .briefing-icon {
    font-size: 1.5rem;
  }
  
  .briefing-content {
    display: flex;
    flex-direction: column;
  }
  
  .briefing-title {
    font-size: 0.875rem;
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .briefing-status {
    font-size: 0.75rem;
    color: var(--text-secondary);
  }
</style>
