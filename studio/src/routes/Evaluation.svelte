<!--
  Evaluation — Full-Stack Metrics Dashboard (RFC-098)
  
  Standalone route for measuring Sunwell vs single-shot performance.
  Real comparison, real metrics, real transparency.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { fade, fly, scale } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import {
    evaluation,
    runEvaluation,
    resetEvaluation,
    setEvalTask,
    loadEvalTasks,
    loadEvalHistory,
    loadEvalStats,
    type EvalTask,
    type FullStackScore,
  } from '../stores';
  import { goHome } from '../stores/app.svelte';
  
  // Animated improvement counter
  const improvementDisplay = spring(0, { stiffness: 0.05, damping: 0.5 });
  
  // Update improvement animation when complete
  $effect(() => {
    if (evaluation.phase === 'complete' && evaluation.currentRun) {
      improvementDisplay.set(evaluation.improvementPercent);
    }
  });
  
  // Reset animation on reset
  $effect(() => {
    if (evaluation.phase === 'ready') {
      improvementDisplay.set(0, { hard: true });
    }
  });
  
  // Load data on mount (untrack to prevent re-running on state changes)
  $effect(() => {
    untrack(() => {
      if (evaluation.availableTasks.length === 0) loadEvalTasks();
      if (evaluation.history.length === 0) loadEvalHistory();
      if (!evaluation.stats) loadEvalStats();
    });
  });
  
  async function startEvaluation() {
    await runEvaluation();
  }
  
  function formatScore(score: FullStackScore | null): string {
    if (!score) return '—';
    return score.total.toFixed(1);
  }
  
  function scoreColor(score: number): string {
    if (score >= 80) return 'var(--color-success)';
    if (score >= 60) return 'var(--color-warning)';
    return 'var(--color-error)';
  }
  
  // Pre-computed slices to avoid array creation in template
  const recentHistory = $derived(evaluation.history.slice(0, 5));
</script>

