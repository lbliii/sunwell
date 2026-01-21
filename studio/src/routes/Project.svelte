<!--
  Project — Working screen (Svelte 5, RFC-062 decomposed)
  
  Main project route that orchestrates state-specific sub-components.
-->
<script lang="ts">
  import { untrack } from 'svelte';
  import { invoke } from '@tauri-apps/api/core';
  import type { ProjectStatus, FileEntry, DagGraph, MemoryStats, IntelligenceData } from '$lib/types';
  import { ViewTab } from '$lib/constants';
  import Button from '../components/Button.svelte';
  import Modal from '../components/Modal.svelte';
  import Tabs from '../components/Tabs.svelte';
  import Spinner from '../components/ui/Spinner.svelte';
  import { MemoryView } from '../components';
  import { DagCanvas, DagControls, DagDetail } from '../components/dag';
  import { WeaknessPanel, WaveExecutionPanel } from '../components/weakness';
  import { ProjectHeader, WorkingState, DoneState, ErrorState, IdleState } from '../components/project';
  import { project } from '../stores/project.svelte';
  import { agent } from '../stores/agent.svelte';
  import { dag, setGraph } from '../stores/dag.svelte';
  import { scanWeaknesses } from '../stores/weakness.svelte';
  
  // Project status for showing last run info
  let projectStatus = $state<ProjectStatus | null>(null);
  let isLoadingStatus = $state(false);
  
  // File tree state
  let projectFiles = $state<FileEntry[]>([]);
  let isLoadingFiles = $state(false);
  let filesLoadedForPath = $state<string | null>(null);
  let selectedFile = $state<{ path: string; name: string; content: string } | null>(null);
  let isLoadingPreview = $state(false);
  
  // View tabs state
  let activeTab = $state<ViewTab>(ViewTab.PROGRESS);
  let isLoadingDag = $state(false);
  let dagError = $state<string | null>(null);
  
  // Memory tab state
  let memoryStats = $state<MemoryStats | null>(null);
  let intelligenceData = $state<IntelligenceData | null>(null);
  let isLoadingMemory = $state(false);
  let memoryError = $state<string | null>(null);
  
  const tabs = [
    { id: ViewTab.PROGRESS, label: 'Progress' },
    { id: ViewTab.PIPELINE, label: 'Pipeline' },
    { id: ViewTab.MEMORY, label: 'Memory' },
    { id: 'health', label: 'Health' },
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
  
  // Load project data when path changes
  $effect(() => {
    const path = project.current?.path;
    if (path && path !== filesLoadedForPath && !isLoadingFiles) {
      loadProjectStatus();
      loadProjectFiles();
    }
  });
  
  // Load DAG when pipeline tab is selected
  $effect(() => {
    const shouldLoad = activeTab === ViewTab.PIPELINE && project.current?.path;
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
  
  // Refresh data when agent completes - track previous status to detect transitions
  let prevAgentDone = $state(false);
  $effect(() => {
    const isDone = agent.isDone;
    const path = project.current?.path;
    // Detect transition from not-done to done
    if (isDone && !prevAgentDone && path) {
      // Reset filesLoadedForPath to force reload
      filesLoadedForPath = null;
      loadProjectFiles();
      if (activeTab === ViewTab.PIPELINE) {
        loadDag();
      }
    }
    prevAgentDone = isDone;
  });
  
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
      const graph = await invoke<DagGraph>('get_project_dag', { path: project.current.path });
      setGraph(graph);
    } catch (e) {
      console.error('Failed to load DAG:', e);
      dagError = e instanceof Error ? e.message : String(e);
    } finally {
      isLoadingDag = false;
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
  
  async function loadProjectFiles() {
    const path = project.current?.path;
    if (!path) return;
    isLoadingFiles = true;
    try {
      projectFiles = await invoke<FileEntry[]>('list_project_files', { path, maxDepth: 4 });
      filesLoadedForPath = path;
    } catch (e) {
      console.error('Failed to load project files:', e);
      projectFiles = [];
      filesLoadedForPath = null;
    }
    isLoadingFiles = false;
  }
  
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
    activeTab = tabId as ViewTab;
  }
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
          {:else if dag.nodes.length === 0}
            <div class="empty-state">
              <p class="empty-title">No pipeline yet</p>
              <p class="empty-description">Run a goal to see your task pipeline</p>
            </div>
          {:else}
            <div class="pipeline-content">
              <DagCanvas />
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
      {:else}
        <main class="content">
          {#if agent.isRunning}
            <WorkingState />
          {:else if agent.isDone}
            <DoneState {projectFiles} {isLoadingFiles} onFileSelect={handleFileSelect} />
          {:else if agent.hasError}
            <ErrorState />
          {:else}
            <IdleState {projectStatus} {isLoadingStatus} {projectFiles} {isLoadingFiles} onFileSelect={handleFileSelect} />
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
    overflow: hidden;
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
    overflow: hidden;
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
</style>
