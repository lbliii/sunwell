<!--
  ConflictPanel — File conflict display and resolution (RFC-100 Phase 4)
  
  Shows conflicts between workers with diff view and resolution options.
-->
<script lang="ts">
  import type { FileConflict } from '../../stores/coordinator.svelte';
  import DiffView from '../primitives/DiffView.svelte';
  
  interface Props {
    conflicts: FileConflict[];
    onResolve?: (conflict: FileConflict, resolution: string) => void;
  }
  
  let { conflicts, onResolve }: Props = $props();
  
  let selectedConflict = $state<FileConflict | null>(null);
  
  function formatTime(isoString: string): string {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return date.toLocaleDateString();
  }
  
  function handleResolve(resolution: string) {
    if (selectedConflict && onResolve) {
      onResolve(selectedConflict, resolution);
      selectedConflict = null;
    }
  }
</script>

{#if conflicts.length > 0}
  <div class="conflict-panel">
    <div class="panel-header">
      <span class="warning-icon">⚠️</span>
      <h3>Conflicts Detected ({conflicts.length})</h3>
    </div>
    
    <div class="conflict-list">
      {#each conflicts as conflict (conflict.path)}
        <button 
          class="conflict-item"
          class:selected={selectedConflict?.path === conflict.path}
          onclick={() => selectedConflict = conflict}
        >
          <div class="conflict-path">{conflict.path}</div>
          <div class="conflict-meta">
            <span class="workers">
              Worker {conflict.worker_a} ↔ Worker {conflict.worker_b}
            </span>
            <span class="time">{formatTime(conflict.detected_at)}</span>
          </div>
          {#if conflict.resolution}
            <div class="resolution-badge">{conflict.resolution}</div>
          {/if}
        </button>
      {/each}
    </div>
    
    {#if selectedConflict}
      <div class="conflict-detail">
        <div class="detail-header">
          <h4>{selectedConflict.path}</h4>
          <button class="close-btn" onclick={() => selectedConflict = null}>×</button>
        </div>
        
        <div class="conflict-type">
          Type: {selectedConflict.conflict_type.replace('_', ' ')}
        </div>
        
        <div class="resolution-actions">
          <button class="resolve-btn" onclick={() => handleResolve('pause_worker_b')}>
            ⏸ Pause Worker {selectedConflict.worker_b}
          </button>
          <button class="resolve-btn" onclick={() => handleResolve('auto_merge')}>
            🔀 Auto-merge
          </button>
          <button class="resolve-btn secondary" onclick={() => handleResolve('manual')}>
            ✏️ Manual Resolution
          </button>
        </div>
      </div>
    {/if}
  </div>
{/if}

<style>
  .conflict-panel {
    background: color-mix(in srgb, var(--warning) 5%, var(--bg-secondary));
    border: 1px solid var(--warning);
    border-radius: 12px;
    padding: 16px;
  }
  
  .panel-header {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 12px;
  }
  
  .panel-header h3 {
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: var(--warning);
  }
  
  .warning-icon {
    font-size: 16px;
  }
  
  .conflict-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  
  .conflict-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: 8px;
    cursor: pointer;
    transition: all 0.15s ease;
    text-align: left;
    width: 100%;
  }
  
  .conflict-item:hover {
    border-color: var(--warning);
  }
  
  .conflict-item.selected {
    border-color: var(--warning);
    background: color-mix(in srgb, var(--warning) 10%, var(--bg-primary));
  }
  
  .conflict-path {
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .conflict-meta {
    display: flex;
    gap: 12px;
    font-size: 11px;
    color: var(--text-tertiary);
  }
  
  .resolution-badge {
    display: inline-block;
    padding: 2px 8px;
    background: var(--success);
    color: var(--bg-primary);
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    margin-top: 4px;
  }
  
  .conflict-detail {
    margin-top: 16px;
    padding-top: 16px;
    border-top: 1px solid var(--border-color);
  }
  
  .detail-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 12px;
  }
  
  .detail-header h4 {
    margin: 0;
    font-family: var(--font-mono);
    font-size: 13px;
    color: var(--text-primary);
  }
  
  .close-btn {
    background: none;
    border: none;
    font-size: 18px;
    color: var(--text-tertiary);
    cursor: pointer;
    padding: 0;
    line-height: 1;
  }
  
  .close-btn:hover {
    color: var(--text-primary);
  }
  
  .conflict-type {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 12px;
  }
  
  .resolution-actions {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
  }
  
  .resolve-btn {
    padding: 8px 12px;
    background: var(--warning);
    color: var(--bg-primary);
    border: none;
    border-radius: 6px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s ease;
  }
  
  .resolve-btn:hover {
    filter: brightness(1.1);
  }
  
  .resolve-btn.secondary {
    background: var(--bg-tertiary);
    color: var(--text-secondary);
    border: 1px solid var(--border-color);
  }
  
  .resolve-btn.secondary:hover {
    background: var(--bg-primary);
    border-color: var(--text-tertiary);
  }
</style>
