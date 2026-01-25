<!--
  ProjectHeader — Header with back navigation (Svelte 5)
  RFC-064: Shows active lens badge
  RFC-108: Shows codebase index status
  RFC-140: Shows workspace switcher
-->
<script lang="ts">
  import { project } from '../../stores/project.svelte';
  import { goHome } from '../../stores/app.svelte';
  import { resetAgent } from '../../stores/agent.svelte';
  import { workspaceManager, switchWorkspace } from '../../stores/workspaceManager.svelte';
  import LensBadge from '../LensBadge.svelte';
  import IndexStatus from '../IndexStatus.svelte';
  import { WorkspaceStatusBadge } from '../workspace';
  
  function handleBack() {
    resetAgent();
    goHome();
  }

  async function handleWorkspaceSwitch(workspaceId: string) {
    await switchWorkspace(workspaceId);
    // Reload project if path changed
    if (project.current?.path) {
      // Trigger project reload
      window.location.reload();
    }
  }
</script>

<header class="header">
  <div class="header-left">
    <button class="back-btn" onclick={handleBack} aria-label="Go back to home">
      ← {project.current?.name ?? 'Project'}
      {#if project.current?.id}
        <span class="header-id">#{project.current.id.slice(0, 8)}</span>
      {/if}
    </button>
    <WorkspaceStatusBadge onSwitch={handleWorkspaceSwitch} />
  </div>
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
  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-3);
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
