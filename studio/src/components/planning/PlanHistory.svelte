<!--
  PlanHistory — Version timeline for plan evolution (Svelte 5, RFC-120)
  
  Shows plan versions with timestamps, reasons, and diff capabilities.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  
  interface PlanVersion {
    version: number;
    plan_id: string;
    goal: string;
    artifacts: string[];
    tasks: string[];
    score: number | null;
    created_at: string;
    reason: string;
    added_artifacts: string[];
    removed_artifacts: string[];
    modified_artifacts: string[];
  }
  
  interface PlanDiff {
    plan_id: string;
    v1: number;
    v2: number;
    added: string[];
    removed: string[];
    modified: string[];
  }
  
  interface Props {
    planId: string;
    onVersionSelect?: (version: PlanVersion) => void;
  }
  
  let { planId, onVersionSelect }: Props = $props();
  
  let versions = $state<PlanVersion[]>([]);
  let selectedVersion = $state<number | null>(null);
  let compareFrom = $state<number | null>(null);
  let compareTo = $state<number | null>(null);
  let diff = $state<PlanDiff | null>(null);
  let loading = $state(true);
  let error = $state<string | null>(null);
  
  async function loadVersions() {
    loading = true;
    error = null;
    
    try {
      const response = await fetch(`/api/plans/${planId}/versions`);
      const data = await response.json();
      
      if (data.error) {
        error = data.error;
      } else {
        versions = data.versions || [];
      }
    } catch (e) {
      error = e instanceof Error ? e.message : 'Failed to load versions';
    } finally {
      loading = false;
    }
  }
  
  async function loadDiff() {
    if (compareFrom === null || compareTo === null) return;
    
    try {
      const response = await fetch(
        `/api/plans/${planId}/diff?v1=${compareFrom}&v2=${compareTo}`
      );
      const data = await response.json();
      
      if (!data.error) {
        diff = data;
      }
    } catch (e) {
      console.error('Failed to load diff:', e);
    }
  }
  
  function selectVersion(version: PlanVersion) {
    selectedVersion = version.version;
    onVersionSelect?.(version);
  }
  
  function startCompare(v: number) {
    if (compareFrom === null) {
      compareFrom = v;
    } else if (compareTo === null && v !== compareFrom) {
      compareTo = v;
      loadDiff();
    } else {
      // Reset comparison
      compareFrom = v;
      compareTo = null;
      diff = null;
    }
  }
  
  function clearCompare() {
    compareFrom = null;
    compareTo = null;
    diff = null;
  }
  
  function formatTime(isoString: string): string {
    const date = new Date(isoString);
    return date.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  }
  
  onMount(() => {
    loadVersions();
  });
  
  // Reload when planId changes
  $effect(() => {
    if (planId) {
      loadVersions();
    }
  });
</script>

