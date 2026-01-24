<!--
  IndexStatus.svelte — Index status pill and popover (RFC-108)
  
  Shows current index state in the header with expandable details.
-->
<script lang="ts">
  import { indexingStore, rebuildIndex } from '../stores/indexing.svelte';
  import { fade } from 'svelte/transition';
  
  let showPopover = $state(false);
  let popoverTimeout: number | null = null;
  
  function handleMouseEnter() {
    popoverTimeout = window.setTimeout(() => {
      showPopover = true;
    }, 300);
  }
  
  function handleMouseLeave() {
    if (popoverTimeout) {
      clearTimeout(popoverTimeout);
    }
    showPopover = false;
  }
  
  function handleClick() {
    if (indexingStore.status.state === 'error' || indexingStore.status.state === 'degraded') {
      rebuildIndex();
    }
  }
</script>

<button 
  type="button"
  class="index-status"
  class:ready={indexingStore.isReady}
  class:building={indexingStore.isBuilding}
  class:degraded={indexingStore.isDegraded}
  class:error={indexingStore.status.state === 'error'}
  onmouseenter={handleMouseEnter}
  onmouseleave={handleMouseLeave}
  onclick={handleClick}
  aria-label={indexingStore.statusLabel}
>
  <span class="icon" class:spinning={indexingStore.isBuilding}>
    {indexingStore.statusIcon}
  </span>
  <span class="label">{indexingStore.statusLabel}</span>
  
  {#if indexingStore.isBuilding && indexingStore.status.progress}
    <div class="progress-bar">
      <div 
        class="progress-fill" 
        style="width: {indexingStore.status.progress}%"
      ></div>
    </div>
  {/if}
</button>

{#if showPopover}
  <div class="popover" transition:fade={{ duration: 150 }}>
    <div class="popover-header">
      <span class="popover-icon">{indexingStore.statusIcon}</span>
      <span class="popover-title">Codebase Index</span>
    </div>
    
    <div class="popover-body">
      {#if indexingStore.isReady}
        <div class="stat">
          <span class="stat-label">Chunks</span>
          <span class="stat-value">{indexingStore.status.chunkCount?.toLocaleString()}</span>
        </div>
        <div class="stat">
          <span class="stat-label">Files</span>
          <span class="stat-value">{indexingStore.status.fileCount?.toLocaleString()}</span>
        </div>
        {#if indexingStore.status.projectType}
          <div class="stat">
            <span class="stat-label">Project Type</span>
            <span class="stat-value">{indexingStore.status.projectType}</span>
          </div>
        {/if}
        {#if indexingStore.status.lastUpdated}
          <div class="stat">
            <span class="stat-label">Updated</span>
            <span class="stat-value">{new Date(indexingStore.status.lastUpdated).toLocaleString()}</span>
          </div>
        {/if}
      {:else if indexingStore.isBuilding}
        <div class="building-info">
          <p>Indexing in progress...</p>
          {#if indexingStore.status.currentFile}
            <p class="current-file">{indexingStore.status.currentFile}</p>
          {/if}
          {#if indexingStore.status.priorityComplete}
            <p class="hint">✓ Priority files indexed, search available</p>
          {/if}
        </div>
      {:else if indexingStore.isDegraded}
        <div class="degraded-info">
          <p>Running in fallback mode</p>
          <p class="reason">{indexingStore.status.fallbackReason}</p>
          <button class="retry-btn" onclick={() => rebuildIndex()}>
            Retry with embeddings
          </button>
        </div>
      {:else if indexingStore.status.state === 'error'}
        <div class="error-info">
          <p>Indexing failed</p>
          <p class="error">{indexingStore.status.error}</p>
          <button class="retry-btn" onclick={() => rebuildIndex()}>
            Retry
          </button>
        </div>
      {:else}
        <div class="no-index-info">
          <p>No index available</p>
          <p class="hint">Open a project to start indexing</p>
        </div>
      {/if}
    </div>
    
    <div class="popover-footer">
      <button class="action-btn" onclick={() => rebuildIndex()}>
        Rebuild Index
      </button>
    </div>
  </div>
{/if}

<style>
  .index-status {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border: none;
    border-radius: 6px;
    font-family: inherit;
    font-size: 12px;
    font-weight: 500;
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    cursor: pointer;
    transition: all 0.2s ease;
    position: relative;
  }
  
  .index-status:hover {
    background: var(--bg-hover);
  }
  
  .index-status.ready {
    background: color-mix(in srgb, var(--success) 15%, transparent);
    color: var(--success);
  }
  
  .index-status.building {
    background: color-mix(in srgb, var(--info) 15%, transparent);
    color: var(--info);
  }
  
  .index-status.degraded {
    background: color-mix(in srgb, var(--warning) 15%, transparent);
    color: var(--warning);
  }
  
  .index-status.error {
    background: color-mix(in srgb, var(--error) 15%, transparent);
    color: var(--error);
  }
  
  .icon {
    font-size: 14px;
  }
  
  .icon.spinning {
    animation: spin 1s linear infinite;
  }
  
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  
  .progress-bar {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--bg-secondary);
    border-radius: 0 0 6px 6px;
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--info);
    transition: width 0.3s ease;
  }
  
  .popover {
    position: absolute;
    top: calc(100% + 8px);
    right: 0;
    width: 280px;
    background: var(--bg-elevated);
    border: 1px solid var(--border);
    border-radius: 8px;
    box-shadow: var(--shadow-lg);
    z-index: 100;
  }
  
  .popover-header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }
  
  .popover-title {
    font-weight: 600;
    color: var(--text-primary);
  }
  
  .popover-body {
    padding: 12px 16px;
  }
  
  .stat {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
  }
  
  .stat-label {
    color: var(--text-secondary);
  }
  
  .stat-value {
    font-weight: 500;
    color: var(--text-primary);
  }
  
  .current-file {
    font-size: 11px;
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .hint {
    font-size: 11px;
    color: var(--success);
    margin-top: 8px;
  }
  
  .reason, .error {
    font-size: 11px;
    color: var(--text-tertiary);
    margin-top: 4px;
  }
  
  .error {
    color: var(--error);
  }
  
  .retry-btn, .action-btn {
    margin-top: 8px;
    padding: 6px 12px;
    font-size: 12px;
    border-radius: 4px;
    border: none;
    cursor: pointer;
    transition: background 0.2s;
  }
  
  .retry-btn {
    background: var(--info);
    color: white;
  }
  
  .popover-footer {
    padding: 8px 16px;
    border-top: 1px solid var(--border);
  }
  
  .action-btn {
    width: 100%;
    background: var(--bg-secondary);
    color: var(--text-secondary);
  }
  
  .action-btn:hover {
    background: var(--bg-hover);
  }

  .building-info p,
  .degraded-info p,
  .error-info p,
  .no-index-info p {
    margin: 0 0 4px 0;
  }
</style>
