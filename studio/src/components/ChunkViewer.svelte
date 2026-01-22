<!--
  ChunkViewer — Visualize chunk hierarchy (Svelte 5, RFC-084)
  
  Shows the three-tier memory hierarchy:
  - HOT: Most recent chunks with full content
  - WARM: CTF-encoded chunks with summaries
  - COLD: Archive chunks with summaries only
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { ChunkHierarchy, Chunk } from '$lib/types';
  
  interface Props {
    projectPath: string;
  }
  
  let { projectPath }: Props = $props();
  
  // State
  let hierarchy: ChunkHierarchy = $state({ hot: [], warm: [], cold: [] });
  let selectedChunk: Chunk | null = $state(null);
  let loading = $state(false);
  let error = $state<string | null>(null);
  
  // Load chunks when project path changes
  $effect(() => {
    if (projectPath) {
      loadChunks();
    }
  });
  
  async function loadChunks() {
    loading = true;
    error = null;
    
    try {
      hierarchy = await invoke<ChunkHierarchy>('get_chunk_hierarchy', { 
        path: projectPath 
      });
    } catch (e) {
      console.warn('Failed to load chunks:', e);
      error = String(e);
      hierarchy = { hot: [], warm: [], cold: [] };
    } finally {
      loading = false;
    }
  }
  
  function selectChunk(chunk: Chunk) {
    selectedChunk = selectedChunk?.id === chunk.id ? null : chunk;
  }
  
  function formatTurnRange(chunk: Chunk): string {
    return `T${chunk.turnRange[0]}–${chunk.turnRange[1]}`;
  }
  
  function formatTokenCount(count: number): string {
    if (count >= 1000) {
      return `${(count / 1000).toFixed(1)}k`;
    }
    return String(count);
  }
  
  // Total stats
  let totalChunks = $derived(
    hierarchy.hot.length + hierarchy.warm.length + hierarchy.cold.length
  );
  let totalTokens = $derived(
    [...hierarchy.hot, ...hierarchy.warm, ...hierarchy.cold]
      .reduce((sum, c) => sum + c.tokenCount, 0)
  );
</script>

