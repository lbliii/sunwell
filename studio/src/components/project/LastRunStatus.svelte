<!--
  LastRunStatus — RFC-106 last run status display (collapsible)
  
  Shows the status of the last run with resume capability for interrupted runs.
  Enhanced from IdleState.svelte last-run section.
-->
<script lang="ts">
  import type { ProjectStatus } from '$lib/types';
  import Button from '../Button.svelte';
  import { formatRelativeTime } from '$lib/format';
  
  interface Props {
    status: ProjectStatus;
    onResume: () => void;
  }
  
  let { status, onResume }: Props = $props();
  
  const isInterrupted = $derived(status.status === 'interrupted');
  const taskProgress = $derived(
    status.tasks_completed !== null && status.tasks_total !== null
      ? `${status.tasks_completed}/${status.tasks_total} tasks`
      : null
  );
</script>

<details class="last-run" open={isInterrupted}>
  <summary>
    <span class="status-badge" class:interrupted={isInterrupted} class:complete={status.status === 'complete'} class:failed={status.status === 'failed'}>
      {#if isInterrupted}
        <span class="badge-icon">◐</span><span>Interrupted</span>
      {:else if status.status === 'complete'}
        <span class="badge-icon">◆</span><span>Last Run Complete</span>
      {:else if status.status === 'failed'}
        <span class="badge-icon">⊗</span><span>Last Run Failed</span>
      {/if}
    </span>
    {#if status.last_activity}
      <span class="time">{formatRelativeTime(new Date(status.last_activity))}</span>
    {/if}
  </summary>
  
  <div class="last-run-details">
    {#if status.last_goal}
      <p class="last-goal">"{status.last_goal}"</p>
    {/if}
    {#if taskProgress}
      <p class="progress">{taskProgress} completed</p>
    {/if}
    {#if isInterrupted}
      <Button variant="primary" size="sm" onclick={onResume}>Resume</Button>
    {/if}
  </div>
</details>

<style>
  .last-run {
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-color);
  }
  
  .last-run summary {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: var(--space-3);
    cursor: pointer;
    list-style: none;
  }
  
  .last-run summary::-webkit-details-marker {
    display: none;
  }
  
  .status-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .status-badge.interrupted {
    color: var(--warning);
  }
  
  .status-badge.complete {
    color: var(--success);
  }
  
  .status-badge.failed {
    color: var(--error);
  }
  
  .badge-icon {
    font-size: var(--text-base);
  }
  
  .time {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
  
  .last-run-details {
    padding: 0 var(--space-3) var(--space-3);
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .last-goal {
    font-family: var(--font-mono);
    color: var(--text-primary);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  .progress {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
</style>
