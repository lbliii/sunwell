<!--
  WorkflowPanel.svelte — Autonomous workflow execution progress (RFC-086)

  Shows:
  - Current workflow chain and step progress
  - Completed, running, and pending steps
  - Controls for stop, skip, resume
  - State persistence indicator
-->
<script lang="ts">
  import { fly } from 'svelte/transition';
  import {
    workflowState,
    stopWorkflow,
    resumeWorkflow,
    skipStep,
    type WorkflowStep,
    type WorkflowExecution,
  } from '../../stores';
  import { parseError } from '$lib/error';
  import ErrorDisplay from '../ui/ErrorDisplay.svelte';

  interface Props {
    /** Override workflow (optional - uses store by default) */
    workflow?: WorkflowExecution | null;
    onStop?: () => void;
    onResume?: () => void;
    onSkipStep?: () => void;
  }

  let {
    workflow: propWorkflow = null,
    onStop,
    onResume,
    onSkipStep,
  }: Props = $props();

  // Use prop if provided, otherwise use store
  const workflow = $derived(propWorkflow ?? workflowState.execution);

  // Handlers that use store actions if no prop handlers provided
  function handleStop() {
    if (onStop) {
      onStop();
    } else {
      stopWorkflow();
    }
  }

  function handleResume() {
    if (onResume) {
      onResume();
    } else {
      resumeWorkflow();
    }
  }

  function handleSkipStep() {
    if (onSkipStep) {
      onSkipStep();
    } else {
      skipStep();
    }
  }

  let expanded = $state(true);

  const progress = $derived(
    workflow ? (workflow.current_step / workflow.total_steps) * 100 : 0
  );

  const isRunning = $derived(workflow?.status === 'running');
  const isPaused = $derived(workflow?.status === 'paused');
  const isComplete = $derived(workflow?.status === 'completed');
  const hasError = $derived(workflow?.status === 'error');

  // Parse step error into structured format
  const stepError = $derived(() => {
    if (!hasError || !workflow) return null;
    const errorStep = workflow.steps.find((s) => s.error);
    return errorStep?.error ? parseError(errorStep.error) : null;
  });

  function getStepIcon(status: string): string {
    switch (status) {
      case 'success':
        return '✅';
      case 'running':
        return '🔄';
      case 'error':
        return '❌';
      case 'warning':
        return '⚠️';
      case 'skipped':
        return '⏭';
      default:
        return '⏳';
    }
  }

  function formatDuration(seconds?: number): string {
    if (!seconds) return '...';
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
    return `${seconds.toFixed(1)}s`;
  }
</script>

