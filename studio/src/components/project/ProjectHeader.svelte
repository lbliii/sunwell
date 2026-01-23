<!--
  ProjectHeader — Header with back navigation (Svelte 5)
  RFC-064: Shows active lens badge
  RFC-108: Shows codebase index status
-->
<script lang="ts">
  import { project } from '../../stores/project.svelte';
  import { goHome } from '../../stores/app.svelte';
  import { resetAgent } from '../../stores/agent.svelte';
  import LensBadge from '../LensBadge.svelte';
  import IndexStatus from '../IndexStatus.svelte';
  
  function handleBack() {
    resetAgent();
    goHome();
  }
</script>

<header class="header">
  <button class="back-btn" onclick={handleBack} aria-label="Go back to home">
    ← {project.current?.name ?? 'Project'}
    {#if project.current?.id}
      <span class="header-id">#{project.current.id.slice(0, 8)}</span>
    {/if}
  </button>
  <div class="header-right">
    <IndexStatus />
    <LensBadge size="sm" />
  </div>
</header>

<style>
  .header {
    margin-bottom: var(--space-4);
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
  .back-btn {
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    padding: var(--space-1) 0;
    background: transparent;
    border: none;
    cursor: pointer;
    transition: color var(--transition-fast);
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .back-btn:hover { color: var(--text-primary); }
  .back-btn:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
  .header-id { font-size: var(--text-xs); color: var(--text-tertiary); opacity: 0.7; }
  .header-right {
    display: flex;
    align-items: center;
    gap: var(--space-3);
  }
</style>
