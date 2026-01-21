<!--
  CandidateComparison — Side-by-side comparison of plan candidates (Svelte 5, RFC-058)
  
  Shows all candidates with metrics, highlighting the selected one.
-->
<script lang="ts">
  import type { PlanCandidate } from '$lib/types';
  
  interface Props {
    candidates?: PlanCandidate[];
    selected?: PlanCandidate | null;
  }
  
  let { candidates = [], selected = null }: Props = $props();
  
  // Filter out undefined entries and sort by ID for consistent display order
  let validCandidates = $derived(
    candidates
      .filter((c): c is PlanCandidate => c != null)
      .sort((a, b) => a.id.localeCompare(b.id))
  );
  
  // Extract display number from candidate ID (e.g., 'candidate-0' -> 1)
  function getDisplayNumber(id: string): number {
    const match = id.match(/-(\d+)$/);
    return match ? parseInt(match[1], 10) + 1 : 1;
  }
</script>

{#if validCandidates.length > 0}
  <div class="candidate-comparison">
    <h4>Plan Candidates ({validCandidates.length} generated)</h4>
    
    <div class="candidates-table-container">
      <table class="candidates-table" aria-label="Plan candidates comparison">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col">Artifacts</th>
            <th scope="col">Score</th>
            <th scope="col">Depth</th>
            <th scope="col">Parallelism</th>
            <th scope="col">Balance</th>
            <th scope="col">Strategy</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each validCandidates as candidate}
            {@const isSelected = selected?.id === candidate.id}
            <tr class:selected={isSelected}>
              <td>{getDisplayNumber(candidate.id)}</td>
              <td>{candidate.artifact_count}</td>
              <td class="score">
                {#if candidate.score !== undefined}
                  {candidate.score.toFixed(1)}
                {:else}
                  <span class="pending">—</span>
                {/if}
              </td>
              <td>{candidate.metrics?.depth ?? '—'}</td>
              <td>
                {#if candidate.metrics?.parallelism_factor !== undefined}
                  {(candidate.metrics.parallelism_factor * 100).toFixed(0)}%
                {:else}
                  —
                {/if}
              </td>
              <td>
                {#if candidate.metrics?.balance_factor !== undefined}
                  {candidate.metrics.balance_factor.toFixed(2)}
                {:else}
                  —
                {/if}
              </td>
              <td class="strategy">
                {candidate.variance_config?.prompt_style ?? 'default'}
              </td>
              <td>
                {#if isSelected}
                  <span class="badge selected">Selected</span>
                {:else}
                  <span class="badge">Considered</span>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    
    {#if selected?.selection_reason}
      <div class="selection-reason">
        <strong>Selection reason:</strong> {selected.selection_reason}
      </div>
    {/if}
  </div>
{/if}

<style>
  .candidate-comparison {
    margin-bottom: var(--space-4);
  }
  
  .candidate-comparison h4 {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    margin-bottom: var(--space-3);
    color: var(--text-primary);
  }
  
  .candidates-table-container {
    overflow-x: auto;
    margin-bottom: var(--space-3);
  }
  
  .candidates-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
  }
  
  .candidates-table thead {
    background: var(--bg-tertiary);
  }
  
  .candidates-table th {
    padding: var(--space-2) var(--space-3);
    text-align: left;
    font-weight: 500;
    color: var(--text-secondary);
    border-bottom: var(--border-width) solid var(--border-color);
  }
  
  .candidates-table td {
    padding: var(--space-2) var(--space-3);
    border-bottom: var(--border-width) solid var(--border-color);
    color: var(--text-secondary);
  }
  
  .candidates-table tbody tr {
    transition: background var(--transition-fast);
  }
  
  .candidates-table tbody tr:hover {
    background: var(--bg-tertiary);
  }
  
  .candidates-table tbody tr.selected {
    background: rgba(var(--gold-rgb), 0.1);
  }
  
  .candidates-table tbody tr.selected td {
    color: var(--text-gold);
    font-weight: 500;
  }
  
  .score {
    font-weight: 500;
    color: var(--text-gold);
  }
  
  .pending {
    color: var(--text-tertiary);
    font-style: italic;
  }
  
  .strategy {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  .badge {
    display: inline-block;
    padding: var(--space-1) var(--space-2);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    font-weight: 500;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
  }
  
  .badge.selected {
    background: var(--gradient-ui-gold);
    color: var(--bg-primary);
    box-shadow: var(--glow-gold-subtle);
  }
  
  .selection-reason {
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    font-family: var(--font-mono);
  }
  
  .selection-reason strong {
    color: var(--text-primary);
  }
</style>
