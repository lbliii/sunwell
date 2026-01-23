<!--
  Planning — DAG-based task visualization (Svelte 5)
  
  Shows the project's task graph with interactive navigation.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { dag, loadDemoGraph, setGraph } from '../stores/dag.svelte';
  import { goHome } from '../stores/app.svelte';
  import { project } from '../stores/project.svelte';
  import type { DagGraph } from '$lib/types';
  
  let canvas: DagCanvas;
  let isLoading = $state(false);
  
  $effect(() => {
    untrack(() => { loadDag(); });
    const handleVisibilityChange = () => { if (!document.hidden) loadDag(); };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    return () => { document.removeEventListener('visibilitychange', handleVisibilityChange); };
  });
  
  async function loadDag() {
    // Prevent concurrent loads
    if (isLoading) return;
    
    if (project.current?.path) {
      isLoading = true;
      try {
        const graph = await invoke<DagGraph>('get_project_dag', { path: project.current.path });
        setGraph(graph);
      } catch (e) {
        console.error('Failed to load DAG:', e);
        if (dag.nodes.length === 0) loadDemoGraph();
      } finally {
        isLoading = false;
      }
    } else {
      if (dag.nodes.length === 0) loadDemoGraph();
    }
  }
  
  function handleFitView() { canvas?.fitToView(); }
  function handleRefresh() { loadDag(); setTimeout(() => canvas?.fitToView(), 100); }
  function handleBack() { goHome(); }
</script>

<div class="planning">
  <header class="header">
    <button class="back-btn" onclick={handleBack}>
      ← {project.current?.name ?? 'Planning'}
    </button>
    
    <div class="header-center">
      {#if dag.goal}
        <span class="goal-text">{dag.goal}</span>
      {:else}
        <span class="goal-text muted">Task Pipeline</span>
      {/if}
    </div>
    
    <div class="header-right">
      <span class="node-count">
        {dag.nodes.filter(n => n.status === 'complete').length}/{dag.nodes.length} tasks
      </span>
    </div>
  </header>
  
  <DagControls onFitView={handleFitView} onRefresh={handleRefresh} />
  
  <main class="content">
    <div class="canvas-container">
      <DagCanvas bind:this={canvas} />
    </div>
    
    {#if dag.selectedNode}
      <DagDetail />
    {/if}
  </main>
</div>

<style>
  .planning { display: flex; flex-direction: column; height: 100vh; background: var(--bg-primary); }
  .header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color); background: var(--bg-secondary); }
  .back-btn { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--text-sm); padding: var(--space-1) 0; transition: color var(--transition-fast); }
  .back-btn:hover { color: var(--text-primary); }
  .header-center { flex: 1; text-align: center; }
  .goal-text { font-family: var(--font-mono); font-size: var(--text-sm); color: var(--text-primary); }
  .goal-text.muted { color: var(--text-tertiary); }
  .header-right { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-tertiary); }
  .node-count { padding: 4px 8px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
  .content { flex: 1; display: flex; min-height: 0; /* Removed overflow:hidden - clips menus */ }
  .canvas-container { flex: 1; position: relative; }
</style>
