<!--
  ATCView — Air Traffic Control view for multi-agent orchestration (RFC-100 Phase 4)
  
  Unified Execution Control showing:
  - Backlog (goal queue) — RFC-114
  - All worker statuses
  - Progress tracking
  - Conflict detection and resolution
  - Pause/resume controls
-->
<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { 
    coordinatorStore, 
    setProjectPath, 
    startPolling, 
    stopPolling,
    startWorkers,
    type FileConflict
  } from '../../stores/coordinator.svelte';
  import { backlogStore } from '../../stores/backlog.svelte';
  import WorkerCard from './WorkerCard.svelte';
  import ConflictPanel from './ConflictPanel.svelte';
  import { BacklogPanel, EpicProgress } from '../backlog';
  import Chart from '../primitives/Chart.svelte';
  
  interface Props {
    projectPath: string;
  }
  
  let { projectPath }: Props = $props();
  
  let showStartDialog = $state(false);
  let numWorkersInput = $state(4);
  
  onMount(() => {
    setProjectPath(projectPath);
    startPolling(2000);  // Poll every 2 seconds
  });
  
  onDestroy(() => {
    stopPolling();
  });
  
  function formatProgress(progress: number): string {
    return `${Math.round(progress * 100)}%`;
  }
  
  async function handleStartWorkers() {
    try {
      await startWorkers(numWorkersInput);
      showStartDialog = false;
    } catch (e) {
      console.error('Failed to start workers:', e);
    }
  }
  
  interface MergeConflict {
    readonly path: string;
    readonly type: 'content' | 'rename' | 'delete';
    readonly branches: readonly string[];
  }

  function handleConflictResolve(conflict: MergeConflict, resolution: string) {
    console.log('Resolving conflict:', conflict.path, resolution);
    // TODO: Implement resolution via Tauri command
  }
</script>

