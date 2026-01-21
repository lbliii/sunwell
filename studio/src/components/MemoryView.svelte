<!--
  MemoryView — Project intelligence and memory display (Svelte 5)
  
  Shows the accumulated intelligence from the agent's work:
  - Memory stats (session, tiers, branches)
  - Decisions made
  - Failed approaches (what didn't work)
  - Learnings discovered
  - Dead ends to avoid
-->
<script lang="ts">
  import type { MemoryStats, IntelligenceData, Decision, FailedApproach, Learning, DeadEnd } from '$lib/types';
  
  interface Props {
    stats: MemoryStats | null;
    intelligence: IntelligenceData | null;
  }
  
  let { stats, intelligence }: Props = $props();
  
  // Collapsible section states
  let sectionsOpen = $state({
    decisions: true,
    failures: true,
    learnings: true,
    deadEnds: false,
  });
  
  function toggleSection(section: keyof typeof sectionsOpen) {
    sectionsOpen[section] = !sectionsOpen[section];
  }
  
  function formatDate(dateStr: string | null): string {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString();
    } catch {
      return '';
    }
  }
</script>

<div class="memory-view">
  <!-- Memory Stats Overview -->
  {#if stats}
    <section class="stats-section">
      <h3 class="section-title">Memory Overview</h3>
      <div class="stats-grid">
        <div class="stat-card">
          <span class="stat-value">{stats.totalTurns}</span>
          <span class="stat-label">Total Turns</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{stats.hotTurns}</span>
          <span class="stat-label">Hot Memory</span>
        </div>
        <div class="stat-card tier-warm">
          <span class="stat-value">{stats.warmFiles}</span>
          <span class="stat-label">Warm Files</span>
          <span class="stat-detail">{stats.warmSizeMb.toFixed(1)} MB</span>
        </div>
        <div class="stat-card tier-cold">
          <span class="stat-value">{stats.coldFiles}</span>
          <span class="stat-label">Cold Files</span>
          <span class="stat-detail">{stats.coldSizeMb.toFixed(1)} MB</span>
        </div>
        <div class="stat-card">
          <span class="stat-value">{stats.branches}</span>
          <span class="stat-label">Branches</span>
        </div>
        <div class="stat-card stat-warning">
          <span class="stat-value">{stats.deadEnds}</span>
          <span class="stat-label">Dead Ends</span>
        </div>
        <div class="stat-card stat-success">
          <span class="stat-value">{stats.learnings}</span>
          <span class="stat-label">Learnings</span>
        </div>
      </div>
    </section>
  {/if}
  
  <!-- Intelligence Sections -->
  {#if intelligence}
    <!-- Decisions -->
    <section class="intelligence-section">
      <button 
        class="section-header" 
        onclick={() => toggleSection('decisions')}
        aria-expanded={sectionsOpen.decisions}
        type="button"
      >
        <span class="section-icon">[D]</span>
        <span class="section-title">Decisions</span>
        <span class="section-count">{intelligence.totalDecisions}</span>
        <span class="section-toggle">{sectionsOpen.decisions ? '▾' : '▸'}</span>
      </button>
      
      {#if sectionsOpen.decisions && intelligence.decisions.length > 0}
        <ul class="item-list" role="list">
          {#each intelligence.decisions as decision (decision.id)}
            <li class="item-card decision">
              <div class="item-main">{decision.decision}</div>
              {#if decision.rationale}
                <div class="item-detail">{decision.rationale}</div>
              {/if}
              {#if decision.scope || decision.createdAt}
                <div class="item-meta">
                  {#if decision.scope}<span class="meta-tag">{decision.scope}</span>{/if}
                  {#if decision.createdAt}<span class="meta-date">{formatDate(decision.createdAt)}</span>{/if}
                </div>
              {/if}
            </li>
          {/each}
        </ul>
      {:else if sectionsOpen.decisions}
        <p class="empty-message">No decisions recorded yet</p>
      {/if}
    </section>
    
    <!-- Failed Approaches -->
    <section class="intelligence-section">
      <button 
        class="section-header" 
        onclick={() => toggleSection('failures')}
        aria-expanded={sectionsOpen.failures}
        type="button"
      >
        <span class="section-icon">[✗]</span>
        <span class="section-title">Failed Approaches</span>
        <span class="section-count">{intelligence.totalFailures}</span>
        <span class="section-toggle">{sectionsOpen.failures ? '▾' : '▸'}</span>
      </button>
      
      {#if sectionsOpen.failures && intelligence.failures.length > 0}
        <ul class="item-list" role="list">
          {#each intelligence.failures as failure (failure.id)}
            <li class="item-card failure">
              <div class="item-main">{failure.approach}</div>
              <div class="item-detail failure-reason">
                <span class="reason-label">Why it failed:</span> {failure.reason}
              </div>
              {#if failure.context}
                <div class="item-meta">{failure.context}</div>
              {/if}
            </li>
          {/each}
        </ul>
      {:else if sectionsOpen.failures}
        <p class="empty-message">No failed approaches recorded</p>
      {/if}
    </section>
    
    <!-- Learnings -->
    <section class="intelligence-section">
      <button 
        class="section-header" 
        onclick={() => toggleSection('learnings')}
        aria-expanded={sectionsOpen.learnings}
        type="button"
      >
        <span class="section-icon">[✓]</span>
        <span class="section-title">Learnings</span>
        <span class="section-count">{intelligence.totalLearnings}</span>
        <span class="section-toggle">{sectionsOpen.learnings ? '▾' : '▸'}</span>
      </button>
      
      {#if sectionsOpen.learnings && intelligence.learnings.length > 0}
        <ul class="item-list" role="list">
          {#each intelligence.learnings as learning (learning.id)}
            <li class="item-card learning">
              <div class="item-main">{learning.fact}</div>
              <div class="item-meta">
                <span class="meta-tag category-{learning.category}">{learning.category}</span>
                {#if learning.confidence}
                  <span class="confidence" style="--confidence: {learning.confidence}">
                    {Math.round(learning.confidence * 100)}% confident
                  </span>
                {/if}
                {#if learning.sourceFile}
                  <span class="meta-file">{learning.sourceFile}</span>
                {/if}
              </div>
            </li>
          {/each}
        </ul>
      {:else if sectionsOpen.learnings}
        <p class="empty-message">No learnings recorded yet</p>
      {/if}
    </section>
    
    <!-- Dead Ends -->
    <section class="intelligence-section">
      <button 
        class="section-header" 
        onclick={() => toggleSection('deadEnds')}
        aria-expanded={sectionsOpen.deadEnds}
        type="button"
      >
        <span class="section-icon">[⊘]</span>
        <span class="section-title">Dead Ends</span>
        <span class="section-count">{intelligence.totalDeadEnds}</span>
        <span class="section-toggle">{sectionsOpen.deadEnds ? '▾' : '▸'}</span>
      </button>
      
      {#if sectionsOpen.deadEnds && intelligence.deadEnds.length > 0}
        <ul class="item-list" role="list">
          {#each intelligence.deadEnds as deadEnd, i (deadEnd.approach + i)}
            <li class="item-card dead-end">
              <div class="item-main">{deadEnd.approach}</div>
              <div class="item-detail">{deadEnd.reason}</div>
              {#if deadEnd.context}
                <div class="item-meta">{deadEnd.context}</div>
              {/if}
            </li>
          {/each}
        </ul>
      {:else if sectionsOpen.deadEnds}
        <p class="empty-message">No dead ends recorded</p>
      {/if}
    </section>
  {:else if !stats}
    <div class="empty-state">
      <span class="empty-icon">[~]</span>
      <p>No memory data available</p>
      <p class="empty-hint">Run a goal to start building project intelligence</p>
    </div>
  {/if}
</div>

<style>
  .memory-view {
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    padding: var(--space-4) 0;
    max-height: calc(100vh - 300px);
    overflow-y: auto;
  }
  
  /* Stats Section */
  .stats-section {
    padding-bottom: var(--space-4);
    border-bottom: 1px solid var(--border-color);
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: var(--space-3);
    margin-top: var(--space-3);
  }
  
  .stat-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-3);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    text-align: center;
  }
  
  .stat-value {
    font-size: var(--text-xl);
    font-weight: 600;
    color: var(--text-primary);
    font-family: var(--font-mono);
  }
  
  .stat-label {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin-top: var(--space-1);
  }
  
  .stat-detail {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    opacity: 0.7;
  }
  
  .stat-card.tier-warm .stat-value { color: var(--warning); }
  .stat-card.tier-cold .stat-value { color: var(--info); }
  .stat-card.stat-warning .stat-value { color: var(--error); }
  .stat-card.stat-success .stat-value { color: var(--success); }
  
  /* Intelligence Sections */
  .intelligence-section {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .section-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border: none;
    cursor: pointer;
    text-align: left;
    transition: background var(--transition-fast);
  }
  
  .section-header:hover {
    background: var(--bg-tertiary);
  }
  
  .section-header:focus-visible {
    outline: 2px solid rgba(201, 162, 39, 0.4);
    outline-offset: -2px;
  }
  
  .section-icon {
    font-family: var(--font-mono);
    color: var(--accent);
    font-size: var(--text-sm);
  }
  
  .section-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .section-count {
    background: var(--bg-primary);
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    padding: 2px 8px;
    border-radius: 10px;
    font-family: var(--font-mono);
  }
  
  .section-toggle {
    margin-left: auto;
    color: var(--text-tertiary);
    font-size: var(--text-xs);
  }
  
  /* Item Lists */
  .item-list {
    list-style: none;
    padding: 0;
    margin: 0;
    max-height: 300px;
    overflow-y: auto;
  }
  
  .item-card {
    padding: var(--space-3) var(--space-4);
    border-top: 1px solid var(--border-color);
    transition: background var(--transition-fast);
  }
  
  .item-card:hover {
    background: var(--bg-secondary);
  }
  
  .item-main {
    font-size: var(--text-sm);
    color: var(--text-primary);
    line-height: 1.5;
  }
  
  .item-detail {
    font-size: var(--text-xs);
    color: var(--text-secondary);
    margin-top: var(--space-2);
    line-height: 1.5;
  }
  
  .failure-reason {
    color: var(--error);
    opacity: 0.9;
  }
  
  .reason-label {
    font-weight: 500;
  }
  
  .item-meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin-top: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .meta-tag {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
  }
  
  .meta-date {
    opacity: 0.7;
  }
  
  .meta-file {
    font-family: var(--font-mono);
    opacity: 0.7;
  }
  
  .confidence {
    color: var(--success);
    opacity: calc(0.5 + var(--confidence) * 0.5);
  }
  
  /* Category colors */
  .category-framework { background: rgba(96, 165, 250, 0.2); color: #60a5fa; }
  .category-database { background: rgba(52, 211, 153, 0.2); color: #34d399; }
  .category-testing { background: rgba(251, 191, 36, 0.2); color: #fbbf24; }
  .category-pattern { background: rgba(167, 139, 250, 0.2); color: #a78bfa; }
  .category-tool { background: rgba(244, 114, 182, 0.2); color: #f472b6; }
  .category-language { background: rgba(251, 146, 60, 0.2); color: #fb923c; }
  
  /* Empty States */
  .empty-message {
    padding: var(--space-4);
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    font-style: italic;
  }
  
  .empty-state {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: var(--space-8);
    text-align: center;
    color: var(--text-tertiary);
  }
  
  .empty-icon {
    font-size: var(--text-2xl);
    font-family: var(--font-mono);
    margin-bottom: var(--space-2);
    opacity: 0.5;
  }
  
  .empty-hint {
    font-size: var(--text-sm);
    opacity: 0.7;
    margin-top: var(--space-1);
  }
  
  /* Scrollbar styling */
  .memory-view::-webkit-scrollbar,
  .item-list::-webkit-scrollbar {
    width: 6px;
  }
  
  .memory-view::-webkit-scrollbar-track,
  .item-list::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .memory-view::-webkit-scrollbar-thumb,
  .item-list::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 3px;
  }
  
  .memory-view::-webkit-scrollbar-thumb:hover,
  .item-list::-webkit-scrollbar-thumb:hover {
    background: var(--text-tertiary);
  }
</style>
