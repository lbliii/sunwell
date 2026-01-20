<!--
  DagControls — Zoom, pan, and view controls for the DAG
-->
<script lang="ts">
  import { dagViewState, setZoom, resetView, toggleShowCompleted, totalProgress } from '../../stores/dag';
  import Button from '../Button.svelte';
  
  export let onFitView: () => void = () => {};
  export let onRefresh: () => void = () => {};
  
  function zoomIn() {
    setZoom($dagViewState.zoom + 0.1);
  }
  
  function zoomOut() {
    setZoom($dagViewState.zoom - 0.1);
  }
  
  function handleFit() {
    onFitView();
  }
  
  function handleRefresh() {
    onRefresh();
  }
</script>

<div class="dag-controls">
  <!-- Progress indicator -->
  <div class="progress-indicator">
    <span class="progress-label">Progress</span>
    <div class="progress-bar">
      <div class="progress-fill" style="width: {$totalProgress}%"></div>
    </div>
    <span class="progress-value">{$totalProgress}%</span>
  </div>
  
  <!-- Divider -->
  <div class="divider"></div>
  
  <!-- Zoom controls -->
  <div class="zoom-controls">
    <button class="control-btn" on:click={zoomOut} title="Zoom out">−</button>
    <span class="zoom-value">{Math.round($dagViewState.zoom * 100)}%</span>
    <button class="control-btn" on:click={zoomIn} title="Zoom in">+</button>
  </div>
  
  <!-- View controls -->
  <button class="control-btn" on:click={handleFit} title="Fit to view">
    ⊡
  </button>
  
  <button class="control-btn" on:click={resetView} title="Reset view">
    ↺
  </button>
  
  <!-- Divider -->
  <div class="divider"></div>
  
  <!-- Toggle completed -->
  <label class="toggle">
    <input 
      type="checkbox" 
      checked={$dagViewState.showCompleted}
      on:change={toggleShowCompleted}
    />
    <span>Show completed</span>
  </label>
  
  <!-- Refresh -->
  <button class="control-btn refresh" on:click={handleRefresh} title="Refresh">
    🔄
  </button>
</div>

<style>
  .dag-controls {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 8px 16px;
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
    font-family: var(--font-mono);
    font-size: 12px;
  }
  
  .progress-indicator {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  
  .progress-label {
    color: var(--text-secondary);
  }
  
  .progress-bar {
    width: 100px;
    height: 6px;
    background: var(--accent-muted);
    border-radius: 3px;
    overflow: hidden;
  }
  
  .progress-fill {
    height: 100%;
    background: var(--success);
    transition: width 0.3s ease;
  }
  
  .progress-value {
    color: var(--text-primary);
    font-weight: 600;
    min-width: 40px;
  }
  
  .divider {
    width: 1px;
    height: 20px;
    background: var(--border-color);
  }
  
  .zoom-controls {
    display: flex;
    align-items: center;
    gap: 4px;
  }
  
  .zoom-value {
    min-width: 45px;
    text-align: center;
    color: var(--text-secondary);
  }
  
  .control-btn {
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-tertiary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-sm);
    color: var(--text-primary);
    font-size: 14px;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .control-btn:hover {
    background: var(--accent-muted);
    border-color: var(--text-tertiary);
  }
  
  .control-btn.refresh {
    font-size: 12px;
  }
  
  .toggle {
    display: flex;
    align-items: center;
    gap: 6px;
    color: var(--text-secondary);
    cursor: pointer;
    user-select: none;
  }
  
  .toggle input {
    appearance: none;
    width: 16px;
    height: 16px;
    border: 1px solid var(--border-color);
    border-radius: 3px;
    background: var(--bg-tertiary);
    cursor: pointer;
    position: relative;
  }
  
  .toggle input:checked {
    background: var(--accent);
    border-color: var(--accent);
  }
  
  .toggle input:checked::after {
    content: '✓';
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--text-inverse);
    font-size: 11px;
    font-weight: bold;
  }
</style>
