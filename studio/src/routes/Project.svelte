<!--
  Project — Working screen
  
  Shows goal, progress, and done state with TRY IT button.
  Matches the RFC mockups for working/done states.
-->
<script lang="ts">
  import Progress from '../components/Progress.svelte';
  import Button from '../components/Button.svelte';
  import { goHome, goToPreview } from '../stores/app';
  import { currentProject } from '../stores/project';
  import { 
    agentState, 
    isRunning, 
    isDone, 
    hasError,
    progress,
    duration,
    completedTasks,
    stopAgent,
    resetAgent
  } from '../stores/agent';
  
  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  }
  
  function handleBack() {
    resetAgent();
    goHome();
  }
  
  function handleTryIt() {
    goToPreview();
  }
  
  function handleStop() {
    stopAgent();
  }
</script>

<div class="project">
  <!-- Header -->
  <header class="header">
    <button class="back-btn" on:click={handleBack}>← {$currentProject?.name ?? 'Project'}</button>
  </header>
  
  <!-- Goal -->
  <div class="goal-section">
    <span class="goal-prompt">&gt;</span>
    <span class="goal-text">{$agentState.goal}</span>
  </div>
  
  <hr class="divider" />
  
  <!-- Content -->
  <main class="content">
    {#if $isRunning}
      <!-- Working State -->
      <div class="working animate-fadeIn">
        <div class="status-header">
          <span class="status-icon animate-pulse">⚡</span>
          <span class="status-text">
            {$agentState.status === 'planning' ? 'Planning' : 'Building'}
          </span>
        </div>
        
        <Progress 
          tasks={$agentState.tasks}
          currentIndex={$agentState.currentTaskIndex}
        />
        
        <div class="working-footer">
          <span class="working-progress">
            {$completedTasks}/{$agentState.totalTasks} tasks
          </span>
          <span class="working-time">{formatDuration($duration)}</span>
        </div>
        
        <div class="actions">
          <Button variant="ghost" size="sm" on:click={handleStop}>
            Stop
          </Button>
        </div>
      </div>
      
    {:else if $isDone}
      <!-- Done State -->
      <div class="done animate-fadeIn">
        <div class="done-header">
          <span class="done-icon">✓</span>
          <span class="done-text">Done</span>
          <span class="done-stats">
            {$agentState.tasks.length} tasks · {formatDuration($duration)}
          </span>
        </div>
        
        <div class="try-it-section">
          <Button variant="primary" size="lg" icon="▶" on:click={handleTryIt}>
            TRY IT
          </Button>
        </div>
        
        <nav class="done-nav">
          <button class="nav-link">files</button>
          <span class="nav-sep">·</span>
          <button class="nav-link">terminal</button>
          <span class="nav-sep">·</span>
          <button class="nav-link">edit</button>
          <span class="nav-sep">·</span>
          <button class="nav-link">rebuild</button>
        </nav>
      </div>
      
    {:else if $hasError}
      <!-- Error State -->
      <div class="error animate-fadeIn">
        <div class="error-header">
          <span class="error-icon">✗</span>
          <span class="error-text">Error</span>
        </div>
        
        <p class="error-message">{$agentState.error}</p>
        
        <div class="actions">
          <Button variant="secondary" on:click={handleBack}>
            Go Back
          </Button>
        </div>
      </div>
      
    {:else}
      <!-- Idle State (shouldn't normally show) -->
      <div class="idle">
        <p>Ready to start</p>
      </div>
    {/if}
  </main>
</div>

<style>
  .project {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-6);
  }
  
  /* Header */
  .header {
    margin-bottom: var(--space-4);
  }
  
  .back-btn {
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    padding: var(--space-1) 0;
    transition: color var(--transition-fast);
  }
  
  .back-btn:hover {
    color: var(--text-primary);
  }
  
  /* Goal */
  .goal-section {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-base);
    margin-bottom: var(--space-4);
  }
  
  .goal-prompt {
    color: var(--text-tertiary);
  }
  
  .goal-text {
    color: var(--text-primary);
  }
  
  .divider {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: var(--space-4) 0;
  }
  
  /* Content */
  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  /* Working State */
  .working {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  
  .status-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-lg);
  }
  
  .status-icon {
    font-size: var(--text-xl);
  }
  
  .status-text {
    font-weight: 500;
  }
  
  .working-footer {
    display: flex;
    justify-content: space-between;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    margin-top: var(--space-4);
  }
  
  /* Done State */
  .done {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
  }
  
  .done-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
  }
  
  .done-icon {
    color: var(--success);
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  .done-text {
    font-size: var(--text-lg);
    font-weight: 500;
  }
  
  .done-stats {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .try-it-section {
    margin: var(--space-8) 0;
  }
  
  .done-nav {
    display: flex;
    gap: var(--space-2);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .nav-link {
    color: var(--text-secondary);
    transition: color var(--transition-fast);
  }
  
  .nav-link:hover {
    color: var(--text-primary);
  }
  
  .nav-sep {
    color: var(--text-tertiary);
  }
  
  /* Error State */
  .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    flex: 1;
  }
  
  .error-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .error-icon {
    color: var(--error);
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  .error-text {
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--error);
  }
  
  .error-message {
    color: var(--text-secondary);
    text-align: center;
    max-width: 400px;
  }
  
  /* Actions */
  .actions {
    margin-top: var(--space-4);
    display: flex;
    justify-content: center;
    gap: var(--space-4);
  }
  
  /* Idle */
  .idle {
    flex: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-tertiary);
  }
</style>