<div class="plan-history">
  <div class="header">
    <h3>Plan History</h3>
    {#if compareFrom !== null}
      <button class="clear-compare" onclick={clearCompare}>
        Clear Comparison
      </button>
    {/if}
  </div>
  
  {#if loading}
    <div class="loading">Loading versions...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else if versions.length === 0}
    <div class="empty">No versions saved for this plan</div>
  {:else}
    <div class="version-timeline" role="list" aria-label="Plan versions">
      {#each versions as version (version.version)}
        {@const isSelected = selectedVersion === version.version}
        {@const isCompareFrom = compareFrom === version.version}
        {@const isCompareTo = compareTo === version.version}
        
        <div
          class="version"
          class:selected={isSelected}
          class:compare-from={isCompareFrom}
          class:compare-to={isCompareTo}
          role="listitem"
        >
          <button
            class="version-select"
            onclick={() => selectVersion(version)}
            aria-pressed={isSelected}
          >
            <span class="version-num">v{version.version}</span>
            <span class="version-reason">{version.reason}</span>
            {#if version.score !== null}
              <span class="version-score">{version.score.toFixed(1)}</span>
            {/if}
            <span class="version-time">{formatTime(version.created_at)}</span>
          </button>
          
          <button
            class="compare-btn"
            onclick={() => startCompare(version.version)}
            title={
              compareFrom === null
                ? 'Select for comparison'
                : compareFrom === version.version
                  ? 'Selected as base'
                  : 'Compare with v' + compareFrom
            }
          >
            {#if isCompareFrom}
              ⬤
            {:else if isCompareTo}
              ◉
            {:else}
              ○
            {/if}
          </button>
          
          {#if version.added_artifacts.length > 0 || version.removed_artifacts.length > 0}
            <div class="version-changes">
              {#if version.added_artifacts.length > 0}
                <span class="change added">+{version.added_artifacts.length}</span>
              {/if}
              {#if version.removed_artifacts.length > 0}
                <span class="change removed">-{version.removed_artifacts.length}</span>
              {/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>
    
    {#if diff}
      <div class="diff-panel">
        <h4>Diff: v{diff.v1} → v{diff.v2}</h4>
        
        {#if diff.added.length > 0}
          <div class="diff-section added">
            <span class="diff-label">+ Added ({diff.added.length})</span>
            <ul>
              {#each diff.added as artifact (artifact)}
                <li>{artifact}</li>
              {/each}
            </ul>
          </div>
        {/if}
        
        {#if diff.removed.length > 0}
          <div class="diff-section removed">
            <span class="diff-label">- Removed ({diff.removed.length})</span>
            <ul>
              {#each diff.removed as artifact (artifact)}
                <li>{artifact}</li>
              {/each}
            </ul>
          </div>
        {/if}
        
        {#if diff.modified.length > 0}
          <div class="diff-section modified">
            <span class="diff-label">~ Modified ({diff.modified.length})</span>
            <ul>
              {#each diff.modified as artifact (artifact)}
                <li>{artifact}</li>
              {/each}
            </ul>
          </div>
        {/if}
        
        {#if diff.added.length === 0 && diff.removed.length === 0 && diff.modified.length === 0}
          <div class="no-changes">No changes between versions</div>
        {/if}
      </div>
    {/if}
  {/if}
</div>

<style>
  .plan-history {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .header h3 {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
    margin: 0;
  }
  
  .clear-compare {
    font-size: var(--text-xs);
    padding: var(--space-1) var(--space-2);
    background: var(--bg-tertiary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    color: var(--text-secondary);
    cursor: pointer;
  }
  
  .clear-compare:hover {
    background: var(--bg-hover);
  }
  
  .loading, .error, .empty {
    font-size: var(--text-sm);
    color: var(--text-muted);
    text-align: center;
    padding: var(--space-4);
  }
  
  .error {
    color: var(--color-error);
  }
  
  .version-timeline {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .version {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2);
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
    transition: all 0.15s ease;
  }
  
  .version:hover {
    border-color: var(--border-secondary);
  }
  
  .version.selected {
    border-color: var(--color-accent);
    background: var(--bg-accent-subtle);
  }
  
  .version.compare-from {
    border-color: var(--color-info);
    box-shadow: inset 2px 0 0 var(--color-info);
  }
  
  .version.compare-to {
    border-color: var(--color-success);
    box-shadow: inset 2px 0 0 var(--color-success);
  }
  
  .version-select {
    flex: 1;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    text-align: left;
    font-family: inherit;
  }
  
  .version-num {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--color-accent);
    min-width: 2.5rem;
  }
  
  .version-reason {
    flex: 1;
    font-size: var(--text-sm);
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .version-score {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--color-success);
    background: var(--bg-success-subtle);
    padding: 0 var(--space-1);
    border-radius: var(--radius-xs);
  }
  
  .version-time {
    font-size: var(--text-xs);
    color: var(--text-muted);
    white-space: nowrap;
  }
  
  .compare-btn {
    background: none;
    border: none;
    padding: var(--space-1);
    cursor: pointer;
    color: var(--text-muted);
    font-size: var(--text-sm);
  }
  
  .compare-btn:hover {
    color: var(--text-primary);
  }
  
  .version-changes {
    display: flex;
    gap: var(--space-1);
  }
  
  .change {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    padding: 0 var(--space-1);
    border-radius: var(--radius-xs);
  }
  
  .change.added {
    color: var(--color-success);
    background: var(--bg-success-subtle);
  }
  
  .change.removed {
    color: var(--color-error);
    background: var(--bg-error-subtle);
  }
  
  .diff-panel {
    margin-top: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-primary);
    border: 1px solid var(--border-primary);
    border-radius: var(--radius-sm);
  }
  
  .diff-panel h4 {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0 0 var(--space-2) 0;
  }
  
  .diff-section {
    margin-bottom: var(--space-2);
  }
  
  .diff-section:last-child {
    margin-bottom: 0;
  }
  
  .diff-label {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    font-weight: 500;
  }
  
  .diff-section.added .diff-label {
    color: var(--color-success);
  }
  
  .diff-section.removed .diff-label {
    color: var(--color-error);
  }
  
  .diff-section.modified .diff-label {
    color: var(--color-warning);
  }
  
  .diff-section ul {
    margin: var(--space-1) 0 0 var(--space-3);
    padding: 0;
    list-style: none;
  }
  
  .diff-section li {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-secondary);
    padding: var(--space-1) 0;
  }
  
  .no-changes {
    font-size: var(--text-sm);
    color: var(--text-muted);
    text-align: center;
    padding: var(--space-2);
  }
</style>
