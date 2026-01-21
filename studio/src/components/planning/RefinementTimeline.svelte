<!--
  RefinementTimeline — Round-by-round refinement improvements (Svelte 5, RFC-058)
  
  Shows each refinement round with score changes and improvements.
-->
<script lang="ts">
  import type { RefinementRound } from '$lib/types';
  
  interface Props {
    rounds?: RefinementRound[];
  }
  
  let { rounds = [] }: Props = $props();
  
  // Filter out undefined entries (defensive - should not occur but prevents errors)
  let validRounds = $derived(rounds.filter((r): r is RefinementRound => r != null));
</script>

{#if validRounds.length > 0}
  <div class="refinement-timeline">
    <h4>Refinement Rounds ({validRounds.length})</h4>
    
    <div class="timeline" role="list" aria-label="Refinement rounds">
      {#each validRounds as round}
        <div class="timeline-item" role="listitem">
          <div class="round-number">Round {round.round}</div>
          <div class="round-content">
            <div class="score-change">
              {#if round.improved && round.new_score !== undefined}
                <span class="improved">
                  {round.current_score.toFixed(1)} → {round.new_score.toFixed(1)}
                  {#if round.improvement !== undefined}
                    (+{round.improvement.toFixed(1)})
                  {/if}
                </span>
              {:else}
                <span class="no-change">
                  {round.current_score.toFixed(1)} 
                  {#if round.reason}
                    ({round.reason})
                  {:else}
                    (no improvement)
                  {/if}
                </span>
              {/if}
            </div>
            {#if round.improvements_identified}
              <div class="improvements">
                {round.improvements_identified}
              </div>
            {/if}
          </div>
        </div>
      {/each}
    </div>
  </div>
{/if}

<style>
  .refinement-timeline {
    margin-bottom: var(--space-4);
  }
  
  .refinement-timeline h4 {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    margin-bottom: var(--space-3);
    color: var(--text-primary);
  }
  
  .timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  
  .timeline-item {
    display: flex;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-sm);
  }
  
  .round-number {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-primary);
    min-width: 60px;
  }
  
  .round-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .score-change {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
  }
  
  .score-change .improved {
    color: var(--success);
    font-weight: 500;
  }
  
  .score-change .no-change {
    color: var(--text-tertiary);
  }
  
  .improvements {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    font-style: italic;
  }
</style>
