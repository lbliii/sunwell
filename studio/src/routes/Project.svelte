<!--
  Project — Working screen
  
  Shows project details, goal input, progress, and done state.
  Handles idle (landing), running, done, and error states.
-->
<script lang="ts">
  import Progress from '../components/Progress.svelte';
  import Button from '../components/Button.svelte';
  import LearningsPanel from '../components/LearningsPanel.svelte';
  import InputBar from '../components/InputBar.svelte';
  import FileTree from '../components/FileTree.svelte';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { goHome, goToPreview } from '../stores/app';
  import { currentProject, resumeProject } from '../stores/project';
  import { 
    agentState, 
    isRunning, 
    isDone, 
    hasError,
    duration,
    completedTasks,
    stopAgent,
    resetAgent,
    runGoal
  } from '../stores/agent';
  import { 
    dagGraph, 
    setGraph, 
    selectedNode
  } from '../stores/dag';
  import { invoke } from '@tauri-apps/api/core';
  import type { ProjectStatus, FileEntry, DagGraph, MemoryStats, IntelligenceData } from '$lib/types';
  import { onMount } from 'svelte';
  
  // Project status for showing last run info
  let projectStatus: ProjectStatus | null = null;
  let isLoadingStatus = true;
  let showFilePanel = false;
  
  // File tree state
  let projectFiles: FileEntry[] = [];
  let isLoadingFiles = true;
  let selectedFile: { path: string; name: string; content: string } | null = null;
  let isLoadingPreview = false;
  
  // View tabs state (RFC-056, RFC-057)
  type ViewTab = 'progress' | 'pipeline' | 'memory';
  let activeTab: ViewTab = 'progress';
  let isLoadingDag = false;
  let dagError: string | null = null;
  
  // Memory tab state (RFC-013, RFC-014)
  let memoryStats: MemoryStats | null = null;
  let intelligenceData: IntelligenceData | null = null;
  let isLoadingMemory = false;
  let memoryError: string | null = null;
  
  onMount(async () => {
    if ($currentProject?.path) {
      // Load project status
      try {
        projectStatus = await invoke<ProjectStatus>('get_project_status', { 
          path: $currentProject.path 
        });
      } catch (e) {
        console.error('Failed to get project status:', e);
      }
      
      // Load file tree
      await loadProjectFiles();
    }
    isLoadingStatus = false;
    
    // RFC-056: Auto-refresh DAG on tab focus
    const handleVisibilityChange = () => {
      if (!document.hidden && activeTab === 'pipeline' && $currentProject?.path) {
        loadDag();
      }
    };
    document.addEventListener('visibilitychange', handleVisibilityChange);
    
    return () => {
      document.removeEventListener('visibilitychange', handleVisibilityChange);
    };
  });
  
  // RFC-056: Load DAG when switching to pipeline tab
  $: if (activeTab === 'pipeline' && $currentProject?.path) {
    loadDag();
  }
  
  // RFC-013/014: Load memory when switching to memory tab
  $: if (activeTab === 'memory' && $currentProject?.path) {
    loadMemory();
  }
  
  // RFC-056: Refresh DAG after agent completes
  $: if ($isDone && activeTab === 'pipeline' && $currentProject?.path) {
    loadDag();
  }
  
  async function loadDag() {
    if (!$currentProject?.path) return;
    
    isLoadingDag = true;
    dagError = null;
    
    try {
      const graph = await invoke<DagGraph>('get_project_dag', { 
        path: $currentProject.path 
      });
      setGraph(graph);
    } catch (e) {
      console.error('Failed to load DAG:', e);
      dagError = e instanceof Error ? e.message : String(e);
    } finally {
      isLoadingDag = false;
    }
  }
  
  async function loadMemory() {
    if (!$currentProject?.path) return;
    
    isLoadingMemory = true;
    memoryError = null;
    
    try {
      const [stats, intel] = await Promise.all([
        invoke<MemoryStats>('get_memory_stats', { path: $currentProject.path }),
        invoke<IntelligenceData>('get_intelligence', { path: $currentProject.path })
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
  
  async function loadProjectFiles() {
    if (!$currentProject?.path) return;
    
    isLoadingFiles = true;
    try {
      projectFiles = await invoke<FileEntry[]>('list_project_files', { 
        path: $currentProject.path,
        maxDepth: 4
      });
    } catch (e) {
      console.error('Failed to load project files:', e);
      projectFiles = [];
    }
    isLoadingFiles = false;
  }
  
  async function handleFileSelect(event: CustomEvent<{ path: string; name: string; isDir: boolean }>) {
    const { path, name, isDir } = event.detail;
    if (isDir) return;
    
    isLoadingPreview = true;
    try {
      const content = await invoke<string>('read_file_contents', { 
        path,
        maxSize: 50000 // 50KB limit for preview
      });
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
  
  // Reload files after agent completes
  $: if ($isDone && $currentProject?.path) {
    loadProjectFiles();
  }
  
  // Reactive: extract project status info
  $: lastGoal = projectStatus?.last_goal;
  $: taskProgress = projectStatus?.tasks_completed && projectStatus?.tasks_total
    ? `${projectStatus.tasks_completed}/${projectStatus.tasks_total} tasks`
    : null;
  
  function formatDuration(seconds: number): string {
    if (seconds < 60) return `${seconds}s`;
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins}m ${secs}s`;
  }
  
  function handleBack() {
    resetAgent();
    goHome();
  }
  
  function handleTryIt() {
    goToPreview();
  }
  
  function handleStop() {
    stopAgent();
  }
  
  // Project access handlers
  async function handleOpenFiles() {
    const project = $currentProject;
    if (!project?.path) return;
    
    try {
      await invoke('open_in_finder', { path: project.path });
    } catch (e) {
      console.error('Failed to open files:', e);
    }
  }
  
  async function handleOpenTerminal() {
    const project = $currentProject;
    if (!project?.path) return;
    
    try {
      await invoke('open_terminal', { path: project.path });
    } catch (e) {
      console.error('Failed to open terminal:', e);
    }
  }
  
  async function handleOpenEditor() {
    const project = $currentProject;
    if (!project?.path) return;
    
    try {
      await invoke('open_in_editor', { path: project.path });
    } catch (e) {
      console.error('Failed to open editor:', e);
    }
  }
  
  async function handleRebuild() {
    const goal = $agentState.goal;
    const project = $currentProject;
    if (!goal || !project?.path) return;
    
    // Reset and re-run with same goal
    resetAgent();
    await runGoal(goal, project.path);
  }
  
  // Idle state handlers
  async function handleNewGoal(goal: string) {
    const project = $currentProject;
    if (!project?.path) return;
    
    await runGoal(goal, project.path);
  }
  
  async function handleResume() {
    const project = $currentProject;
    if (!project?.path) return;
    
    await resumeProject(project.path);
  }
  
  function formatRelativeTime(timestamp: string | null): string {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  }
</script>

<div class="project">
  <!-- Header -->
  <header class="header">
    <button class="back-btn" on:click={handleBack}>← {$currentProject?.name ?? 'Project'}</button>
  </header>
  
  <!-- Goal (only show when there's an active goal) -->
  {#if $agentState.goal}
    <div class="goal-section">
      <span class="goal-prompt">&gt;</span>
      <span class="goal-text">{$agentState.goal}</span>
    </div>
  {/if}
  
  <!-- View Tabs (RFC-056, RFC-057) -->
  <div class="view-tabs">
    <button 
      class="tab" 
      class:active={activeTab === 'progress'}
      on:click={() => activeTab = 'progress'}
    >
      Progress
    </button>
    <button 
      class="tab" 
      class:active={activeTab === 'pipeline'}
      on:click={() => activeTab = 'pipeline'}
    >
      Pipeline
    </button>
    <button 
      class="tab" 
      class:active={activeTab === 'memory'}
      on:click={() => activeTab = 'memory'}
    >
      Memory
    </button>
  </div>
  
  <!-- Content -->
  <main class="content">
    {#if activeTab === 'pipeline'}
      <!-- Pipeline View (RFC-056) -->
      <div class="pipeline-view">
        <DagControls 
          onFitView={() => {}}
          onRefresh={loadDag}
        />
        
        {#if isLoadingDag}
          <div class="pipeline-loading">
            <span class="loading-icon animate-pulse">::</span>
            <span>Loading pipeline...</span>
          </div>
        {:else if dagError}
          <div class="pipeline-error">
            <span class="error-icon">[x]</span>
            <span>{dagError}</span>
            <Button variant="ghost" size="sm" on:click={loadDag}>Retry</Button>
          </div>
        {:else if $dagGraph.nodes.length === 0}
          <div class="pipeline-empty">
            <p class="empty-title">No pipeline yet</p>
            <p class="empty-description">Run a goal to see your task pipeline</p>
          </div>
        {:else}
          <div class="pipeline-content">
            <DagCanvas />
            {#if $selectedNode}
              <DagDetail />
            {/if}
          </div>
        {/if}
      </div>
    {:else if activeTab === 'memory'}
      <!-- Memory View (RFC-013, RFC-014) -->
      <div class="memory-view">
        {#if isLoadingMemory}
          <div class="memory-loading">
            <span class="loading-icon animate-pulse">::</span>
            <span>Loading memory...</span>
          </div>
        {:else if memoryError}
          <div class="memory-error">
            <span class="error-icon">[x]</span>
            <span>{memoryError}</span>
            <Button variant="ghost" size="sm" on:click={loadMemory}>Retry</Button>
          </div>
        {:else}
          <div class="memory-content">
            <!-- Memory Stats -->
            <section class="memory-section">
              <h3 class="memory-section-title">// Memory Stats</h3>
              {#if memoryStats}
                <div class="stats-grid">
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.totalTurns}</span>
                    <span class="stat-label">Total Turns</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.hotTurns}</span>
                    <span class="stat-label">Hot (Recent)</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.warmFiles}</span>
                    <span class="stat-label">Warm Files</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.coldFiles}</span>
                    <span class="stat-label">Archived</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.branches}</span>
                    <span class="stat-label">Branches</span>
                  </div>
                  <div class="stat-card">
                    <span class="stat-value">{memoryStats.learnings}</span>
                    <span class="stat-label">Learnings</span>
                  </div>
                </div>
              {:else}
                <p class="empty-text">No memory data yet</p>
              {/if}
            </section>
            
            <!-- Learnings (from agent runs) -->
            <section class="memory-section">
              <h3 class="memory-section-title">// Learnings ({intelligenceData?.totalLearnings ?? 0})</h3>
              {#if intelligenceData && intelligenceData.learnings.length > 0}
                <div class="intelligence-list">
                  {#each intelligenceData.learnings as learning}
                    <div class="intelligence-item learning">
                      <span class="item-icon">[📚]</span>
                      <div class="item-content">
                        <p class="item-title">{learning.fact}</p>
                        <p class="item-meta">
                          <span class="item-category">{learning.category}</span>
                          {#if learning.sourceFile}
                            <span class="item-source">{learning.sourceFile}</span>
                          {/if}
                        </p>
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="empty-text">No learnings yet — run a goal to start learning</p>
              {/if}
            </section>
            
            <!-- Dead Ends (approaches that didn't work) -->
            <section class="memory-section">
              <h3 class="memory-section-title">// Dead Ends ({intelligenceData?.totalDeadEnds ?? 0})</h3>
              {#if intelligenceData && intelligenceData.deadEnds.length > 0}
                <div class="intelligence-list">
                  {#each intelligenceData.deadEnds as deadEnd}
                    <div class="intelligence-item dead-end">
                      <span class="item-icon">[⚠]</span>
                      <div class="item-content">
                        <p class="item-title">{deadEnd.approach}</p>
                        {#if deadEnd.reason}
                          <p class="item-detail">{deadEnd.reason}</p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="empty-text">No dead ends recorded</p>
              {/if}
            </section>
            
            <!-- Decisions -->
            <section class="memory-section">
              <h3 class="memory-section-title">// Decisions ({intelligenceData?.totalDecisions ?? 0})</h3>
              {#if intelligenceData && intelligenceData.decisions.length > 0}
                <div class="intelligence-list">
                  {#each intelligenceData.decisions as decision}
                    <div class="intelligence-item decision">
                      <span class="item-icon">[✓]</span>
                      <div class="item-content">
                        <p class="item-title">{decision.decision}</p>
                        {#if decision.rationale}
                          <p class="item-detail">{decision.rationale}</p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="empty-text">No decisions recorded</p>
              {/if}
            </section>
            
            <!-- Failed Approaches (legacy) -->
            <section class="memory-section">
              <h3 class="memory-section-title">// Avoided Paths ({intelligenceData?.totalFailures ?? 0})</h3>
              {#if intelligenceData && intelligenceData.failures.length > 0}
                <div class="intelligence-list">
                  {#each intelligenceData.failures as failure}
                    <div class="intelligence-item failure">
                      <span class="item-icon">[✗]</span>
                      <div class="item-content">
                        <p class="item-title">{failure.approach}</p>
                        {#if failure.reason}
                          <p class="item-detail">{failure.reason}</p>
                        {/if}
                      </div>
                    </div>
                  {/each}
                </div>
              {:else}
                <p class="empty-text">No failed approaches recorded</p>
              {/if}
            </section>
          </div>
        {/if}
      </div>
    {:else if $isRunning}
      <!-- Working State -->
      <div class="working animate-fadeIn">
        <div class="status-header">
          <span class="status-icon animate-pulse">::</span>
          <span class="status-text">
            {$agentState.status === 'planning' ? 'Planning' : 'Building'}
          </span>
        </div>
        
        <Progress 
          tasks={$agentState.tasks}
          currentIndex={$agentState.currentTaskIndex}
          totalExpected={$agentState.totalTasks}
        />
        
        <div class="working-footer">
          <span class="working-progress">
            {$completedTasks}/{$agentState.totalTasks} tasks
          </span>
          <span class="working-time">{formatDuration($duration)}</span>
        </div>
        
        <div class="actions">
          <Button variant="ghost" size="sm" on:click={handleStop}>
            Stop
          </Button>
        </div>
        
        <!-- Quick Actions (browse while waiting) -->
        <div class="working-actions">
          <button class="action-btn" on:click={handleOpenFiles}>
            <span class="action-icon">[dir]</span>
            <span>Files</span>
          </button>
          <button class="action-btn" on:click={handleOpenTerminal}>
            <span class="action-icon">[&gt;_]</span>
            <span>Terminal</span>
          </button>
          <button class="action-btn" on:click={handleOpenEditor}>
            <span class="action-icon">[ed]</span>
            <span>Editor</span>
          </button>
          <button class="action-btn" on:click={() => showFilePanel = !showFilePanel}>
            <span class="action-icon">{showFilePanel ? '[-]' : '[+]'}</span>
            <span>Browse</span>
          </button>
        </div>
        
        <!-- Inline File Browser -->
        {#if showFilePanel}
          <div class="file-panel">
            <FileTree path={$currentProject?.path ?? ''} />
          </div>
        {/if}
        
        <!-- Learnings Panel -->
        <LearningsPanel 
          learnings={$agentState.learnings}
          concepts={$agentState.concepts}
        />
      </div>
      
    {:else if $isDone}
      <!-- Done State -->
      <div class="done animate-fadeIn">
        <div class="done-header">
          <span class="done-icon">[ok]</span>
          <span class="done-text">Done</span>
          <span class="done-stats">
            {$agentState.tasks.length} tasks · {formatDuration($duration)}
          </span>
        </div>
        
        <div class="try-it-section">
          <Button variant="primary" size="lg" icon=">" on:click={handleTryIt}>
            TRY IT
          </Button>
        </div>
        
        <nav class="done-nav">
          <button class="nav-link" on:click={handleOpenFiles}>files</button>
          <span class="nav-sep">·</span>
          <button class="nav-link" on:click={handleOpenTerminal}>terminal</button>
          <span class="nav-sep">·</span>
          <button class="nav-link" on:click={handleOpenEditor}>edit</button>
          <span class="nav-sep">·</span>
          <button class="nav-link" on:click={handleRebuild}>rebuild</button>
        </nav>
        
        <!-- File Tree (in done state) -->
        <div class="done-files">
          <h3 class="section-title">📂 Created Files</h3>
          {#if isLoadingFiles}
            <p class="loading-text">Loading files...</p>
          {:else if projectFiles.length === 0}
            <p class="empty-text">No files created</p>
          {:else}
            <div class="file-tree-container">
              <FileTree 
                files={projectFiles} 
                on:select={handleFileSelect}
              />
            </div>
          {/if}
        </div>
        
        <!-- Learnings Panel (collapsed by default in done state) -->
        {#if $agentState.learnings.length > 0}
          <div class="done-learnings">
            <LearningsPanel 
              learnings={$agentState.learnings}
              concepts={$agentState.concepts}
              collapsed={true}
            />
          </div>
        {/if}
      </div>
      
    {:else if $hasError}
      <!-- Error State -->
      <div class="error animate-fadeIn">
        <div class="error-header">
          <span class="error-icon">[x]</span>
          <span class="error-text">Error</span>
        </div>
        
        <p class="error-message">{$agentState.error}</p>
        
        <div class="actions">
          <Button variant="secondary" on:click={handleBack}>
            Go Back
          </Button>
        </div>
      </div>
      
    {:else}
      <!-- Idle State — Project Landing -->
      <div class="idle animate-fadeIn">
        <!-- Project Info -->
        <div class="project-info">
          <h2 class="project-title">{$currentProject?.name ?? 'Project'}</h2>
          {#if $currentProject?.description}
            <p class="project-description">{$currentProject.description}</p>
          {/if}
          <p class="project-path">{$currentProject?.path}</p>
        </div>
        
        <!-- Last Run Status (only show if there's history) -->
        {#if !isLoadingStatus && projectStatus && projectStatus.status !== 'none'}
          <div class="last-run">
            {#if projectStatus.status === 'interrupted'}
              <div class="status-badge interrupted">
                <span class="badge-icon">||</span>
                <span>Interrupted</span>
              </div>
              {#if lastGoal}
                <p class="last-goal">"{lastGoal}"</p>
              {/if}
              {#if taskProgress}
                <p class="last-progress">{taskProgress} completed</p>
              {/if}
              <Button variant="primary" on:click={handleResume}>
                Resume
              </Button>
            {:else if projectStatus.status === 'complete'}
              <div class="status-badge complete">
                <span class="badge-icon">[ok]</span>
                <span>Last run complete</span>
              </div>
              {#if lastGoal}
                <p class="last-goal">"{lastGoal}"</p>
              {/if}
            {:else if projectStatus.status === 'failed'}
              <div class="status-badge failed">
                <span class="badge-icon">[x]</span>
                <span>Last run failed</span>
              </div>
            {/if}
            {#if projectStatus.last_activity}
              <p class="last-activity">{formatRelativeTime(projectStatus.last_activity)}</p>
            {/if}
          </div>
        {/if}
        
        <!-- Quick Actions -->
        <div class="quick-actions">
          <button class="action-btn" on:click={handleOpenFiles}>
            <span class="action-icon">[dir]</span>
            <span>Finder</span>
          </button>
          <button class="action-btn" on:click={handleOpenTerminal}>
            <span class="action-icon">&gt;_</span>
            <span>Terminal</span>
          </button>
          <button class="action-btn" on:click={handleOpenEditor}>
            <span class="action-icon">[ed]</span>
            <span>Editor</span>
          </button>
        </div>
        
        <!-- File Tree -->
        <div class="file-tree-section">
          <h3 class="section-title">// Project Files</h3>
          {#if isLoadingFiles}
            <p class="loading-text">Loading files...</p>
          {:else if projectFiles.length === 0}
            <p class="empty-text">No files yet</p>
          {:else}
            <div class="file-tree-container">
              <FileTree 
                files={projectFiles} 
                on:select={handleFileSelect}
              />
            </div>
          {/if}
        </div>
        
        <!-- Goal Input -->
        <div class="goal-input-section">
          <p class="input-label">What would you like to build?</p>
          <InputBar 
            placeholder="describe your goal..." 
            on:submit={(e) => handleNewGoal(e.detail)}
          />
        </div>
      </div>
    {/if}
  </main>
  
  <!-- File Preview Panel -->
  {#if selectedFile}
    <div class="preview-overlay" role="button" tabindex="0" on:click={closePreview} on:keydown={(e) => e.key === 'Escape' && closePreview()}>
      <div class="preview-panel" role="dialog" aria-modal="true" on:click|stopPropagation on:keydown|stopPropagation>
        <header class="preview-header">
          <span class="preview-filename">{selectedFile.name}</span>
          <button class="preview-close" on:click={closePreview}>✕</button>
        </header>
        <div class="preview-content">
          {#if isLoadingPreview}
            <p class="loading-text">Loading...</p>
          {:else}
            <pre class="preview-code"><code>{selectedFile.content}</code></pre>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .project {
    display: flex;
    flex-direction: column;
    min-height: 100vh;
    padding: var(--space-6);
  }
  
  /* Header */
  .header {
    margin-bottom: var(--space-4);
  }
  
  /* View Tabs (RFC-056) */
  .view-tabs {
    display: flex;
    gap: var(--space-1);
    margin-bottom: var(--space-4);
    border-bottom: 1px solid var(--border-color);
    padding-bottom: var(--space-2);
  }
  
  .tab {
    padding: var(--space-2) var(--space-4);
    font-size: var(--text-sm);
    font-family: var(--font-mono);
    color: var(--text-tertiary);
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    cursor: pointer;
    transition: all var(--transition-fast);
  }
  
  .tab:hover {
    color: var(--text-secondary);
  }
  
  .tab.active {
    color: var(--text-primary);
    border-bottom-color: var(--text-primary);
  }
  
  /* Pipeline View (RFC-056) */
  .pipeline-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 500px;
  }
  
  .pipeline-content {
    flex: 1;
    display: flex;
    min-height: 400px;
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    overflow: hidden;
  }
  
  .pipeline-loading,
  .pipeline-error,
  .pipeline-empty {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    color: var(--text-tertiary);
    padding: var(--space-8);
  }
  
  .pipeline-loading {
    font-family: var(--font-mono);
  }
  
  .loading-icon {
    font-size: var(--text-xl);
  }
  
  .pipeline-error {
    color: var(--error);
  }
  
  .error-icon {
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  .empty-title {
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
  }
  
  .empty-description {
    font-size: var(--text-sm);
    margin: 0;
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
  
  /* Goal */
  .goal-section {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-base);
    margin-bottom: var(--space-4);
  }
  
  .goal-prompt {
    color: var(--text-tertiary);
  }
  
  .goal-text {
    color: var(--text-primary);
  }
  
  /* Content */
  .content {
    flex: 1;
    display: flex;
    flex-direction: column;
  }
  
  /* Working State */
  .working {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  
  .status-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-lg);
  }
  
  .status-icon {
    font-size: var(--text-xl);
  }
  
  .status-text {
    font-weight: 500;
  }
  
  .working-footer {
    display: flex;
    justify-content: space-between;
    color: var(--text-tertiary);
    font-size: var(--text-sm);
    margin-top: var(--space-4);
  }
  
  .working-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-4);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-color);
  }
  
  .file-panel {
    margin-top: var(--space-4);
    animation: slideDown 0.2s ease-out;
  }
  
  @keyframes slideDown {
    from {
      opacity: 0;
      transform: translateY(-10px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
  
  /* Done State */
  .done {
    flex: 1;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-8);
  }
  
  .done-header {
    display: flex;
    align-items: baseline;
    gap: var(--space-3);
  }
  
  .done-icon {
    color: var(--success);
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  .done-text {
    font-size: var(--text-lg);
    font-weight: 500;
  }
  
  .done-stats {
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .try-it-section {
    margin: var(--space-8) 0;
  }
  
  .done-nav {
    display: flex;
    gap: var(--space-2);
    color: var(--text-tertiary);
    font-size: var(--text-sm);
  }
  
  .nav-link {
    color: var(--text-secondary);
    transition: color var(--transition-fast);
  }
  
  .nav-link:hover {
    color: var(--text-primary);
  }
  
  .nav-sep {
    color: var(--text-tertiary);
  }
  
  .done-learnings {
    width: 100%;
    max-width: 500px;
    margin-top: var(--space-6);
  }
  
  /* Error State */
  .error {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-4);
    flex: 1;
  }
  
  .error-header {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  
  .error-icon {
    color: var(--error);
    font-size: var(--text-xl);
    font-weight: 600;
  }
  
  .error-text {
    font-size: var(--text-lg);
    font-weight: 500;
    color: var(--error);
  }
  
  .error-message {
    color: var(--text-secondary);
    text-align: center;
    max-width: 400px;
  }
  
  /* Actions */
  .actions {
    margin-top: var(--space-4);
    display: flex;
    justify-content: center;
    gap: var(--space-4);
  }
  
  /* Idle — Project Landing */
  .idle {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-8);
    padding: var(--space-4) 0;
  }
  
  .project-info {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .project-title {
    font-size: var(--text-2xl);
    font-weight: 600;
    color: var(--text-primary);
    margin: 0;
  }
  
  .project-description {
    color: var(--text-secondary);
    font-size: var(--text-base);
    margin: 0;
  }
  
  .project-path {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  /* Last Run Status */
  .last-run {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-4);
    background: var(--bg-secondary);
    border-radius: var(--radius-lg);
    border: 1px solid var(--border-color);
    max-width: 600px;
  }
  
  .status-badge {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--text-sm);
    font-weight: 500;
  }
  
  .status-badge.interrupted {
    color: var(--warning, #f59e0b);
  }
  
  .status-badge.complete {
    color: var(--success);
  }
  
  .status-badge.failed {
    color: var(--error);
  }
  
  .badge-icon {
    font-size: var(--text-base);
  }
  
  .last-goal {
    font-family: var(--font-mono);
    color: var(--text-primary);
    font-size: var(--text-sm);
    margin: 0;
  }
  
  .last-activity {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
  }
  
  /* Quick Actions */
  .quick-actions {
    display: flex;
    gap: var(--space-3);
  }
  
  .action-btn {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    color: var(--text-secondary);
    font-size: var(--text-xs);
    transition: all var(--transition-fast);
    min-width: 70px;
  }
  
  .action-btn:hover {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-icon {
    font-size: var(--text-lg);
  }
  
  /* Goal Input Section */
  .goal-input-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin-top: auto;
    padding-top: var(--space-8);
  }
  
  .input-label {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  /* File Tree Section */
  .file-tree-section,
  .done-files {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  
  .done-files {
    width: 100%;
    max-width: 500px;
    align-self: center;
  }
  
  .section-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    margin: 0;
  }
  
  .file-tree-container {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-md);
    padding: var(--space-2);
    max-height: 300px;
    overflow-y: auto;
  }
  
  .loading-text,
  .empty-text {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    padding: var(--space-4);
    text-align: center;
    margin: 0;
  }
  
  /* File Preview Overlay */
  .preview-overlay {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    padding: var(--space-6);
    z-index: 100;
    backdrop-filter: blur(4px);
  }
  
  .preview-panel {
    background: var(--bg-primary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    width: 100%;
    max-width: 800px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.4);
  }
  
  .preview-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3) var(--space-4);
    background: var(--bg-secondary);
    border-bottom: 1px solid var(--border-color);
  }
  
  .preview-filename {
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    color: var(--text-primary);
    font-weight: 500;
  }
  
  .preview-close {
    background: transparent;
    border: none;
    color: var(--text-tertiary);
    font-size: var(--text-lg);
    cursor: pointer;
    padding: var(--space-1);
    line-height: 1;
    transition: color var(--transition-fast);
  }
  
  .preview-close:hover {
    color: var(--text-primary);
  }
  
  .preview-content {
    flex: 1;
    overflow: auto;
    padding: var(--space-4);
  }
  
  .preview-code {
    margin: 0;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    line-height: 1.6;
    color: var(--text-secondary);
    white-space: pre-wrap;
    word-wrap: break-word;
  }
  
  .preview-code code {
    display: block;
  }
  
  /* Memory View (RFC-013, RFC-014) */
  .memory-view {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 400px;
  }
  
  .memory-loading,
  .memory-error {
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
  
  .memory-error {
    color: var(--error);
  }
  
  .memory-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-6);
    padding: var(--space-4) 0;
  }
  
  .memory-section {
    background: var(--bg-secondary);
    border: 1px solid var(--border-color);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
  }
  
  .memory-section-title {
    font-size: var(--text-sm);
    font-weight: 500;
    color: var(--text-secondary);
    font-family: var(--font-mono);
    margin: 0 0 var(--space-4) 0;
  }
  
  .stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(100px, 1fr));
    gap: var(--space-3);
  }
  
  .stat-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
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
  }
  
  .intelligence-list {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    max-height: 300px;
    overflow-y: auto;
  }
  
  .intelligence-item {
    display: flex;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--bg-tertiary);
    border-radius: var(--radius-md);
    border-left: 3px solid transparent;
  }
  
  .intelligence-item.decision {
    border-left-color: var(--success);
  }
  
  .intelligence-item.failure {
    border-left-color: var(--error);
  }
  
  .intelligence-item.learning {
    border-left-color: var(--accent, #8b5cf6);
  }
  
  .intelligence-item.dead-end {
    border-left-color: var(--warning, #f59e0b);
  }
  
  .item-icon {
    color: var(--text-tertiary);
    font-family: var(--font-mono);
    font-size: var(--text-sm);
    flex-shrink: 0;
  }
  
  .intelligence-item.decision .item-icon {
    color: var(--success);
  }
  
  .intelligence-item.failure .item-icon {
    color: var(--error);
  }
  
  .intelligence-item.learning .item-icon {
    color: var(--accent, #8b5cf6);
  }
  
  .intelligence-item.dead-end .item-icon {
    color: var(--warning, #f59e0b);
  }
  
  .item-content {
    flex: 1;
    min-width: 0;
  }
  
  .item-title {
    font-size: var(--text-sm);
    color: var(--text-primary);
    margin: 0;
    font-weight: 500;
  }
  
  .item-detail {
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: var(--space-1) 0 0 0;
    line-height: 1.4;
  }
  
  .item-meta {
    display: flex;
    gap: var(--space-2);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: var(--space-1) 0 0 0;
  }
  
  .item-category {
    padding: 1px 6px;
    background: var(--bg-tertiary);
    border-radius: var(--radius-sm);
    font-family: var(--font-mono);
  }
  
  .item-source {
    opacity: 0.7;
  }
</style>