<div class="chunk-viewer">
  <!-- Header with stats -->
  <div class="header">
    <h4>Memory Hierarchy</h4>
    <div class="stats">
      <span class="stat">{totalChunks} chunks</span>
      <span class="stat">{formatTokenCount(totalTokens)} tokens</span>
    </div>
  </div>
  
  {#if loading}
    <div class="loading">Loading chunks...</div>
  {:else if error}
    <div class="error">{error}</div>
  {:else}
    <div class="tiers">
      <!-- HOT Tier -->
      <div class="tier tier-hot">
        <div class="tier-header">
          <span class="tier-icon">🔥</span>
          <span class="tier-name">HOT</span>
          <span class="tier-count">{hierarchy.hot.length}</span>
        </div>
        <div class="chunk-list">
          {#each hierarchy.hot as chunk (chunk.id)}
            <button 
              class="chunk-card"
              class:selected={selectedChunk?.id === chunk.id}
              onclick={() => selectChunk(chunk)}
              type="button"
            >
              <span class="turn-range">{formatTurnRange(chunk)}</span>
              <span class="token-count">{formatTokenCount(chunk.tokenCount)}</span>
            </button>
          {/each}
          {#if hierarchy.hot.length === 0}
            <div class="empty-tier">No hot chunks</div>
          {/if}
        </div>
      </div>
      
      <!-- WARM Tier -->
      <div class="tier tier-warm">
        <div class="tier-header">
          <span class="tier-icon">🌡️</span>
          <span class="tier-name">WARM</span>
          <span class="tier-count">{hierarchy.warm.length}</span>
        </div>
        <div class="chunk-list">
          {#each hierarchy.warm as chunk (chunk.id)}
            <button 
              class="chunk-card"
              class:selected={selectedChunk?.id === chunk.id}
              onclick={() => selectChunk(chunk)}
              type="button"
            >
              <span class="turn-range">{formatTurnRange(chunk)}</span>
              {#if chunk.summary}
                <span class="summary" title={chunk.summary}>
                  {chunk.summary.slice(0, 40)}...
                </span>
              {/if}
            </button>
          {/each}
          {#if hierarchy.warm.length === 0}
            <div class="empty-tier">No warm chunks</div>
          {/if}
        </div>
      </div>
      
      <!-- COLD Tier -->
      <div class="tier tier-cold">
        <div class="tier-header">
          <span class="tier-icon">❄️</span>
          <span class="tier-name">COLD</span>
          <span class="tier-count">{hierarchy.cold.length}</span>
        </div>
        <div class="chunk-list">
          {#each hierarchy.cold as chunk (chunk.id)}
            <button 
              class="chunk-card"
              class:selected={selectedChunk?.id === chunk.id}
              onclick={() => selectChunk(chunk)}
              type="button"
            >
              <span class="turn-range">{formatTurnRange(chunk)}</span>
              {#if chunk.themes.length > 0}
                <span class="themes">
                  {chunk.themes.slice(0, 3).join(', ')}
                </span>
              {/if}
            </button>
          {/each}
          {#if hierarchy.cold.length === 0}
            <div class="empty-tier">No cold chunks</div>
          {/if}
        </div>
      </div>
    </div>
    
    <!-- Detail panel for selected chunk -->
    {#if selectedChunk}
      <aside class="chunk-detail">
        <div class="detail-header">
          <h5>Chunk Details</h5>
          <button 
            class="close-btn" 
            onclick={() => selectedChunk = null}
            type="button"
            aria-label="Close details"
          >×</button>
        </div>
        
        <dl class="detail-list">
          <dt>ID</dt>
          <dd class="mono">{selectedChunk.id.slice(0, 20)}...</dd>
          
          <dt>Type</dt>
          <dd class="badge badge-{selectedChunk.chunkType}">
            {selectedChunk.chunkType}
          </dd>
          
          <dt>Turns</dt>
          <dd>{formatTurnRange(selectedChunk)}</dd>
          
          <dt>Tokens</dt>
          <dd>{selectedChunk.tokenCount.toLocaleString()}</dd>
          
          {#if selectedChunk.summary}
            <dt>Summary</dt>
            <dd class="summary-full">{selectedChunk.summary}</dd>
          {/if}
          
          {#if selectedChunk.keyFacts.length > 0}
            <dt>Key Facts</dt>
            <dd>
              <ul class="facts-list">
                {#each selectedChunk.keyFacts as fact}
                  <li>{fact}</li>
                {/each}
              </ul>
            </dd>
          {/if}
          
          {#if selectedChunk.themes.length > 0}
            <dt>Themes</dt>
            <dd class="themes-list">
              {#each selectedChunk.themes as theme}
                <span class="theme-tag">{theme}</span>
              {/each}
            </dd>
          {/if}
          
          {#if selectedChunk.timestampStart}
            <dt>Time Range</dt>
            <dd class="mono text-sm">
              {new Date(selectedChunk.timestampStart).toLocaleDateString()}
              {#if selectedChunk.timestampEnd}
                → {new Date(selectedChunk.timestampEnd).toLocaleDateString()}
              {/if}
            </dd>
          {/if}
        </dl>
      </aside>
    {/if}
  {/if}
</div>

<style>
  .chunk-viewer {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    height: 100%;
    overflow: hidden;
  }
  
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-color);
  }
  
  .header h4 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .stats {
    display: flex;
    gap: var(--space-3);
  }
  
  .stat {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
  
  .tiers {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    overflow-y: auto;
    flex: 1;
  }
  
  .tier {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    overflow: hidden;
  }
  
  .tier-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-2) var(--space-3);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }
  
  .tier-icon {
    font-size: 14px;
  }
  
  .tier-name {
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  
  .tier-count {
    margin-left: auto;
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    background: var(--bg-primary);
    padding: 2px 8px;
    border-radius: 10px;
  }
  
  .tier-hot .tier-header { border-left: 3px solid #ef4444; }
  .tier-warm .tier-header { border-left: 3px solid #fbbf24; }
  .tier-cold .tier-header { border-left: 3px solid #60a5fa; }
  
  .chunk-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    padding: var(--space-2);
    max-height: 120px;
    overflow-y: auto;
  }
  
  .chunk-card {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: var(--space-2);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    cursor: pointer;
    transition: all var(--transition-fast);
    text-align: left;
    min-width: 80px;
    font-size: var(--text-xs);
  }
  
  .chunk-card:hover {
    background: var(--bg-tertiary);
    border-color: var(--accent);
  }
  
  .chunk-card.selected {
    background: rgba(201, 162, 39, 0.1);
    border-color: var(--accent);
  }
  
  .turn-range {
    font-family: var(--font-mono);
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .token-count {
    color: var(--text-tertiary);
    font-family: var(--font-mono);
  }
  
  .summary {
    color: var(--text-secondary);
    font-size: var(--text-xs);
    max-width: 150px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .themes {
    color: var(--text-tertiary);
    font-style: italic;
    font-size: var(--text-xs);
  }
  
  .empty-tier {
    color: var(--text-tertiary);
    font-size: var(--text-xs);
    font-style: italic;
    padding: var(--space-2);
  }
  
  /* Detail Panel */
  .chunk-detail {
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    background: var(--bg-secondary);
    padding: var(--space-3);
    max-height: 250px;
    overflow-y: auto;
  }
  
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: var(--space-3);
  }
  
  .detail-header h5 {
    margin: 0;
    font-size: var(--text-sm);
    font-weight: 600;
  }
  
  .close-btn {
    background: none;
    border: none;
    color: var(--text-tertiary);
    cursor: pointer;
    font-size: 18px;
    padding: 0 4px;
    line-height: 1;
  }
  
  .close-btn:hover {
    color: var(--text-primary);
  }
  
  .detail-list {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-2) var(--space-3);
    font-size: var(--text-xs);
  }
  
  .detail-list dt {
    color: var(--text-tertiary);
    font-weight: 500;
  }
  
  .detail-list dd {
    color: var(--text-primary);
    margin: 0;
  }
  
  .mono {
    font-family: var(--font-mono);
  }
  
  .text-sm {
    font-size: var(--text-xs);
  }
  
  .badge {
    display: inline-block;
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    text-transform: uppercase;
    font-size: 10px;
    font-weight: 600;
  }
  
  .badge-micro { background: #ef444420; color: #ef4444; }
  .badge-mini { background: #fbbf2420; color: #fbbf24; }
  .badge-macro { background: #60a5fa20; color: #60a5fa; }
  
  .summary-full {
    line-height: 1.5;
  }
  
  .facts-list {
    list-style: disc;
    margin: 0;
    padding-left: var(--space-4);
  }
  
  .facts-list li {
    margin-bottom: 2px;
  }
  
  .themes-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  
  .theme-tag {
    background: var(--bg-tertiary);
    padding: 2px 6px;
    border-radius: var(--radius-sm);
    font-size: 10px;
  }
  
  .loading, .error {
    padding: var(--space-4);
    text-align: center;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .error {
    color: var(--error);
  }
  
  /* Scrollbar styling */
  .tiers::-webkit-scrollbar,
  .chunk-list::-webkit-scrollbar,
  .chunk-detail::-webkit-scrollbar {
    width: 6px;
  }
  
  .tiers::-webkit-scrollbar-track,
  .chunk-list::-webkit-scrollbar-track,
  .chunk-detail::-webkit-scrollbar-track {
    background: transparent;
  }
  
  .tiers::-webkit-scrollbar-thumb,
  .chunk-list::-webkit-scrollbar-thumb,
  .chunk-detail::-webkit-scrollbar-thumb {
    background: var(--border-color);
    border-radius: 3px;
  }
</style>
