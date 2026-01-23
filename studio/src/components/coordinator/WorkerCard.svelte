<!--
  WorkerCard — Individual worker status card for ATC view (RFC-100 Phase 4)
  
  Displays worker status, progress, and controls for pause/resume.
-->
<script lang="ts">
  import type { WorkerStatus } from '../../stores/coordinator.svelte';
  import { pauseWorker, resumeWorker } from '../../stores/coordinator.svelte';
  
  interface Props {
    worker: WorkerStatus;
    isSelected?: boolean;
  }
  
  let { worker, isSelected = false }: Props = $props();
  
  let isPaused = $derived(worker.status === 'paused' || worker.status === 'idle');
  let isRunning = $derived(worker.status === 'executing');
  let isFailed = $derived(worker.status === 'failed');
  
  let statusEmoji = $derived(
    isFailed ? '❌' :
    isPaused ? '⏸️' :
    isRunning ? '🟢' :
    worker.status === 'committing' ? '💾' :
    worker.status === 'merging' ? '🔀' :
    '🟡'
  );
  
  let statusLabel = $derived(
    isFailed ? 'Failed' :
    isPaused ? 'Paused' :
    isRunning ? 'Running' :
    worker.status === 'committing' ? 'Committing' :
    worker.status === 'merging' ? 'Merging' :
    worker.status.charAt(0).toUpperCase() + worker.status.slice(1)
  );
  
  function formatProgress(progress: number): string {
    const filled = Math.round(progress * 10);
    return '█'.repeat(filled) + '░'.repeat(10 - filled);
  }
  
  async function handlePauseResume() {
    try {
      if (isPaused) {
        await resumeWorker(worker.id);
      } else {
        await pauseWorker(worker.id);
      }
    } catch (e) {
      console.error('Failed to pause/resume worker:', e);
    }
  }
</script>

<div 
  class="worker-card"
  class:selected={isSelected}
  class:running={isRunning}
  class:paused={isPaused}
  class:failed={isFailed}
>
  <div class="worker-header">
    <span class="worker-id">Worker {worker.id}</span>
    <span class="worker-status">
      <span class="status-emoji">{statusEmoji}</span>
      {statusLabel}
    </span>
  </div>
  
  <div class="worker-goal">
    {worker.goal || 'Waiting for goal...'}
  </div>
  
  {#if isRunning}
    <div class="worker-progress">
      <span class="progress-bar">{formatProgress(worker.progress)}</span>
      <span class="progress-pct">{Math.round(worker.progress * 100)}%</span>
    </div>
  {/if}
  
  <div class="worker-stats">
    <span class="stat">
      <span class="stat-label">Done:</span>
      <span class="stat-value success">{worker.goals_completed}</span>
    </span>
    <span class="stat">
      <span class="stat-label">Failed:</span>
      <span class="stat-value error">{worker.goals_failed}</span>
    </span>
    <span class="stat branch">
      <span class="stat-label">Branch:</span>
      <span class="stat-value">{worker.branch.split('/').pop()}</span>
    </span>
  </div>
  
  <div class="worker-actions">
    <button 
      class="action-btn"
      onclick={handlePauseResume}
      disabled={isFailed}
    >
      {isPaused ? '▶ Resume' : '⏸ Pause'}
    </button>
  </div>
</div>

<style>
  .worker-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 12px;
    transition: all 0.2s ease;
  }
  
  .worker-card:hover {
    border-color: var(--text-tertiary);
    background: var(--bg-tertiary);
  }
  
  .worker-card.selected {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-dim);
  }
  
  .worker-card.running {
    border-color: var(--success);
  }
  
  .worker-card.paused {
    opacity: 0.8;
  }
  
  .worker-card.failed {
    border-color: var(--error);
    background: color-mix(in srgb, var(--error) 5%, var(--bg-secondary));
  }
  
  .worker-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .worker-id {
    font-family: var(--font-mono);
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .worker-status {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: var(--text-secondary);
  }
  
  .status-emoji {
    font-size: 14px;
  }
  
  .worker-goal {
    font-size: 13px;
    color: var(--text-secondary);
    line-height: 1.4;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  
  .worker-progress {
    display: flex;
    align-items: center;
    gap: 8px;
    font-family: var(--font-mono);
    font-size: 11px;
  }
  
  .progress-bar {
    color: var(--success);
    letter-spacing: -1px;
  }
  
  .progress-pct {
    color: var(--text-secondary);
    font-weight: 500;
  }
  
  .worker-stats {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  
  .stat {
    display: flex;
    gap: 4px;
    font-size: 11px;
  }
  
  .stat-label {
    color: var(--text-tertiary);
  }
  
  .stat-value {
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  .stat-value.success {
    color: var(--success);
  }
  
  .stat-value.error {
    color: var(--error);
  }
  
  .stat.branch {
    flex: 1;
    justify-content: flex-end;
  }
  
  .worker-actions {
    display: flex;
    justify-content: flex-end;
    padding-top: 8px;
    border-top: 1px solid var(--border-color);
  }
  
  .action-btn {
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 6px;
    padding: 6px 12px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .action-btn:hover:not(:disabled) {
    background: var(--bg-primary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
</style>
