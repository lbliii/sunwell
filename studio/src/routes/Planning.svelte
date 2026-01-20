<!--
  Planning — DAG-based task visualization
  
  Shows the project's task graph with interactive navigation,
  progress tracking, and "what-if" analysis.
  
  RFC-056: Now loads real data from .sunwell/ when a project is open.
-->
<script lang="ts">
  import { onMount } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { 
    dagGraph, 
    dagViewState, 
    loadDemoGraph,
    setGraph,
    selectedNode,
    totalProgress 
  } from '../stores/dag';
  import { goHome } from '../stores/app';
  import { currentProject } from '../stores/project';
  import type { DagGraph } from '$lib/types';
  
  let canvas: DagCanvas;
  let isLoading = false;
  
  onMount(() => {
    loadDag();
    
    // RFC-056: Auto-refresh on tab focus
    const handleVisibilityChange = () => {
      if (!document.hidden) {
        loadDag();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  });
  
  async function loadDag() {
    // If we have a project, load real data
    if ($currentProject?.path) {
      isLoading = true;
      try {
        const graph = await invoke<DagGraph>('get_project_dag', {
          path: $currentProject.path
        });
        setGraph(graph);
      } catch (e) {
        console.error('Failed to load DAG:', e);
        // Fall back to demo if real data fails
        if ($dagGraph.nodes.length === 0) {
          loadDemoGraph();
        }
      } finally {
        isLoading = false;
      }
    } else {
      // No project selected, show demo
      if ($dagGraph.nodes.length === 0) {
        loadDemoGraph();
      }
    }
  }
  
  function handleFitView() {
    canvas?.fitToView();
  }
  
  function handleRefresh() {
    loadDag();
    setTimeout(() => canvas?.fitToView(), 100);
  }
  
  function handleBack() {
    goHome();
  }
</script>

<div class="planning">
  <!-- Header -->
  <header class="header">
    <button class="back-btn" on:click={handleBack}>
      ← {$currentProject?.name ?? 'Planning'}
    </button>
    
    <div class="header-center">
      {#if $dagGraph.goal}
        <span class="goal-text">{$dagGraph.goal}</span>
      {:else}
        <span class="goal-text muted">Task Pipeline</span>
      {/if}
    </div>
    
    <div class="header-right">
      <span class="node-count">
        {$dagGraph.nodes.filter(n => n.status === 'complete').length}/{$dagGraph.nodes.length} tasks
      </span>
    </div>
  </header>
  
  <!-- Controls -->
  <DagControls 
    onFitView={handleFitView}
    onRefresh={handleRefresh}
  />
  
  <!-- Main content -->
  <main class="content">
    <!-- DAG Canvas -->
    <div class="canvas-container">
      <DagCanvas bind:this={canvas} />
    </div>
    
    <!-- Detail Panel (shows when node selected) -->
    {#if $selectedNode}
      <DagDetail />
    {/if}
  </main>
  
  <!-- Floating hints when hovering -->
  {#if $dagViewState.hoveredNodeId && !$selectedNode}
    <div class="hover-hint">
      Click to see details • Shift+drag to pan • Scroll to zoom
    </div>
  {/if}
</div>

<style>
  .planning {
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--bg-primary);
  }
  
  /* Header */
  .header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-secondary);
  }
  
  .back-btn {
    color: var(--text-secondary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    padding: var(--space-1) 0;
    transition: color var(--transition-fast);
  }
  
  .back-btn:hover {
    color: var(--text-primary);
  }
  
  .header-center {
    flex: 1;
    text-align: center;
  }
  
  .goal-text {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
  }
  
  .goal-text.muted {
    color: var(--text-tertiary);
  }
  
  .header-right {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  .node-count {
    padding: 4px 8px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
  }
  
  /* Content */
  .content {
    flex: 1;
    display: flex;
    overflow: hidden;
  }
  
  .canvas-container {
    flex: 1;
    position: relative;
  }
  
  /* Hover hint */
  .hover-hint {
    position: fixed;
    bottom: 24px;
    left: 50%;
    transform: translateX(-50%);
    padding: 8px 16px;
    background: var(--bg-elevated);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    font-family: var(--font-mono);
    font-size: 11px;
    color: var(--text-tertiary);
    pointer-events: none;
    animation: fadeIn 0.2s ease;
  }
  
  @keyframes fadeIn {
    from { opacity: 0; transform: translateX(-50%) translateY(10px); }
    to { opacity: 1; transform: translateX(-50%) translateY(0); }
  }
</style>
