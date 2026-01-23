<!--
  Project — Working screen (Svelte 5, RFC-062 decomposed)
  
  Main project route that orchestrates state-specific sub-components.
  RFC-106: Unified Project Surface - Overview and Progress tabs merged into single Project tab.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import type { ProjectStatus, DagGraph, MemoryStats, IntelligenceData, GoalSummary } from '$lib/types';
  import { ViewTab } from '$lib/constants';
  import Button from '../components/Button.svelte';
  import Modal from '../components/Modal.svelte';
  import Tabs from '../components/Tabs.svelte';
  import Spinner from '../components/ui/Spinner.svelte';
  import { MemoryView } from '../components';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { WeaknessPanel, WaveExecutionPanel } from '../components/weakness';
  import { ProjectHeader, WorkingState, DoneState, ErrorState, IdleState } from '../components/project';
  import { ATCView, StateDagView } from '../components/coordinator';
  import { project } from '../stores/project.svelte';
  import { agent, runGoal } from '../stores/agent.svelte';
  import { dag, setGraph, setProjectPath, loadProjectDagIndex, getSortedGoals, expandGoal } from '../stores/dag.svelte';
  import { files, setFilesProjectPath } from '../stores/files.svelte';
  import { scanWeaknesses } from '../stores/weakness.svelte';
  
  // Project status for showing last run info
  let projectStatus = $state<ProjectStatus | null>(null);
  let isLoadingStatus = $state(false);
  
  // File preview state (files tree now managed by store)
  let selectedFile = $state<{ path: string; name: string; content: string } | null>(null);
  let isLoadingPreview = $state(false);
  
  // View tabs state: default to project (unified landing surface, RFC-106)
  let activeTab = $state<string>(ViewTab.PROJECT);
  let isLoadingDag = $state(false);
  let dagError = $state<string | null>(null);
  
  // Memory tab state
  let memoryStats = $state<MemoryStats | null>(null);
  let intelligenceData = $state<IntelligenceData | null>(null);
  let isLoadingMemory = $state(false);
  let memoryError = $state<string | null>(null);
  
  // RFC-106: Consolidated tabs (Overview merged into Project)
  const tabs = [
    { id: ViewTab.PROJECT, label: 'Project' },  // RFC-106: Unified project surface
    { id: ViewTab.PIPELINE, label: 'Pipeline' },
    { id: ViewTab.MEMORY, label: 'Memory' },
    { id: 'health', label: 'Health' },
    { id: ViewTab.STATE_DAG, label: 'State' },  // RFC-100: Project health
    { id: ViewTab.WORKERS, label: 'Workers' },  // RFC-100: Multi-agent
  ];
  
  // Keyboard shortcut for weakness scan (Ctrl+Shift+W)
  function handleKeydown(e: KeyboardEvent) {
    if (e.ctrlKey && e.shiftKey && e.key === 'W') {
      e.preventDefault();
      if (project.current?.path) {
        activeTab = 'health' as ViewTab;
        scanWeaknesses(project.current.path);
      }
    }
  }
  
  // RFC-079: Track analyzed path to avoid re-analysis
  let analyzedForPath = $state<string | null>(null);
  
  // Load project data when path changes
  $effect(() => {
    const path = project.current?.path;
    if (path) {
      loadProjectStatus();
      setFilesProjectPath(path); // Files store handles loading and event-driven refresh
    }
  });
  
  // RFC-079: Auto-analyze project when opened (if not already analyzed)
  $effect(() => {
    const path = project.current?.path;
    if (path && path !== analyzedForPath && !project.isAnalyzing) {
      untrack(() => {
        analyzedForPath = path;
        analyzeProject(path);
      });
    }
  });
  
  // RFC-094: Set project path in dag store for reactive reload
  $effect(() => {
    const path = project.current?.path;
    setProjectPath(path ?? null);
  });
  
  // Load DAG when pipeline tab is selected (initial load only)
  $effect(() => {
    const shouldLoad = activeTab === ViewTab.PIPELINE && project.current?.path && dag.nodes.length === 0;
    if (shouldLoad) {
      untrack(() => {
        if (!isLoadingDag) loadDag();
      });
    }
  });
  
  // Load memory when memory tab is selected
  $effect(() => {
    const shouldLoad = activeTab === ViewTab.MEMORY && project.current?.path;
    if (shouldLoad) {
      untrack(() => {
        if (!isLoadingMemory) loadMemory();
      });
    }
  });
  
  // RFC-094: Files refresh is now handled by files.svelte store via agent events
  // See: agent.svelte.ts calls reloadFiles() on task_complete, complete, backlog_goal_completed
  
  async function loadProjectStatus() {
    if (!project.current?.path) return;
    try {
      projectStatus = await invoke<ProjectStatus>('get_project_status', { path: project.current.path });
    } catch (e) {
      console.error('Failed to get project status:', e);
    }
    isLoadingStatus = false;
  }
  
  async function loadDag() {
    if (!project.current?.path) return;
    isLoadingDag = true;
    dagError = null;
    try {
      // RFC-105: Load both index (fast) and full graph
      await loadProjectDagIndex(project.current.path);
      const graph = await invoke<DagGraph>('get_project_dag', { path: project.current.path });
      setGraph(graph);
    } catch (e) {
      console.error('Failed to load DAG:', e);
      dagError = e instanceof Error ? e.message : String(e);
    } finally {
      isLoadingDag = false;
    }
  }
  
  // RFC-105: Handle goal click in Pipeline view
  async function handleGoalClick(goalId: string) {
    const details = await expandGoal(goalId);
    if (details) {
      console.log('Goal expanded:', details);
    }
  }
  
  async function loadMemory() {
    if (!project.current?.path) return;
    isLoadingMemory = true;
    memoryError = null;
    try {
      const [stats, intel] = await Promise.all([
        invoke<MemoryStats>('get_memory_stats', { path: project.current.path }),
        invoke<IntelligenceData>('get_intelligence', { path: project.current.path })
      ]);
      memoryStats = stats;
      intelligenceData = intel;
    } catch (e) {
      console.error('Failed to load memory:', e);
      memoryError = e instanceof Error ? e.message : String(e);
    } finally {
      isLoadingMemory = false;
    }
  }
  
  // loadProjectFiles removed — now handled by files.svelte store
  
  async function handleFileSelect(event: { path: string; name: string; isDir: boolean }) {
    const { path, name, isDir } = event;
    if (isDir) return;
    isLoadingPreview = true;
    try {
      const content = await invoke<string>('read_file_contents', { path, maxSize: 50000 });
      selectedFile = { path, name, content };
    } catch (e) {
      console.error('Failed to read file:', e);
      selectedFile = { path, name, content: `Error: ${e}` };
    }
    isLoadingPreview = false;
  }
  
  function closePreview() {
    selectedFile = null;
  }
  
  function handleTabChange(tabId: string) {
    activeTab = tabId;
  }
  
  // RFC-106: Overview handlers moved to IdleState.svelte
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="project">
  <ProjectHeader />
  
  {#if agent.goal}
    <div class="goal-section">
      <span class="goal-prompt" aria-hidden="true">&gt;</span>
      <span class="goal-text">{agent.goal}</span>
    </div>
  {/if}
  
  <Tabs {tabs} activeTab={activeTab} onchange={handleTabChange} label="Project views">
    {#snippet children(tabId)}
      {#if tabId === ViewTab.PIPELINE}
        <div class="pipeline-view">
          <DagControls onFitView={() => {}} onRefresh={loadDag} />
          
          {#if isLoadingDag}
            <div class="loading-state" role="status">
              <Spinner style="dots" speed={80} />
              <span>Loading pipeline...</span>
            </div>
          {:else if dagError}
            <div class="error-state" role="alert">
              <span class="error-icon">⊗</span>
              <span>{dagError}</span>
              <Button variant="ghost" size="sm" onclick={loadDag}>Retry</Button>
            </div>
          {:else if dag.nodes.length === 0 && (!dag.projectIndex || dag.projectIndex.goals.length === 0)}
            <div class="empty-state">
              <p class="empty-title">No pipeline yet</p>
              <p class="empty-description">Run a goal to see your task pipeline</p>
            </div>
          {:else}
            <div class="pipeline-content">
              <!-- RFC-105: Goals sidebar -->
              {#if dag.projectIndex && dag.projectIndex.goals.length > 0}
                <aside class="goals-sidebar">
                  <h3 class="sidebar-title">
                    Goals ({dag.projectIndex.summary.completedGoals}/{dag.projectIndex.summary.totalGoals})
                  </h3>
                  <ul class="goals-list">
                    {#each getSortedGoals() as goal}
                      <li class="goal-item" class:complete={goal.status === 'complete'}>
                        <button class="goal-btn" onclick={() => handleGoalClick(goal.id)}>
                          <span class="goal-status">
                            {#if goal.status === 'complete'}✓
                            {:else if goal.status === 'running' || goal.status === 'in_progress'}◐
                            {:else if goal.status === 'failed'}✗
                            {:else}○{/if}
                          </span>
                          <span class="goal-title">{goal.title}</span>
                          {#if goal.taskCount > 0}
                            <span class="goal-tasks">{goal.taskCount}</span>
                          {/if}
                        </button>
                      </li>
                    {/each}
                  </ul>
                </aside>
              {/if}
              
              <div class="dag-canvas-wrapper">
                <DagCanvas />
              </div>
              
              {#if dag.selectedNode}
                <DagDetail />
              {/if}
            </div>
          {/if}
        </div>
      {:else if tabId === ViewTab.MEMORY}
        <div class="memory-view">
          {#if isLoadingMemory}
            <div class="loading-state" role="status">
              <Spinner style="dots" speed={80} />
              <span>Loading memory...</span>
            </div>
          {:else if memoryError}
            <div class="error-state" role="alert">
              <span class="error-icon">⊗</span>
              <span>{memoryError}</span>
              <Button variant="ghost" size="sm" onclick={loadMemory}>Retry</Button>
            </div>
          {:else}
            <div class="memory-content">
              <MemoryView stats={memoryStats} intelligence={intelligenceData} />
            </div>
          {/if}
        </div>
      {:else if tabId === 'health'}
        <div class="health-view">
          <WeaknessPanel />
          <WaveExecutionPanel />
        </div>
      {:else if tabId === ViewTab.STATE_DAG}
        <!-- RFC-100: Project State DAG visualization -->
        <div class="state-dag-view">
          {#if project.current?.path}
            <StateDagView projectPath={project.current.path} />
          {:else}
            <div class="empty-state">
              <p class="empty-title">No project selected</p>
              <p class="empty-description">Open a project to see its health status</p>
            </div>
          {/if}
        </div>
      {:else if tabId === ViewTab.WORKERS}
        <!-- RFC-100: Multi-agent orchestration view -->
        <div class="workers-view">
          {#if project.current?.path}
            <ATCView projectPath={project.current.path} />
          {:else}
            <div class="empty-state">
              <p class="empty-title">No project selected</p>
              <p class="empty-description">Open a project to manage workers</p>
            </div>
          {/if}
        </div>
      {:else if tabId === ViewTab.PROJECT}
        <!-- RFC-106: Unified Project Surface -->
        <main class="content">
          {#if agent.isRunning}
            <WorkingState />
          {:else if agent.isDone}
            <DoneState projectFiles={files.entries} isLoadingFiles={files.isLoading} onFileSelect={handleFileSelect} />
          {:else if agent.hasError}
            <ErrorState />
          {:else}
            <IdleState {projectStatus} {isLoadingStatus} projectFiles={files.entries} isLoadingFiles={files.isLoading} onFileSelect={handleFileSelect} />
          {/if}
        </main>
      {/if}
    {/snippet}
  </Tabs>
  
  <Modal isOpen={selectedFile !== null} onClose={closePreview} title={selectedFile?.name ?? 'File Preview'}>
    <div class="preview-content">
      {#if isLoadingPreview}
        <p class="loading-text" role="status">Loading...</p>
      {:else if selectedFile}
        <pre class="preview-code"><code>{selectedFile.content}</code></pre>
      {/if}
    </div>
  </Modal>
</div>

<style>
  .project {
    display: flex;
    flex-direction: column;
    height: 100vh;
    padding: var(--space-6);
    /* Removed overflow:hidden - clips dropdown menus */
  }
  
  .goal-section {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-base);
    margin-bottom: var(--space-4);
    flex-shrink: 0;
  }
  
  .goal-prompt { color: var(--text-tertiary); }
  .goal-text { color: var(--text-primary); }
  .content { flex: 1; display: flex; flex-direction: column; min-height: 0; }
  
  .pipeline-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0; /* Critical for proper flex behavior */
  }
  
  .pipeline-content {
    flex: 1;
    display: flex;
    min-height: 0; /* Allow shrinking */
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    /* Removed overflow:hidden - clips menus; border-radius still works */
  }
  
  /* RFC-105: DAG canvas wrapper */
  .dag-canvas-wrapper { flex: 1; position: relative; }
  
  /* RFC-105: Goals sidebar for pipeline view */
  .goals-sidebar { 
    width: 220px; 
    border-right: 1px solid var(--border-color); 
    display: flex; 
    flex-direction: column;
    overflow: hidden;
    flex-shrink: 0;
  }
  .sidebar-title { 
    padding: 10px 12px; 
    margin: 0; 
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    font-weight: 600; 
    color: var(--text-tertiary); 
    text-transform: uppercase;
    letter-spacing: 0.05em;
    border-bottom: 1px solid var(--border-color);
    background: var(--bg-tertiary);
  }
  .goals-list { list-style: none; margin: 0; padding: 6px; overflow-y: auto; flex: 1; }
  .goal-item { margin-bottom: 2px; }
  .goal-btn { 
    width: 100%; 
    display: flex; 
    align-items: center; 
    gap: 6px; 
    padding: 8px 10px; 
    border-radius: var(--radius-sm); 
    text-align: left;
    transition: background var(--transition-fast);
  }
  .goal-btn:hover { background: var(--bg-tertiary); }
  .goal-status { 
    flex-shrink: 0; 
    width: 16px; 
    height: 16px; 
    display: flex; 
    align-items: center; 
    justify-content: center;
    font-size: var(--text-xs); 
    color: var(--text-tertiary);
  }
  .goal-item.complete .goal-status { color: var(--success); }
  .goal-title { 
    flex: 1; 
    font-family: var(--font-mono); 
    font-size: var(--text-xs); 
    color: var(--text-primary);
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .goal-tasks { 
    flex-shrink: 0;
    padding: 1px 5px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono); 
    font-size: 10px; 
    color: var(--text-tertiary);
  }
  
  .memory-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow-y: auto;
  }
  
  .memory-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    padding: var(--space-4) 0;
  }
  
  .loading-state, .error-state, .empty-state {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    color: var(--text-tertiary);
    padding: var(--space-8);
    font-family: var(--font-mono);
  }
  
  .error-state { color: var(--error); }
  /* (unused) .loading-icon { font-size: var(--text-xl); }*/
  .error-icon { font-size: var(--text-xl); font-weight: 600; }
  .empty-title { font-size: var(--text-lg); font-weight: 500; color: var(--text-secondary); margin: 0; }
  .empty-description { font-size: var(--text-sm); margin: 0; }
  
  .preview-content { max-height: 60vh; overflow: auto; }
  .preview-code { margin: 0; font-family: var(--font-mono); font-size: var(--text-xs); line-height: 1.6; color: var(--text-secondary); white-space: pre-wrap; word-wrap: break-word; }
  .preview-code code { display: block; }
  .loading-text { font-size: var(--text-sm); color: var(--text-tertiary); text-align: center; margin: 0; }
  
  .health-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4) 0;
    max-width: 600px;
  }
  
  /* RFC-100: State DAG view */
  .state-dag-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }

  /* RFC-100: Workers/ATC view */
  .workers-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: hidden;
  }
</style>