<div class="atc-view">
  <header class="atc-header">
    <div class="header-left">
      <h1>🛫 Execution Control</h1>
      <span class="project-badge">{projectPath.split('/').pop()}</span>
    </div>
    
    <div class="header-right">
      {#if coordinatorStore.isRunning}
        <div class="status-indicator running">
          <span class="pulse"></span>
          Running
        </div>
      {:else}
        <div class="status-indicator idle">
          Idle
        </div>
      {/if}
      
      <button 
        class="start-btn"
        onclick={() => showStartDialog = true}
        disabled={coordinatorStore.isRunning}
      >
        + Start Workers
      </button>
    </div>
  </header>
  
  <!-- Progress Overview -->
  <section class="progress-overview">
    <div class="progress-card">
      <div class="progress-label">Overall Progress</div>
      <div class="progress-value">{formatProgress(coordinatorStore.totalProgress)}</div>
      <div class="progress-bar-container">
        <div 
          class="progress-bar-fill"
          style="width: {coordinatorStore.totalProgress * 100}%"
        ></div>
      </div>
    </div>
    
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-value success">{coordinatorStore.completedGoals}</div>
        <div class="stat-label">Completed</div>
      </div>
      <div class="stat-card">
        <div class="stat-value error">{coordinatorStore.failedGoals}</div>
        <div class="stat-label">Failed</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{coordinatorStore.activeWorkers.length}</div>
        <div class="stat-label">Active Workers</div>
      </div>
      <div class="stat-card">
        <div class="stat-value">{coordinatorStore.mergedBranches.length}</div>
        <div class="stat-label">Merged</div>
      </div>
    </div>
  </section>
  
  <!-- Epic Progress (RFC-115) -->
  {#if backlogStore.hasActiveEpic}
    <section class="epic-section">
      <EpicProgress />
    </section>
  {/if}
  
  <!-- Backlog (RFC-114) -->
  <section class="backlog-section">
    <BacklogPanel 
      {projectPath}
      onRunGoal={(goal) => console.log('Run goal:', goal.id)}
    />
  </section>
  
  <!-- Conflicts -->
  {#if coordinatorStore.hasConflicts}
    <section class="conflicts-section">
      <ConflictPanel 
        conflicts={coordinatorStore.conflicts}
        onResolve={handleConflictResolve}
      />
    </section>
  {/if}
  
  <!-- Workers Grid -->
  <section class="workers-section">
    <h2>Workers ({coordinatorStore.workers.length})</h2>
    
    {#if coordinatorStore.workers.length === 0}
      <div class="empty-state">
        <p>No workers running.</p>
        <p class="hint">Workers will claim goals from the backlog above.</p>
        <button class="start-btn" onclick={() => showStartDialog = true} disabled={backlogStore.pendingCount === 0}>
          {backlogStore.pendingCount > 0 ? `▶ Start ${numWorkersInput} Workers` : 'Add goals first'}
        </button>
      </div>
    {:else}
      <div class="workers-grid">
        {#each coordinatorStore.workers as worker (worker.id)}
          <WorkerCard {worker} />
        {/each}
      </div>
    {/if}
  </section>
  
  <!-- Start Workers Dialog -->
  {#if showStartDialog}
    <div class="dialog-overlay" role="presentation" onclick={() => showStartDialog = false} onkeydown={(e) => e.key === 'Escape' && (showStartDialog = false)}>
      <div class="dialog" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()} onkeydown={(e) => e.stopPropagation()}>
        <h3>Start Parallel Execution</h3>
        
        <div class="form-group">
          <label for="num-workers">Number of Workers</label>
          <input 
            id="num-workers"
            type="number" 
            min="1" 
            max="8" 
            bind:value={numWorkersInput}
          />
        </div>
        
        <div class="dialog-actions">
          <button class="cancel-btn" onclick={() => showStartDialog = false}>
            Cancel
          </button>
          <button class="confirm-btn" onclick={handleStartWorkers}>
            Start {numWorkersInput} Workers
          </button>
        </div>
      </div>
    </div>
  {/if}
  
  <!-- Loading/Error States -->
  {#if coordinatorStore.isLoading}
    <div class="loading-overlay">
      <div class="spinner"></div>
    </div>
  {/if}
  
  {#if coordinatorStore.error}
    <div class="error-banner">
      ⚠️ {coordinatorStore.error}
    </div>
  {/if}
</div>

<style>
  .atc-view {
    display: flex;
    flex-direction: column;
    gap: 24px;
    padding: 24px;
    height: 100%;
    overflow-y: auto;
    position: relative;
  }
  
  .atc-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .header-left {
    display: flex;
    align-items: center;
    gap: 12px;
  }
  
  .header-left h1 {
    margin: 0;
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .project-badge {
    padding: 4px 12px;
    background: var(--bg-tertiary);
    border-radius: 20px;
    font-size: 12px;
    font-family: var(--font-mono);
    color: var(--text-secondary);
  }
  
  .header-right {
    display: flex;
    align-items: center;
    gap: 16px;
  }
  
  .status-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    font-weight: 500;
  }
  
  .status-indicator.running {
    color: var(--success);
  }
  
  .status-indicator.idle {
    color: var(--text-tertiary);
  }
  
  .pulse {
    width: 8px;
    height: 8px;
    background: var(--success);
    border-radius: 50%;
    animation: pulse 1.5s ease-in-out infinite;
  }
  
  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.5; transform: scale(1.2); }
  }
  
  .start-btn {
    padding: 10px 20px;
    background: var(--accent);
    color: var(--bg-primary);
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .start-btn:hover:not(:disabled) {
    filter: brightness(1.1);
  }
  
  .start-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .progress-overview {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }
  
  .progress-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 20px;
  }
  
  .progress-label {
    font-size: 12px;
    color: var(--text-tertiary);
    margin-bottom: 4px;
  }
  
  .progress-value {
    font-size: 32px;
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 12px;
  }
  
  .progress-bar-container {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
  }
  
  .progress-bar-fill {
    height: 100%;
    background: var(--success);
    border-radius: 4px;
    transition: width 0.3s ease;
  }
  
  .stats-row {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
  }
  
  .stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
    text-align: center;
  }
  
  .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: var(--text-primary);
  }
  
  .stat-value.success {
    color: var(--success);
  }
  
  .stat-value.error {
    color: var(--error);
  }
  
  .stat-label {
    font-size: 12px;
    color: var(--text-tertiary);
    margin-top: 4px;
  }
  
  .backlog-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 12px;
    padding: 16px;
  }

  .conflicts-section {
    margin-bottom: 8px;
  }
  
  .workers-section h2 {
    margin: 0 0 16px;
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .workers-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
    gap: 16px;
  }
  
  .empty-state {
    text-align: center;
    padding: 48px;
    background: var(--bg-secondary);
    border: 1px dashed var(--border-color);
    border-radius: 12px;
  }
  
  .empty-state p {
    color: var(--text-tertiary);
    margin-bottom: 8px;
  }

  .empty-state p.hint {
    font-size: 12px;
    margin-bottom: 16px;
  }
  
  /* Dialog */
  .dialog-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.6);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
  }
  
  .dialog {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 16px;
    padding: 24px;
    min-width: 360px;
  }
  
  .dialog h3 {
    margin: 0 0 20px;
    font-size: 18px;
    color: var(--text-primary);
  }
  
  .form-group {
    margin-bottom: 20px;
  }
  
  .form-group label {
    display: block;
    font-size: 13px;
    color: var(--text-secondary);
    margin-bottom: 8px;
  }
  
  .form-group input {
    width: 100%;
    padding: 10px 12px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    color: var(--text-primary);
  }
  
  .form-group input:focus {
    outline: none;
    border-color: var(--accent);
  }
  
  .dialog-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
  }
  
  .cancel-btn {
    padding: 10px 20px;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    font-size: 14px;
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  .cancel-btn:hover {
    background: var(--bg-secondary);
  }
  
  .confirm-btn {
    padding: 10px 20px;
    background: var(--accent);
    border: none;
    border-radius: 8px;
    font-size: 14px;
    font-weight: 600;
    color: var(--bg-primary);
    cursor: pointer;
  }
  
  .confirm-btn:hover {
    filter: brightness(1.1);
  }
  
  /* Loading/Error */
  .loading-overlay {
    position: absolute;
    inset: 0;
    background: rgba(0, 0, 0, 0.3);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }
  
  .spinner {
    width: 32px;
    height: 32px;
    border: 3px solid var(--border-color);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  .error-banner {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    padding: 12px 20px;
    background: var(--error);
    color: white;
    border-radius: 8px;
    font-size: 13px;
    z-index: 1000;
  }
</style>
