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
  import { goHome, goToPreview } from '../stores/app';
  import { currentProject, resumeProject } from '../stores/project';
  import { 
    agentState, 
    isRunning, 
    isDone, 
    hasError,
    progress,
    duration,
    completedTasks,
    stopAgent,
    resetAgent,
    runGoal
  } from '../stores/agent';
  import { invoke } from '@tauri-apps/api/core';
  import type { ProjectStatus, FileEntry } from '$lib/types';
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
  });
  
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
  
  // Reactive: check if there's an interrupted run to resume
  $: canResume = projectStatus?.status === 'interrupted';
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
    <hr class="divider" />
  {/if}
  
  <!-- Content -->
  <main class="content">
    {#if $isRunning}
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
    <div class="preview-overlay" on:click={closePreview} on:keydown={(e) => e.key === 'Escape' && closePreview()}>
      <div class="preview-panel" on:click|stopPropagation>
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
  
  .divider {
    border: none;
    border-top: 1px solid var(--border-color);
    margin: var(--space-4) 0;
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
  
  .last-run-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
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
  
  /* Checkpoint Tasks */
  .checkpoint-tasks {
    display: flex;
    flex-direction: column;
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    margin: var(--space-2) 0;
  }
  
  .checkpoint-task {
    display: grid;
    grid-template-columns: 24px 36px 1fr 24px;
    align-items: center;
    gap: var(--space-1);
    padding: var(--space-1) 0;
    color: var(--text-secondary);
  }
  
  .checkpoint-task.completed {
    color: var(--text-tertiary);
  }
  
  .checkpoint-task .task-prefix {
    color: var(--text-tertiary);
  }
  
  .checkpoint-task .task-number {
    color: var(--text-tertiary);
  }
  
  .checkpoint-task .task-description {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  
  .checkpoint-task .task-status {
    text-align: center;
  }
  
  .checkpoint-task.completed .task-status {
    color: var(--success);
  }
  
  .task-summary {
    font-family: var(--font-mono);
    font-size: var(--text-xs);
    color: var(--text-tertiary);
    margin: 0;
  }
  
  .resume-action {
    margin-top: var(--space-2);
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
</style>