{#if workflow}
  <div
    class="workflow-panel"
    class:running={isRunning}
    class:paused={isPaused}
    class:complete={isComplete}
    class:error={hasError}
    transition:fly={{ y: 20, duration: 200 }}
  >
    <button class="header" onclick={() => (expanded = !expanded)}>
      <span class="status-icon">
        {#if isRunning}
          <span class="spinner">🔄</span>
        {:else if isPaused}
          ⏸
        {:else if isComplete}
          ✅
        {:else if hasError}
          ❌
        {/if}
      </span>
      <span class="title">
        <span class="chain-name">{workflow.chain_name}</span>
        <span class="step-count">
          Step {workflow.current_step + 1}/{workflow.total_steps}
        </span>
      </span>
      <span class="toggle">{expanded ? '▼' : '▶'}</span>
    </button>

    <div class="progress-bar">
      <div class="progress-fill" style="width: {progress}%"></div>
    </div>

    {#if expanded}
      <div class="content" transition:fly={{ y: -10, duration: 150 }}>
        <div class="description">{workflow.description}</div>

        <div class="steps">
          {#each workflow.steps as step, i}
            <div class="step" class:current={i === workflow.current_step}>
              <span class="step-icon">{getStepIcon(step.status)}</span>
              <span class="step-skill">{step.skill}</span>
              <span class="step-purpose">{step.purpose}</span>
              {#if step.duration_s !== undefined}
                <span class="step-duration">{formatDuration(step.duration_s)}</span>
              {/if}
            </div>
          {/each}
        </div>

        {#if hasError && stepError()}
          <div class="error-container">
            <ErrorDisplay error={stepError()} compact onRetry={handleResume} />
          </div>
        {/if}

        <div class="controls">
          {#if isRunning}
            <button class="control-btn stop" onclick={handleStop}>
              ⏹ Stop
            </button>
            <button class="control-btn skip" onclick={handleSkipStep}>
              ⏭ Skip Step
            </button>
          {:else if isPaused || hasError}
            <button class="control-btn resume" onclick={handleResume}>
              ▶ Resume
            </button>
          {:else if isComplete}
            <span class="complete-message">Workflow complete</span>
          {/if}
        </div>

        <div class="footer">
          <span class="state-path">💾 .sunwell/state/...</span>
          <span class="execution-id">{workflow.id.slice(0, 20)}...</span>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .workflow-panel {
    background: var(--surface-2, #1a1a2e);
    border-radius: 8px;
    overflow: hidden;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 12px;
    border: 1px solid var(--border, #333);
  }

  .workflow-panel.running {
    border-color: var(--accent, #6366f1);
  }

  .workflow-panel.paused {
    border-color: var(--warning, #ffd93d);
  }

  .workflow-panel.complete {
    border-color: var(--success, #6bff6b);
  }

  .workflow-panel.error {
    border-color: var(--error, #ff6b6b);
  }

  .header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: var(--surface-3, #252547);
    cursor: pointer;
    border: none;
    width: 100%;
    text-align: left;
    color: inherit;
  }

  .header:hover {
    background: var(--surface-4, #2d2d5a);
  }

  .status-icon {
    font-size: 14px;
  }

  .spinner {
    display: inline-block;
    animation: spin 1s linear infinite;
  }

  @keyframes spin {
    from {
      transform: rotate(0deg);
    }
    to {
      transform: rotate(360deg);
    }
  }

  .title {
    flex: 1;
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .chain-name {
    font-weight: 600;
  }

  .step-count {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .toggle {
    color: var(--text-muted, #888);
    font-size: 10px;
  }

  .progress-bar {
    height: 3px;
    background: var(--surface-1, #0f0f1a);
  }

  .progress-fill {
    height: 100%;
    background: var(--accent, #6366f1);
    transition: width 0.3s ease;
  }

  .workflow-panel.complete .progress-fill {
    background: var(--success, #6bff6b);
  }

  .workflow-panel.error .progress-fill {
    background: var(--error, #ff6b6b);
  }

  .content {
    padding: 12px;
  }

  .description {
    color: var(--text-muted, #888);
    font-size: 11px;
    margin-bottom: 12px;
  }

  .steps {
    display: flex;
    flex-direction: column;
    gap: 4px;
    margin-bottom: 12px;
  }

  .step {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 8px;
    border-radius: 4px;
    background: var(--surface-1, #0f0f1a);
  }

  .step.current {
    background: var(--accent-bg, rgba(99, 102, 241, 0.2));
    border-left: 2px solid var(--accent, #6366f1);
  }

  .step-icon {
    flex-shrink: 0;
  }

  .step-skill {
    font-weight: 500;
    min-width: 120px;
  }

  .step-purpose {
    flex: 1;
    color: var(--text-muted, #888);
    font-size: 11px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .step-duration {
    color: var(--text-muted, #666);
    font-size: 10px;
  }

  .error-container {
    margin-bottom: 12px;
  }

  .controls {
    display: flex;
    gap: 8px;
    margin-bottom: 12px;
  }

  .control-btn {
    border: none;
    border-radius: 4px;
    padding: 6px 12px;
    font-size: 11px;
    cursor: pointer;
    font-family: inherit;
  }

  .control-btn.stop {
    background: var(--error, #ff6b6b);
    color: white;
  }

  .control-btn.skip {
    background: var(--surface-3, #252547);
    color: var(--text, #fff);
  }

  .control-btn.resume {
    background: var(--accent, #6366f1);
    color: white;
  }

  .control-btn:hover {
    opacity: 0.9;
  }

  .complete-message {
    color: var(--success, #6bff6b);
    font-size: 11px;
  }

  .footer {
    display: flex;
    justify-content: space-between;
    padding-top: 8px;
    border-top: 1px solid var(--border, #333);
    color: var(--text-muted, #666);
    font-size: 10px;
  }
</style>
