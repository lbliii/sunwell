<!--
  ConvergenceProgress — RFC-123 Convergence Loop visualization
  
  Displays the self-stabilizing code generation loop progress with
  animated gate checks and iteration tracking. Shows status badges
  for running/stable/escalated states.
  
  Data contract:
  - Consumes real events via observatory.convergence
  - Shows empty state when no convergence data
-->
<script lang="ts">
  import { fade, fly, scale } from 'svelte/transition';
  import { spring } from 'svelte/motion';
  import EmptyState from './EmptyState.svelte';
  import { observatory, type ConvergenceGate } from '../../stores';
  import Spinner from '../ui/Spinner.svelte';
  
  // Reactive state from observatory
  const convergence = $derived(observatory.convergence);
  const hasData = $derived(observatory.hasConvergence);
  const isActive = $derived(convergence.isActive);
  
  // Build gate result lookup map for O(1) access
  const latestGateMap = $derived.by(() => {
    const latestIter = convergence.iterations[convergence.iterations.length - 1];
    if (!latestIter) return new Map<string, ConvergenceGate>();
    return new Map(latestIter.gates.map(g => [g.name, g]));
  });
  
  // Progress bar spring animation
  const progressSpring = spring(0, { stiffness: 0.1, damping: 0.5 });
  $effect(() => {
    const progress = convergence.iterations.length / Math.max(convergence.maxIterations, 1);
    progressSpring.set(progress * 100);
  });
  
  // Status badge helper
  function getStatusBadge(status: string): { text: string; class: string; icon: string } {
    switch (status) {
      case 'running':
        return { text: 'Running', class: 'running', icon: '🔄' };
      case 'stable':
        return { text: 'Stable', class: 'stable', icon: '✓' };
      case 'escalated':
        return { text: 'Escalated', class: 'escalated', icon: '⚠' };
      case 'timeout':
        return { text: 'Timeout', class: 'timeout', icon: '⏱' };
      case 'stuck':
        return { text: 'Stuck', class: 'stuck', icon: '🔒' };
      default:
        return { text: 'Idle', class: 'idle', icon: '○' };
    }
  }
  
  // Gate status helper  
  function getGateIcon(gate: ConvergenceGate): string {
    return gate.passed ? '✓' : '✗';
  }
  
  const statusBadge = $derived(getStatusBadge(convergence.status));
</script>