<div class="evaluation-route">
  <button class="back-button" onclick={goHome}>
    ← Back
  </button>
  
  <div class="eval-content">
    <!-- Header -->
    <header class="eval-header">
      <h1>
        <span class="header-icon">📊</span>
        Evaluation Framework
      </h1>
      <p class="subtitle">Compare single-shot vs Sunwell — real metrics, real transparency</p>
    </header>
    
    <!-- Ready State -->
    {#if evaluation.phase === 'ready'}
      <div class="eval-ready" in:fade={{ duration: 300 }}>
        <!-- Stats Overview (if available) -->
        {#if evaluation.stats && evaluation.stats.total_runs > 0}
          <div class="stats-overview">
            <div class="stat-card">
              <span class="stat-value">{evaluation.stats.total_runs}</span>
              <span class="stat-label">Total Runs</span>
            </div>
            <div class="stat-card">
              <span class="stat-value" style="color: var(--color-success)">
                +{evaluation.stats.avg_improvement.toFixed(0)}%
              </span>
              <span class="stat-label">Avg Improvement</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{evaluation.stats.sunwell_wins}</span>
              <span class="stat-label">Sunwell Wins</span>
            </div>
            <div class="stat-card">
              <span class="stat-value">{evaluation.stats.single_shot_wins}</span>
              <span class="stat-label">Single-Shot Wins</span>
            </div>
          </div>
        {/if}
        
        <!-- Task Selection -->
        <div class="task-selection">
          <h2>Select Task</h2>
          <div class="task-grid">
            {#each evaluation.availableTasks as evalTask (evalTask.id)}
              <button
                class="task-card"
                class:selected={evaluation.currentTask?.id === evalTask.id}
                onclick={() => setEvalTask(evalTask)}
              >
                <span class="task-name">{evalTask.name}</span>
                <span class="task-prompt">{evalTask.prompt}</span>
              </button>
            {/each}
          </div>
        </div>
        
        <!-- Run Button -->
        <button class="run-cta" onclick={startEvaluation} disabled={!evaluation.currentTask}>
          <span>Run Evaluation</span>
          <span class="run-icon">▶</span>
        </button>
        
        <div class="context-meta">
          <span>Model: {evaluation.currentModel}</span>
          <span class="dot">•</span>
          <span>Task: {evaluation.currentTask?.name ?? 'None selected'}</span>
        </div>
      </div>
    {/if}
    
    <!-- Error State -->
    {#if evaluation.phase === 'error'}
      <div class="eval-error" in:fade={{ duration: 300 }}>
        <div class="error-icon">⚠️</div>
        <h2>Evaluation Failed</h2>
        <p class="error-message">{evaluation.error}</p>
        <button class="action-secondary" onclick={resetEvaluation}>
          Try Again ↻
        </button>
      </div>
    {/if}
    
    <!-- Running State -->
    {#if evaluation.phase !== 'ready' && evaluation.phase !== 'complete' && evaluation.phase !== 'error'}
      <div class="eval-running" in:fade={{ duration: 300 }}>
        <h2>{evaluation.message}</h2>
        
        <div class="progress-bar">
          <div class="progress-fill" style="width: {evaluation.progress}%"></div>
        </div>
        
        <div class="running-grid">
          <!-- Single-Shot Column -->
          <div class="method-column" class:active={evaluation.phase === 'running_single'}>
            <div class="method-header">
              <span class="method-icon">⚫</span>
              <span>Single-Shot</span>
            </div>
            <div class="file-list">
              {#each evaluation.singleShotFiles as file (file)}
                <div class="file-item" in:fly={{ y: 10, duration: 200 }}>
                  📄 {file}
                </div>
              {/each}
              {#if evaluation.singleShotFiles.length === 0 && evaluation.phase === 'running_single'}
                <div class="waiting">Generating...</div>
              {/if}
            </div>
          </div>
          
          <!-- Sunwell Column -->
          <div class="method-column" class:active={evaluation.phase === 'running_sunwell'}>
            <div class="method-header">
              <span class="method-icon">🔮</span>
              <span>Sunwell</span>
            </div>
            <div class="file-list">
              {#each evaluation.sunwellFiles as file (file)}
                <div class="file-item" in:fly={{ y: 10, duration: 200 }}>
                  📄 {file}
                </div>
              {/each}
              {#if evaluation.sunwellFiles.length === 0 && evaluation.phase === 'running_sunwell'}
                <div class="waiting">Generating with Lens + Judge + Resonance...</div>
              {/if}
            </div>
          </div>
        </div>
      </div>
    {/if}
    
    <!-- Complete State -->
    {#if evaluation.phase === 'complete'}
      <div class="eval-complete" in:fade={{ duration: 300 }}>
        <!-- Winner Banner -->
        <div class="winner-banner" class:sunwell-wins={evaluation.sunwellWins}>
          {#if evaluation.sunwellWins}
            <span class="winner-icon">🏆</span>
            <span class="winner-text">Sunwell wins by +{$improvementDisplay.toFixed(0)}%</span>
          {:else}
            <span class="winner-icon">📊</span>
            <span class="winner-text">Single-Shot: {evaluation.currentRun?.improvement_percent.toFixed(0)}% difference</span>
          {/if}
        </div>
        
        <!-- Score Comparison -->
        <div class="score-comparison">
          <div class="score-card">
            <div class="score-header">
              <span class="score-icon">⚫</span>
              <span>Single-Shot</span>
            </div>
            <div class="score-value" style="color: {scoreColor(evaluation.singleShotScore?.total ?? 0)}">
              {formatScore(evaluation.singleShotScore)}
            </div>
            {#if evaluation.singleShotScore}
              <div class="score-breakdown">
                <div class="breakdown-row">
                  <span>Structure</span>
                  <span>{(evaluation.singleShotScore.structure * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Runnable</span>
                  <span>{(evaluation.singleShotScore.runnable * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Features</span>
                  <span>{(evaluation.singleShotScore.features * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Quality</span>
                  <span>{(evaluation.singleShotScore.quality * 100).toFixed(0)}%</span>
                </div>
              </div>
            {/if}
          </div>
          
          <div class="score-vs">VS</div>
          
          <div class="score-card winner">
            <div class="score-header">
              <span class="score-icon">🔮</span>
              <span>Sunwell</span>
            </div>
            <div class="score-value" style="color: {scoreColor(evaluation.sunwellScore?.total ?? 0)}">
              {formatScore(evaluation.sunwellScore)}
            </div>
            {#if evaluation.sunwellScore}
              <div class="score-breakdown">
                <div class="breakdown-row">
                  <span>Structure</span>
                  <span>{(evaluation.sunwellScore.structure * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Runnable</span>
                  <span>{(evaluation.sunwellScore.runnable * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Features</span>
                  <span>{(evaluation.sunwellScore.features * 100).toFixed(0)}%</span>
                </div>
                <div class="breakdown-row">
                  <span>Quality</span>
                  <span>{(evaluation.sunwellScore.quality * 100).toFixed(0)}%</span>
                </div>
              </div>
            {/if}
          </div>
        </div>
        
        <!-- Run Info -->
        {#if evaluation.currentRun}
          <div class="run-info">
            <div class="info-item">
              <span class="info-label">Model</span>
              <span class="info-value">{evaluation.currentRun.model}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Task</span>
              <span class="info-value">{evaluation.currentRun.task_id}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Lens</span>
              <span class="info-value">{evaluation.currentRun.sunwell?.lens_used ?? 'auto'}</span>
            </div>
            <div class="info-item">
              <span class="info-label">Resonance Iterations</span>
              <span class="info-value">{evaluation.currentRun.sunwell?.resonance_iterations ?? 0}</span>
            </div>
          </div>
        {/if}
        
        <button class="action-secondary" onclick={resetEvaluation}>
          Run Another ↻
        </button>
      </div>
    {/if}
    
    <!-- History (always shown at bottom) -->
    {#if evaluation.history.length > 0}
      <div class="history-section">
        <h3>Recent Evaluations</h3>
        <div class="history-list">
          {#each recentHistory as run (run.id)}
            <div class="history-item">
              <span class="history-task">{run.task_id}</span>
              <span class="history-model">{run.model}</span>
              <span class="history-improvement" class:positive={run.improvement_percent > 0}>
                {run.improvement_percent > 0 ? '+' : ''}{run.improvement_percent.toFixed(0)}%
              </span>
            </div>
          {/each}
        </div>
      </div>
    {/if}
  </div>
</div>

<style>
  .evaluation-route {
    min-height: 100vh;
    background: var(--bg-primary);
    position: relative;
    padding: var(--space-6);
  }
  
  .back-button {
    position: fixed;
    top: var(--space-4);
    left: var(--space-4);
    padding: var(--space-2) var(--space-4);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
    z-index: 10;
  }
  
  .back-button:hover {
    color: var(--text-primary);
    border-color: var(--border-default);
  }
  
  .eval-content {
    max-width: 1000px;
    margin: 0 auto;
    padding-top: var(--space-8);
  }
  
  .eval-header {
    text-align: center;
    margin-bottom: var(--space-8);
  }
  
  .eval-header h1 {
    font-size: var(--text-3xl);
    font-weight: 600;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
  }
  
  .header-icon {
    font-size: var(--text-4xl);
  }
  
  .subtitle {
    color: var(--text-secondary);
    margin-top: var(--space-2);
  }
  
  /* Stats Overview */
  .stats-overview {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-4);
    margin-bottom: var(--space-8);
  }
  
  .stat-card {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    text-align: center;
  }
  
  .stat-value {
    font-size: var(--text-2xl);
    font-weight: 700;
    color: var(--text-primary);
    display: block;
  }
  
  .stat-label {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin-top: var(--space-1);
    display: block;
  }
  
  /* Task Selection */
  .task-selection {
    margin-bottom: var(--space-8);
  }
  
  .task-selection h2 {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin-bottom: var(--space-4);
  }
  
  .task-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--space-4);
  }
  
  .task-card {
    background: var(--bg-secondary);
    border: 2px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    text-align: left;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .task-card:hover {
    border-color: var(--border-default);
  }
  
  .task-card.selected {
    border-color: var(--color-primary);
    background: var(--bg-tertiary);
  }
  
  .task-name {
    display: block;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-1);
  }
  
  .task-prompt {
    display: block;
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }
  
  /* Run CTA */
  .run-cta {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-3);
    width: 100%;
    max-width: 300px;
    margin: 0 auto var(--space-6);
    padding: var(--space-4) var(--space-6);
    font-size: var(--text-lg);
    font-weight: 600;
    color: white;
    background: var(--color-primary);
    border: none;
    border-radius: var(--radius-lg);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .run-cta:hover:not(:disabled) {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
  }
  
  .run-cta:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }
  
  .run-icon {
    font-size: var(--text-sm);
  }
  
  .context-meta {
    text-align: center;
    font-size: var(--text-sm);
    color: var(--text-tertiary);
  }
  
  .dot {
    margin: 0 var(--space-2);
  }
  
  /* Error State */
  .eval-error {
    text-align: center;
    padding: var(--space-8);
  }
  
  .error-icon {
    font-size: 4rem;
    margin-bottom: var(--space-4);
  }
  
  .error-message {
    color: var(--color-error);
    margin-bottom: var(--space-6);
  }
  
  .action-secondary {
    padding: var(--space-3) var(--space-6);
    font-size: var(--text-base);
    color: var(--text-secondary);
    background: var(--bg-secondary);
    border: 1px solid var(--border-default);
    border-radius: var(--radius-md);
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .action-secondary:hover {
    color: var(--text-primary);
    border-color: var(--color-primary);
  }
  
  /* Running State */
  .eval-running {
    text-align: center;
    padding: var(--space-8) 0;
  }
  
  .eval-running h2 {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin-bottom: var(--space-6);
  }
  
  .progress-bar {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
    margin-bottom: var(--space-8);
  }
  
  .progress-fill {
    height: 100%;
    background: var(--color-primary);
    border-radius: var(--radius-full);
    transition: width 0.3s ease;
  }
  
  .running-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--space-6);
  }
  
  .method-column {
    background: var(--bg-secondary);
    border: 2px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    opacity: 0.6;
    transition: all var(--transition-fast);
  }
  
  .method-column.active {
    opacity: 1;
    border-color: var(--color-primary);
  }
  
  .method-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-4);
  }
  
  .file-list {
    text-align: left;
    min-height: 100px;
  }
  
  .file-item {
    padding: var(--space-2);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .waiting {
    color: var(--text-tertiary);
    font-style: italic;
    padding: var(--space-4);
  }
  
  /* Complete State */
  .eval-complete {
    text-align: center;
  }
  
  .winner-banner {
    display: inline-flex;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-4) var(--space-8);
    background: var(--bg-secondary);
    border: 2px solid var(--border-default);
    border-radius: var(--radius-lg);
    margin-bottom: var(--space-8);
  }
  
  .winner-banner.sunwell-wins {
    border-color: var(--color-success);
    background: color-mix(in srgb, var(--color-success) 10%, var(--bg-secondary));
  }
  
  .winner-icon {
    font-size: var(--text-2xl);
  }
  
  .winner-text {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  /* Score Comparison */
  .score-comparison {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-6);
    margin-bottom: var(--space-8);
  }
  
  .score-card {
    background: var(--bg-secondary);
    border: 2px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-6);
    min-width: 200px;
  }
  
  .score-card.winner {
    border-color: var(--color-success);
  }
  
  .score-header {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: var(--space-4);
  }
  
  .score-value {
    font-size: 3rem;
    font-weight: 700;
  }
  
  .score-vs {
    font-size: var(--text-xl);
    font-weight: 700;
    color: var(--text-tertiary);
  }
  
  .score-breakdown {
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-subtle);
    text-align: left;
  }
  
  .breakdown-row {
    display: flex;
    justify-content: space-between;
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    padding: var(--space-1) 0;
  }
  
  /* Run Info */
  .run-info {
    display: flex;
    justify-content: center;
    gap: var(--space-8);
    margin-bottom: var(--space-6);
    flex-wrap: wrap;
  }
  
  .info-item {
    text-align: center;
  }
  
  .info-label {
    display: block;
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .info-value {
    display: block;
    font-weight: 500;
    color: var(--text-secondary);
  }
  
  /* History Section */
  .history-section {
    margin-top: var(--space-12);
    padding-top: var(--space-8);
    border-top: 1px solid var(--border-subtle);
  }
  
  .history-section h3 {
    font-size: var(--text-lg);
    color: var(--text-secondary);
    margin-bottom: var(--space-4);
  }
  
  .history-list {
    background: var(--bg-secondary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }
  
  .history-item {
    display: flex;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    border-bottom: 1px solid var(--border-subtle);
  }
  
  .history-item:last-child {
    border-bottom: none;
  }
  
  .history-task {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .history-model {
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .history-improvement {
    font-weight: 600;
    color: var(--text-secondary);
  }
  
  .history-improvement.positive {
    color: var(--color-success);
  }
  
  /* Responsive */
  @media (max-width: 768px) {
    .stats-overview {
      grid-template-columns: repeat(2, 1fr);
    }
    
    .running-grid {
      grid-template-columns: 1fr;
    }
    
    .score-comparison {
      flex-direction: column;
    }
    
    .score-vs {
      transform: rotate(90deg);
    }
  }
</style>
