<!--
  PipelineSection — RFC-106 pipeline progress display
  
  Shows goal pipeline with completion status and current step indicator.
  Extracted from ProjectOverview.svelte pipeline section.
-->
<script lang="ts">
  import type { PipelineStep } from '$lib/types';
  
  interface Props {
    pipeline: PipelineStep[];
    currentStep: string | null;
    completionPercent: number;
  }
  
  let { pipeline, currentStep, completionPercent }: Props = $props();
  
  function getStepIcon(step: PipelineStep): string {
    switch (step.status) {
      case 'completed': return '✅';
      case 'in_progress': return '🔄';
      default: return '⏳';
    }
  }
</script>

<section class="pipeline-section">
  <h3 class="pipeline-header">
    <span>📋 Pipeline</span>
    <span class="completion">{Math.round(completionPercent * 100)}% done</span>
  </h3>
  <div class="pipeline">
    {#each pipeline as step (step.id)}
      <div 
        class="step" 
        class:current={step.id === currentStep}
        class:completed={step.status === 'completed'}
      >
        <span class="step-icon">{getStepIcon(step)}</span>
        <span class="step-title">{step.title}</span>
        {#if step.id === currentStep}
          <span class="current-marker">← current</span>
        {/if}
      </div>
    {/each}
  </div>
</section>

<style>
  .pipeline-section {
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }
  
  .pipeline-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin: 0 0 var(--space-2) 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .completion {
    font-weight: 400;
    color: var(--text-secondary);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
  }
  
  .pipeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
  }
  
  .step {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) 0;
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .step.completed {
    opacity: 0.6;
  }
  
  .step.current {
    font-weight: 500;
  }
  
  .step-icon {
    flex-shrink: 0;
    font-size: var(--text-sm);
  }
  
  .step-title {
    flex: 1;
  }
  
  .current-marker {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-style: italic;
  }
</style>