{#if !hasData}
  <EmptyState
    icon="🔄"
    title="No convergence data"
    message="Run a goal with --converge to enable self-stabilizing code generation and see the loop progress here."
  />
{:else}
<div class="convergence-panel" in:fade={{ duration: 300 }}>
  <div class="panel-header">
    <h2>
      <span class="header-icon">🔄</span>
      Convergence Loop
    </h2>
    
    <div class="status-badges">
      <span class="badge {statusBadge.class}" in:scale={{ duration: 200 }}>
        {#if isActive}
          <Spinner style="moon" speed={100} />
        {:else}
          <span class="badge-icon">{statusBadge.icon}</span>
        {/if}
        {statusBadge.text}
      </span>
      
      <span class="badge iteration">
        Iteration {convergence.currentIteration}/{convergence.maxIterations}
      </span>
    </div>
  </div>
  
  <!-- Overall progress bar -->
  <div class="progress-container">
    <div class="progress-bar">
      <div 
        class="progress-fill {convergence.status}"
        style="width: {$progressSpring}%"
      >
        {#if isActive}
          <div class="shimmer"></div>
        {/if}
      </div>
    </div>
    <span class="progress-label">
      {convergence.iterations.length} / {convergence.maxIterations} iterations
    </span>
  </div>
  
  <!-- Gates overview -->
  <div class="gates-overview">
    <h3>Gates</h3>
    <div class="gates-list">
      {#each convergence.enabledGates as gate (gate)}
        {@const gateResult = latestGateMap.get(gate)}
        <div 
          class="gate-chip"
          class:passed={gateResult?.passed}
          class:failed={gateResult && !gateResult.passed}
          class:pending={!gateResult}
        >
          <span class="gate-name">{gate}</span>
          {#if gateResult}
            <span class="gate-status">
              {gateResult.passed ? '✓' : `${gateResult.errorCount} errors`}
            </span>
          {:else}
            <span class="gate-status">pending</span>
          {/if}
        </div>
      {/each}
    </div>
  </div>
  
  <!-- Iteration timeline -->
  <div class="iterations-timeline">
    <h3>Iterations</h3>
    <div class="iterations-list">
      {#each convergence.iterations as iter, i (iter.iteration)}
        <div 
          class="iteration-row"
          class:passed={iter.allPassed}
          class:failed={!iter.allPassed}
          in:fly={{ y: 20, delay: i * 50, duration: 200 }}
        >
          <div class="iteration-header">
            <span class="iteration-num">#{iter.iteration}</span>
            <span class="iteration-status">
              {#if iter.allPassed}
                <span class="status-icon passed">✓</span>
                All gates pass
              {:else}
                <span class="status-icon failed">✗</span>
                {iter.totalErrors} error{iter.totalErrors !== 1 ? 's' : ''}
              {/if}
            </span>
          </div>
          
          <div class="iteration-gates">
            {#each iter.gates as gate (gate.name)}
              <span 
                class="gate-result"
                class:passed={gate.passed}
                class:failed={!gate.passed}
                title={gate.passed ? 'Passed' : `${gate.errorCount} errors`}
              >
                {gate.name}
                <span class="gate-icon">{getGateIcon(gate)}</span>
                {#if !gate.passed}
                  <span class="error-count">({gate.errorCount})</span>
                {/if}
              </span>
            {/each}
          </div>
        </div>
      {:else}
        <div class="no-iterations">
          {#if isActive}
            <Spinner style="moon" speed={100} />
            <span>Starting convergence loop...</span>
          {:else}
            <span>No iterations yet</span>
          {/if}
        </div>
      {/each}
    </div>
  </div>
  
  <!-- Final status message -->
  {#if convergence.status === 'stable'}
    <div class="success-message" in:scale={{ duration: 300 }}>
      <span class="success-icon">✅</span>
      All gates pass after {convergence.iterations.length} iteration{convergence.iterations.length !== 1 ? 's' : ''}
      {#if convergence.durationMs}
        <span class="duration">({Math.round(convergence.durationMs / 1000)}s)</span>
      {/if}
    </div>
  {:else if convergence.status === 'escalated'}
    <div class="escalated-message" in:scale={{ duration: 300 }}>
      <span class="escalated-icon">⚠️</span>
      Escalated to human after {convergence.iterations.length} iterations
      {#if convergence.tokensUsed}
        <span class="tokens">({convergence.tokensUsed.toLocaleString()} tokens)</span>
      {/if}
    </div>
  {:else if convergence.status === 'stuck'}
    <div class="stuck-message" in:scale={{ duration: 300 }}>
      <span class="stuck-icon">🔒</span>
      Same errors repeated — needs manual intervention
    </div>
  {:else if convergence.status === 'timeout'}
    <div class="timeout-message" in:scale={{ duration: 300 }}>
      <span class="timeout-icon">⏱</span>
      Convergence timed out
    </div>
  {/if}
  
  <!-- Footer stats -->
  <div class="panel-footer">
    <span class="stat">
      Gates: {convergence.enabledGates.join(', ')}
    </span>
    {#if convergence.tokensUsed}
      <span class="stat">
        Tokens: {convergence.tokensUsed.toLocaleString()}
      </span>
    {/if}
  </div>
</div>
{/if}

<style>
  .convergence-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-6);
    height: 100%;
  }
  
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: var(--space-3);
  }
  
  .panel-header h2 {
    font-family: var(--font-serif);
    font-size: var(--text-xl);
    color: var(--text-primary);
    margin: 0;
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .header-icon {
    font-size: var(--text-2xl);
  }
  
  .status-badges {
    display: flex;
    gap: var(--space-2);
  }
  
  .badge {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }
  
  .badge.running {
    background: var(--ui-gold-15);
    color: var(--text-gold);
    animation: pulse-opacity 1.5s ease-in-out infinite;
  }
  
  .badge.stable {
    background: rgba(var(--success-rgb), 0.15);
    color: var(--success);
  }
  
  .badge.escalated,
  .badge.stuck,
  .badge.timeout {
    background: rgba(var(--warning-rgb), 0.15);
    color: var(--warning);
  }
  
  .badge.iteration {
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
  }
  
  @keyframes pulse-opacity {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }
  
  /* Progress bar */
  .progress-container {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  
  .progress-bar {
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-full);
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--gradient-progress);
    border-radius: var(--radius-full);
    transition: width 0.3s ease-out;
    position: relative;
    overflow: hidden;
  }
  
  .progress-fill.running {
    box-shadow: var(--glow-gold-subtle);
  }
  
  .progress-fill.stable {
    background: var(--success);
  }
  
  .progress-fill.escalated,
  .progress-fill.stuck,
  .progress-fill.timeout {
    background: var(--warning);
  }
  
  .shimmer {
    position: absolute;
    inset: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.3),
      transparent
    );
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  .progress-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    text-align: right;
  }
  
  /* Gates overview */
  .gates-overview h3,
  .iterations-timeline h3 {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-secondary);
    margin: 0 0 var(--space-2);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .gates-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  
  .gate-chip {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .gate-chip.passed {
    border-color: var(--success);
    background: rgba(var(--success-rgb), 0.1);
  }
  
  .gate-chip.failed {
    border-color: var(--error);
    background: rgba(var(--error-rgb), 0.1);
  }
  
  .gate-name {
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .gate-status {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .gate-chip.passed .gate-status {
    color: var(--success);
  }
  
  .gate-chip.failed .gate-status {
    color: var(--error);
  }
  
  /* Iterations timeline */
  .iterations-timeline {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
  }
  
  .iterations-list {
    flex: 1;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .iteration-row {
    padding: var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
  }
  
  .iteration-row.passed {
    border-left: 3px solid var(--success);
  }
  
  .iteration-row.failed {
    border-left: 3px solid var(--error);
  }
  
  .iteration-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
  }
  
  .iteration-num {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    font-weight: 700;
  }
  
  .iteration-status {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .status-icon.passed {
    color: var(--success);
  }
  
  .status-icon.failed {
    color: var(--error);
  }
  
  .iteration-gates {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  
  .gate-result {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    background: var(--bg-tertiary);
  }
  
  .gate-result.passed {
    background: rgba(var(--success-rgb), 0.1);
    color: var(--success);
  }
  
  .gate-result.failed {
    background: rgba(var(--error-rgb), 0.1);
    color: var(--error);
  }
  
  .gate-icon {
    font-weight: 700;
  }
  
  .error-count {
    opacity: 0.7;
  }
  
  .no-iterations {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    padding: var(--space-6);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  /* Status messages */
  .success-message,
  .escalated-message,
  .stuck-message,
  .timeout-message {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .success-message {
    background: rgba(var(--success-rgb), 0.1);
    color: var(--success);
    border: 1px solid var(--success);
  }
  
  .escalated-message,
  .stuck-message,
  .timeout-message {
    background: rgba(var(--warning-rgb), 0.1);
    color: var(--warning);
    border: 1px solid var(--warning);
  }
  
  .success-icon,
  .escalated-icon,
  .stuck-icon,
  .timeout-icon {
    font-size: var(--text-lg);
  }
  
  .duration,
  .tokens {
    opacity: 0.7;
  }
  
  /* Footer */
  .panel-footer {
    display: flex;
    justify-content: space-between;
    padding-top: var(--space-3);
    border-top: 1px solid var(--border-subtle);
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .stat {
    display: flex;
    align-items: center;
    gap: var(--space-1);
  }
  
  /* Reduced motion */
  @media (prefers-reduced-motion: reduce) {
    .shimmer,
    .badge.running {
      animation: none;
    }
  }
</style>
