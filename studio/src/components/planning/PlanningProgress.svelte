<!--
  PlanningProgress — Progress bar for planning phases (Svelte 5, RFC-058)
  
  Shows real-time progress during candidate generation, scoring, and refinement.
-->
<script lang="ts">
  import { PlanningPhase } from '$lib/constants';
  import type { PlanningProgress as PlanningProgressType } from '$lib/types';
  import Sparkle from '../ui/Sparkle.svelte';
  
  interface Props {
    progress?: PlanningProgressType | null;
  }
  
  let { progress = null }: Props = $props();
  
  let percentage = $derived(
    progress 
      ? Math.min((progress.current_candidates / progress.total_candidates) * 100, 100)
      : 0
  );
  
  const phaseLabels = {
    [PlanningPhase.GENERATING]: 'Generating candidates',
    [PlanningPhase.SCORING]: 'Scoring candidates',
    [PlanningPhase.REFINING]: 'Refining plan',
    [PlanningPhase.COMPLETE]: 'Complete',
  } as const;
</script>

{#if progress && progress.total_candidates > 0}
  <div class="planning-progress">
    <div class="progress-header">
      <span class="phase-label">
        {#if progress.phase === PlanningPhase.GENERATING}
          <Sparkle style="star" speed={120} />
        {/if}
        {phaseLabels[progress.phase]}
      </span>
      <span class="progress-text">{progress.current_candidates} / {progress.total_candidates}</span>
    </div>
    
    <div class="progress-bar-container">
      <div 
        class="progress-bar" 
        style="width: {percentage}%"
        role="progressbar"
        aria-valuenow={progress.current_candidates}
        aria-valuemin={0}
        aria-valuemax={progress.total_candidates}
        aria-label="Planning progress: {percentage}%"
      >
        <div class="progress-fill"></div>
      </div>
    </div>
    
    {#if progress.phase === PlanningPhase.GENERATING}
      <div class="progress-detail">
        Generating plan candidates with different strategies...
      </div>
    {:else if progress.phase === PlanningPhase.SCORING}
      <div class="progress-detail">
        Evaluating candidates for parallelism and efficiency...
      </div>
    {:else if progress.phase === PlanningPhase.REFINING}
      <div class="progress-detail">
        Refining selected plan to improve quality...
      </div>
    {/if}
  </div>
{/if}

<style>
  .planning-progress {
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    margin-bottom: var(--space-4);
  }
  
  .progress-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-2);
    font-size: var(--text-sm);
  }
  
  .phase-label {
    font-weight: 500;
    color: var(--text-primary);
    font-family: var(--font-mono);
  }
  
  .progress-text {
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .progress-bar-container {
    width: 100%;
    height: 8px;
    background: var(--bg-tertiary);
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: var(--space-2);
  }
  
  .progress-bar {
    height: 100%;
    background: var(--gradient-progress);
    transition: width 0.3s ease;
    position: relative;
    box-shadow: var(--glow-gold-subtle);
  }
  
  .progress-fill {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
      90deg,
      transparent,
      rgba(255, 255, 255, 0.2),
      transparent
    );
    animation: shimmer 1.5s infinite;
  }
  
  @keyframes shimmer {
    0% { transform: translateX(-100%); }
    100% { transform: translateX(100%); }
  }
  
  .progress-detail {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-style: italic;
  }
</style>
