<!--
  ProjectStats — Summary statistics for projects (RFC-096)
-->
<script lang="ts">
  import { getProjectStats } from '../../stores/projectManager.svelte';
  
  const stats = $derived(getProjectStats());
</script>

<div class="project-stats">
  <span class="stat total">{stats.total} total</span>
  {#if stats.active > 0}
    <span class="stat active">• {stats.active} active</span>
  {/if}
  {#if stats.interrupted > 0}
    <span class="stat interrupted">• {stats.interrupted} paused</span>
  {/if}
</div>

<style>
  .project-stats {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .stat.active {
    color: var(--success);
  }
  
  .stat.interrupted {
    color: var(--warning);
  }
</style>
