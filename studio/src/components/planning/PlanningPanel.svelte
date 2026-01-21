<!--
  PlanningPanel — Main planning visibility panel (Svelte 5, RFC-058)
-->
<script lang="ts">
  import { agent } from '../../stores/agent.svelte';
  import PlanningProgress from './PlanningProgress.svelte';
  import CandidateComparison from './CandidateComparison.svelte';
  import RefinementTimeline from './RefinementTimeline.svelte';
  
  let candidates = $derived(agent.planningCandidates || []);
  let selectedCandidate = $derived(agent.selectedCandidate);
  let refinementRounds = $derived(agent.refinementRounds || []);
  let planningProgress = $derived(agent.planningProgress);
</script>

{#if planningProgress || candidates.length > 0 || refinementRounds.length > 0}
  <div class="planning-panel" role="region" aria-label="Planning details">
    <h3>Planning Details</h3>
    
    {#if planningProgress}
      <PlanningProgress progress={planningProgress} />
    {/if}
    
    {#if candidates.length > 0}
      <CandidateComparison candidates={candidates} selected={selectedCandidate} />
    {/if}
    
    {#if refinementRounds.length > 0}
      <RefinementTimeline rounds={refinementRounds} />
    {/if}
    
    {#if selectedCandidate?.metrics}
      <div class="metrics-summary">
        <h4>Selected Plan Metrics</h4>
        <div class="metrics-grid" role="list">
          {#if selectedCandidate.score !== undefined}
            <div class="metric" role="listitem">
              <span class="metric-label">Score</span>
              <span class="metric-value">{selectedCandidate.score.toFixed(1)}</span>
            </div>
          {/if}
          <div class="metric" role="listitem">
            <span class="metric-label">Depth</span>
            <span class="metric-value">{selectedCandidate.metrics.depth}</span>
          </div>
          <div class="metric" role="listitem">
            <span class="metric-label">Parallelism</span>
            <span class="metric-value">{(selectedCandidate.metrics.parallelism_factor * 100).toFixed(0)}%</span>
          </div>
          <div class="metric" role="listitem">
            <span class="metric-label">Balance</span>
            <span class="metric-value">{selectedCandidate.metrics.balance_factor.toFixed(2)}</span>
          </div>
          <div class="metric" role="listitem">
            <span class="metric-label">Waves</span>
            <span class="metric-value">{selectedCandidate.metrics.estimated_waves}</span>
          </div>
          {#if selectedCandidate.metrics.file_conflicts > 0}
            <div class="metric warning" role="listitem">
              <span class="metric-label">Conflicts</span>
              <span class="metric-value">{selectedCandidate.metrics.file_conflicts}</span>
            </div>
          {/if}
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .planning-panel { padding: var(--space-4); background: var(--bg-secondary); border-radius: var(--radius-md); margin-bottom: var(--space-4); }
  .planning-panel h3 { font-family: var(--font-mono); font-size: var(--text-base); font-weight: 500; margin-bottom: var(--space-4); color: var(--text-primary); }
  .metrics-summary { margin-top: var(--space-4); padding-top: var(--space-4); border-top: var(--border-width) solid var(--border-color); }
  .metrics-summary h4 { font-family: var(--font-mono); font-size: var(--text-sm); font-weight: 500; margin-bottom: var(--space-3); color: var(--text-primary); }
  .metrics-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: var(--space-3); }
  .metric { display: flex; flex-direction: column; gap: var(--space-1); padding: var(--space-2); background: var(--bg-tertiary); border-radius: var(--radius-sm); }
  .metric.warning { background: rgba(var(--error-rgb), 0.1); }
  .metric-label { font-size: var(--text-xs); color: var(--text-tertiary); font-family: var(--font-mono); }
  .metric-value { font-size: var(--text-base); font-weight: 500; color: var(--text-primary); font-family: var(--font-mono); }
</style>
