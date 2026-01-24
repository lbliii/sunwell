<!--
  DagControls — Zoom, pan, and view controls for the DAG (Svelte 5)
  
  RFC-074: Extended with incremental execution plan controls.
-->
<script lang="ts">
  import { apiGet, apiPost } from '$lib/socket';
  import { dag, setZoom, resetView, toggleShowCompleted, setIncrementalPlan, setPlanLoading, setPlanError, clearIncrementalPlan } from '../../stores/dag.svelte';
  import { project } from '../../stores/project.svelte';
  import type { IncrementalPlan } from '$lib/types';
  
  interface Props {
    onFitView?: () => void;
    onRefresh?: () => void;
  }
  
  let { onFitView = () => {}, onRefresh = () => {} }: Props = $props();
  
  // RFC-074: Derived state for plan summary
  let hasIncrementalPlan = $derived(dag.incrementalPlan !== null);
  let toExecuteCount = $derived(dag.incrementalPlan?.toExecute.length ?? 0);
  let toSkipCount = $derived(dag.incrementalPlan?.toSkip.length ?? 0);
  let skipPercentage = $derived(dag.skipPercentage);
  
  function zoomIn() { setZoom(dag.zoom + 0.1); }
  function zoomOut() { setZoom(dag.zoom - 0.1); }
  function handleFit() { onFitView(); }
  function handleRefresh() { onRefresh(); }
  
  // RFC-074: Load incremental execution plan
  // RFC-113: Uses HTTP API instead of Tauri invoke
  async function handlePlan() {
    const projectPath = project.current?.path;
    if (!projectPath) {
      setPlanError('No project selected');
      return;
    }
    
    setPlanLoading(true);
    
    try {
      const plan = await apiGet<IncrementalPlan>(`/api/dag/plan?path=${encodeURIComponent(projectPath)}`);
      if (plan) {
        setIncrementalPlan(plan);
      }
    } catch (e) {
      console.error('Failed to get plan:', e);
      setPlanError(e instanceof Error ? e.message : String(e));
    }
  }
  
  function handleClearPlan() {
    clearIncrementalPlan();
  }
</script>

<div class="dag-controls">
  <div class="progress-indicator">
    <span class="progress-label">Progress</span>
    <div class="progress-bar" role="progressbar" aria-valuenow={dag.totalProgress} aria-valuemin={0} aria-valuemax={100}>
      <div class="progress-fill" style="width: {dag.totalProgress}%"></div>
    </div>
    <span class="progress-value">{dag.totalProgress}%</span>
  </div>
  
  <div class="divider"></div>
  
  <!-- RFC-074: Incremental execution plan controls -->
  <button 
    class="control-btn plan-btn" 
    class:active={hasIncrementalPlan}
    onclick={hasIncrementalPlan ? handleClearPlan : handlePlan} 
    title={hasIncrementalPlan ? "Clear plan" : "Show execution plan"}
    disabled={dag.isPlanLoading}
  >
    {#if dag.isPlanLoading}
      ⏳
    {:else if hasIncrementalPlan}
      ✕
    {:else}
      📋
    {/if}
    <span class="plan-btn-label">Plan</span>
  </button>
  
  {#if hasIncrementalPlan}
    <div class="plan-summary">
      <span class="plan-skip" title="Will skip (cached)">● {toSkipCount}</span>
      <span class="plan-exec" title="Will execute">○ {toExecuteCount}</span>
      <span class="plan-savings">({Math.round(skipPercentage)}% saved)</span>
    </div>
  {/if}
  
  {#if dag.planError}
    <span class="plan-error" title={dag.planError}>⚠️</span>
  {/if}
  
  <div class="divider"></div>
  
  <div class="zoom-controls">
    <button class="control-btn" onclick={zoomOut} title="Zoom out" aria-label="Zoom out">−</button>
    <span class="zoom-value">{Math.round(dag.zoom * 100)}%</span>
    <button class="control-btn" onclick={zoomIn} title="Zoom in" aria-label="Zoom in">+</button>
  </div>
  
  <button class="control-btn" onclick={handleFit} title="Fit to view" aria-label="Fit to view">⊡</button>
  <button class="control-btn" onclick={resetView} title="Reset view" aria-label="Reset view">↺</button>
  
  <div class="divider"></div>
  
  <label class="toggle">
    <input type="checkbox" checked={dag.showCompleted} onchange={toggleShowCompleted} aria-label="Show completed tasks" />
    <span>Show completed</span>
  </label>
  
  <button class="control-btn refresh" onclick={handleRefresh} title="Refresh" aria-label="Refresh DAG">🔄</button>
</div>

<style>
  .dag-controls { display: flex; align-items: center; gap: 12px; padding: 8px 16px; background: var(--bg-secondary); border-bottom: 1px solid var(--border-color); font-family: var(--font-mono); font-size: 12px; }
  .progress-indicator { display: flex; align-items: center; gap: 8px; }
  .progress-label { color: var(--text-secondary); }
  .progress-bar { width: 100px; height: 6px; background: var(--accent-muted); border-radius: 3px; overflow: hidden; }
  .progress-fill { height: 100%; background: var(--success); transition: width 0.3s ease; }
  .progress-value { color: var(--text-primary); font-weight: 600; min-width: 40px; }
  .divider { width: 1px; height: 20px; background: var(--border-color); }
  .zoom-controls { display: flex; align-items: center; gap: 4px; }
  .zoom-value { min-width: 45px; text-align: center; color: var(--text-secondary); }
  .control-btn { width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: var(--bg-tertiary); border: 1px solid var(--border-color); border-radius: var(--radius-sm); color: var(--text-primary); font-size: 14px; cursor: pointer; transition: all var(--transition-fast); }
  .control-btn:hover { background: var(--accent-muted); border-color: var(--text-tertiary); }
  .control-btn:disabled { opacity: 0.5; cursor: not-allowed; }
  .control-btn.refresh { font-size: 12px; }
  .toggle { display: flex; align-items: center; gap: 6px; color: var(--text-secondary); cursor: pointer; user-select: none; }
  .toggle input { appearance: none; width: 16px; height: 16px; border: 1px solid var(--border-color); border-radius: 3px; background: var(--bg-tertiary); cursor: pointer; position: relative; }
  .toggle input:checked { background: var(--accent); border-color: var(--accent); }
  .toggle input:checked::after { content: '✓'; position: absolute; inset: 0; display: flex; align-items: center; justify-content: center; color: var(--text-inverse); font-size: 11px; font-weight: bold; }
  
  /* RFC-074: Plan controls */
  .plan-btn { width: auto; padding: 0 8px; gap: 4px; }
  .plan-btn.active { background: var(--success-muted); border-color: var(--success); }
  .plan-btn-label { font-size: 11px; }
  
  .plan-summary { display: flex; align-items: center; gap: 8px; font-size: 11px; }
  .plan-skip { color: var(--success); font-weight: 600; }
  .plan-exec { color: var(--warning); font-weight: 600; }
  .plan-savings { color: var(--text-tertiary); }
  
  .plan-error { color: var(--error); cursor: help; }
</style>
