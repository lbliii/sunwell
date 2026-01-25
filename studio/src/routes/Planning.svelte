<!--
  Planning — DAG-based task visualization (Svelte 5)
  
  RFC-105: Updated to use hierarchical DAG with index-based fast loading.
  Shows the project's task graph with interactive navigation.
-->
<script lang="ts">
  /**
   * Planning — DAG-based task visualization (Svelte 5)
   * RFC-113: Uses HTTP API instead of Tauri for all communication.
   */
  import { untrack } from 'svelte';
  import { apiGet } from '$lib/socket';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { 
    dag, 
    setGraph, 
    loadProjectDagIndex,
    loadWorkspaceDag,
    setViewLevel,
    getSortedGoals,
    expandGoal,
  } from '../stores/dag.svelte';
  import { goHome } from '../stores/app.svelte';
  import { project } from '../stores/project.svelte';
  import type { DagGraph, DagViewLevel, GoalSummary } from '$lib/types';
  
  let canvas = $state<DagCanvas | null>(null);
  let isLoading = $state(false);
  
  // Pre-compute completed node count to avoid O(n) filter in template
  const completedNodeCount = $derived(dag.nodes.filter(n => n.status === 'complete').length);
  
  // RFC-105: View level tabs (readonly to prevent mutation)
  const viewLevels = [
    { id: 'project', label: 'Project', icon: '📁' },
    { id: 'workspace', label: 'Workspace', icon: '🗂️' },
    { id: 'environment', label: 'Environment', icon: '🌐' },
  ] as const satisfies readonly { id: DagViewLevel; label: string; icon: string }[];

  // Pre-computed sorted goals (avoid function call in template)
  const sortedGoals = $derived(getSortedGoals());
  
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
        // RFC-105: Load both index (fast) and full graph (for canvas)
        await loadProjectDagIndex(project.current.path);
        
        // Also load full graph for canvas visualization (RFC-113: HTTP API)
        const graph = await apiGet<DagGraph>(`/api/dag?path=${encodeURIComponent(project.current.path)}`);
        if (graph) {
          setGraph(graph);
        }
      } catch (e) {
        console.error('Failed to load DAG:', e);
        // Don't fallback to demo - show empty state instead
      } finally {
        isLoading = false;
      }
    }
    // No demo fallback - let the empty state show
  }
  
  // RFC-105: Handle view level change
  function handleViewLevelChange(level: DagViewLevel) {
    setViewLevel(level);
    if (level === 'workspace' && project.current?.path) {
      // Get parent directory as workspace
      const parts = project.current.path.split('/');
      parts.pop();
      const workspacePath = parts.join('/');
      loadWorkspaceDag(workspacePath);
    }
  }
  
  // RFC-105: Handle goal expansion
  async function handleGoalClick(goal: GoalSummary) {
    const details = await expandGoal(goal.id);
    if (details) {
      console.log('Goal expanded:', details);
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
      <!-- RFC-105: View level tabs -->
      <div class="view-level-tabs">
        {#each viewLevels as level (level.id)}
          <button 
            class="level-tab" 
            class:active={dag.viewLevel === level.id}
            onclick={() => handleViewLevelChange(level.id)}
          >
            <span class="level-icon">{level.icon}</span>
            <span class="level-label">{level.label}</span>
          </button>
        {/each}
      </div>
    </div>
    
    <div class="header-right">
      {#if dag.projectIndex}
        <span class="node-count">
          {dag.projectIndex.summary.completedGoals}/{dag.projectIndex.summary.totalGoals} goals
        </span>
      {:else}
        <span class="node-count">
          {completedNodeCount}/{dag.nodes.length} tasks
        </span>
      {/if}
    </div>
  </header>
  
  <DagControls onFitView={handleFitView} onRefresh={handleRefresh} />
  
  <main class="content">
    {#if dag.viewLevel === 'project'}
      <!-- RFC-105: Project view with goal list sidebar -->
      <div class="project-view">
        {#if dag.projectIndex && dag.projectIndex.goals.length > 0}
          <aside class="goals-sidebar">
            <h3 class="sidebar-title">Goals ({dag.projectIndex.summary.totalGoals})</h3>
            <ul class="goals-list">
              {#each sortedGoals as goal (goal.id)}
                <li class="goal-item" class:complete={goal.status === 'complete'}>
                  <button class="goal-btn" onclick={() => handleGoalClick(goal)}>
                    <span class="goal-status">
                      {#if goal.status === 'complete'}✓
                      {:else if goal.status === 'running' || goal.status === 'in_progress'}◐
                      {:else if goal.status === 'failed'}✗
                      {:else}○{/if}
                    </span>
                    <span class="goal-title">{goal.title}</span>
                    <span class="goal-tasks">{goal.taskCount} tasks</span>
                  </button>
                </li>
              {/each}
            </ul>
          </aside>
        {/if}
        
        <div class="canvas-container">
          <DagCanvas bind:this={canvas} />
        </div>
      </div>
      
    {:else if dag.viewLevel === 'workspace'}
      <!-- RFC-105: Workspace view showing all projects -->
      <div class="workspace-view">
        {#if dag.isLoadingWorkspace}
          <div class="loading-state">Loading workspace...</div>
        {:else if dag.workspaceIndex}
          <div class="projects-grid">
            {#each dag.workspaceIndex.projects as proj (proj.path)}
              <div class="project-card">
                <h4 class="project-name">{proj.name}</h4>
                <div class="project-progress">
                  <div class="progress-bar">
                    <div 
                      class="progress-fill" 
                      style="width: {proj.summary.totalGoals ? (proj.summary.completedGoals / proj.summary.totalGoals * 100) : 0}%"
                    ></div>
                  </div>
                  <span class="progress-text">
                    {proj.summary.completedGoals}/{proj.summary.totalGoals} goals
                  </span>
                </div>
                <div class="project-stack">
                  {#each proj.techStack as tech (tech)}
                    <span class="tech-badge">{tech}</span>
                  {/each}
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <div class="empty-state">No workspace data available</div>
        {/if}
      </div>
      
    {:else}
      <!-- Environment view placeholder -->
      <div class="environment-view">
        <div class="empty-state">Environment view coming soon</div>
      </div>
    {/if}
    
    {#if dag.selectedNode && dag.viewLevel === 'project'}
      <DagDetail />
    {/if}
  </main>
</div>

<style>
  .planning { display: flex; flex-direction: column; height: 100vh; background: var(--bg-primary); }
  .header { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--border-color); background: var(--bg-secondary); }
  .back-btn { color: var(--text-secondary); font-family: var(--font-mono); font-size: var(--text-sm); padding: var(--space-1) 0; transition: color var(--transition-fast); }
  .back-btn:hover { color: var(--text-primary); }
  .header-center { flex: 1; display: flex; justify-content: center; }
  .header-right { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-tertiary); }
  .node-count { padding: 4px 8px; background: var(--bg-tertiary); border-radius: var(--radius-sm); }
  .content { flex: 1; display: flex; min-height: 0; }
  .canvas-container { flex: 1; position: relative; }
  
  /* RFC-105: View level tabs */
  .view-level-tabs { display: flex; gap: 4px; background: var(--bg-tertiary); padding: 4px; border-radius: var(--radius-md); }
  .level-tab { 
    display: flex; 
    align-items: center; 
    gap: 6px; 
    padding: 6px 12px; 
    border-radius: var(--radius-sm); 
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    color: var(--text-tertiary); 
    transition: all var(--transition-fast);
  }
  .level-tab:hover { color: var(--text-secondary); background: var(--bg-secondary); }
  .level-tab.active { color: var(--text-primary); background: var(--bg-primary); box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .level-icon { font-size: var(--text-sm); }
  .level-label { font-weight: 500; }
  
  /* RFC-105: Project view with sidebar */
  .project-view { display: flex; flex: 1; min-height: 0; }
  
  .goals-sidebar { 
    width: 260px; 
    border-right: 1px solid var(--border-color); 
    background: var(--bg-secondary); 
    display: flex; 
    flex-direction: column;
    overflow: hidden;
  }
  .sidebar-title { 
    padding: 12px 16px; 
    margin: 0; 
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    font-weight: 600; 
    color: var(--text-tertiary); 
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-color);
  }
  .goals-list { list-style: none; margin: 0; padding: 8px; overflow-y: auto; flex: 1; }
  .goal-item { margin-bottom: 4px; }
  .goal-btn { 
    width: 100%; 
    display: flex; 
    align-items: center; 
    gap: 8px; 
    padding: 10px 12px; 
    border-radius: var(--radius-sm); 
    text-align: left;
    transition: background var(--transition-fast);
  }
  .goal-btn:hover { background: var(--bg-tertiary); }
  .goal-status { 
    flex-shrink: 0; 
    width: 18px; 
    height: 18px; 
    display: flex; 
    align-items: center; 
    justify-content: center;
    font-size: var(--text-sm); 
    color: var(--text-tertiary);
  }
  .goal-item.complete .goal-status { color: var(--success); }
  .goal-title { 
    flex: 1; 
    font-family: var(--font-mono); 
    font-size: var(--text-sm); 
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .goal-tasks { 
    flex-shrink: 0;
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    color: var(--text-tertiary);
  }
  
  /* RFC-105: Workspace view */
  .workspace-view { flex: 1; padding: 24px; overflow-y: auto; }
  .projects-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }
  .project-card { 
    background: var(--bg-secondary); 
    border: 1px solid var(--border-color); 
    border-radius: var(--radius-lg); 
    padding: 20px;
  }
  .project-name { 
    margin: 0 0 12px; 
    font-family: var(--font-mono); 
    font-size: var(--text-base); 
    font-weight: 600;
    color: var(--text-primary);
  }
  .project-progress { margin-bottom: 12px; }
  .progress-bar { 
    height: 6px; 
    background: var(--bg-tertiary); 
    border-radius: 3px; 
    overflow: hidden;
    margin-bottom: 6px;
  }
  .progress-fill { height: 100%; background: var(--accent); transition: width 0.3s ease; }
  .progress-text { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-tertiary); }
  .project-stack { display: flex; flex-wrap: wrap; gap: 6px; }
  .tech-badge { 
    padding: 2px 8px; 
    background: var(--bg-tertiary); 
    border-radius: var(--radius-sm); 
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    color: var(--text-secondary);
  }
  
  /* Environment view */
  .environment-view { flex: 1; display: flex; align-items: center; justify-content: center; }
  
  /* States */
  .loading-state, .empty-state { 
    flex: 1; 
    display: flex; 
    align-items: center; 
    justify-content: center; 
    font-family: var(--font-mono); 
    font-size: var(--text-sm); 
    color: var(--text-tertiary); 
  }
</style>
