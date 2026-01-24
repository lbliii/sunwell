<!--
  IdleState — RFC-106 Unified Project Surface
  
  Combined project landing view that merges Overview and Progress tabs.
  Shows project analysis, pipeline, suggested action, last run status,
  and goal input in a single unified view.
-->
<script lang="ts">
  import { openFinder, openTerminal, openEditor, apiPost } from '$lib/socket';
  import { untrack } from 'svelte';
  import type { FileEntry, ProjectStatus } from '$lib/types';
  import Button from '../Button.svelte';
  import InputBar from '../InputBar.svelte';
  import FileTree from '../FileTree.svelte';
  import RunButton from '../RunButton.svelte';
  import BriefingPanel from '../BriefingPanel.svelte';
  import ProviderSelector from '../ProviderSelector.svelte';
  import { project, resumeProject, analyzeProject } from '../../stores/project.svelte';
  import { runGoal } from '../../stores/agent.svelte';
  import { briefing, loadBriefing } from '../../stores/briefing.svelte';
  import { getRunProvider } from '../../stores/settings.svelte';
  
  // RFC-106: New unified components
  import AnalysisSkeleton from './AnalysisSkeleton.svelte';
  import EmptyPipelineState from './EmptyPipelineState.svelte';
  import ProjectIdentity from './ProjectIdentity.svelte';
  import PipelineSection from './PipelineSection.svelte';
  import SuggestedAction from './SuggestedAction.svelte';
  import LastRunStatus from './LastRunStatus.svelte';
  import CollapsibleSection from './CollapsibleSection.svelte';
  
  interface Props {
    projectStatus?: ProjectStatus | null;
    isLoadingStatus?: boolean;
    projectFiles?: FileEntry[];
    isLoadingFiles?: boolean;
    onFileSelect?: (event: { path: string; name: string; isDir: boolean }) => void;
  }
  
  let { projectStatus = null, isLoadingStatus = true, projectFiles = [], isLoadingFiles = false, onFileSelect }: Props = $props();
  
  // RFC-071: Load briefing when project path is available
  $effect(() => {
    const path = project.current?.path;
    if (path) {
      untrack(async () => {
        await loadBriefing(path);
      });
    }
  });
  
  // Derived states
  const hasAnalysis = $derived(project.analysis !== null);
  const hasPipeline = $derived(project.analysis?.pipeline && project.analysis.pipeline.length > 0);
  const hasSuggestedAction = $derived(project.analysis?.suggested_action !== null);
  const hasLastRun = $derived(projectStatus && projectStatus.status !== 'none');
  
  // Quick action handlers
  async function handleOpenFiles() {
    if (!project.current?.path) return;
    try { await openFinder(project.current.path); } catch (e) { console.error('Failed:', e); }
  }
  
  async function handleOpenTerminal() {
    if (!project.current?.path) return;
    try { await openTerminal(project.current.path); } catch (e) { console.error('Failed:', e); }
  }
  
  async function handleOpenEditor() {
    if (!project.current?.path) return;
    try { await openEditor(project.current.path); } catch (e) { console.error('Failed:', e); }
  }
  
  // Goal handlers
  async function handleNewGoal(goal: string) {
    if (!project.current?.path) return;
    const provider = getRunProvider();
    // RFC-117: Pass project ID for workspace isolation
    await runGoal(goal, project.current.path, project.currentId ?? undefined, null, true, provider);
  }
  
  async function handleResume() {
    if (!project.current?.path) return;
    await resumeProject(project.current.path);
  }
  
  // RFC-106: Handlers for analysis actions (moved from Project.svelte)
  async function handleWorkOnGoal(goalId: string) {
    const goal = project.analysis?.goals.find(g => g.id === goalId);
    if (goal && project.current?.path) {
      const provider = getRunProvider();
      // RFC-117: Pass project ID for workspace isolation
      await runGoal(goal.title, project.current.path, project.currentId ?? undefined, null, true, provider);
    }
  }
  
  async function handleStartServer(command: string) {
    if (!project.current?.path) return;
    try {
      await apiPost('/api/project/run', { 
        path: project.current.path, 
        command,
      });
    } catch (e) {
      console.error('Failed to start dev server:', e);
    }
  }
  
  function handleAddGoal() {
    // Focus the input bar - the goal input is already visible below
    const input = document.querySelector<HTMLInputElement>('.goal-input-section input');
    input?.focus();
  }
  
  function handleFileSelectInternal(detail: { path: string; name: string; isDir: boolean }) {
    onFileSelect?.(detail);
  }
  
  async function handleRetryAnalysis() {
    if (project.current?.path) {
      await analyzeProject(project.current.path, true);
    }
  }
</script>

<div class="idle animate-fadeIn">
  <!-- Section 1: Project Identity / Analysis -->
  {#if project.isAnalyzing}
    <AnalysisSkeleton />
  {:else if project.analysisError}
    <div class="analysis-error" role="alert">
      <span class="error-icon">⚠️</span>
      <span>Analysis unavailable</span>
      <Button variant="ghost" size="sm" onclick={handleRetryAnalysis}>Retry</Button>
    </div>
  {:else if hasAnalysis && project.analysis}
    <ProjectIdentity analysis={project.analysis} />
  {/if}
  
  <!-- Section 2: Pipeline -->
  {#if !project.isAnalyzing && hasAnalysis && project.analysis}
    {#if hasPipeline && project.analysis.pipeline}
      <PipelineSection 
        pipeline={project.analysis.pipeline}
        currentStep={project.analysis.current_step}
        completionPercent={project.analysis.completion_percent}
      />
    {:else}
      <EmptyPipelineState projectType={project.analysis.project_type} />
    {/if}
  {/if}
  
  <!-- Section 3: Suggested Action -->
  {#if !project.isAnalyzing && hasAnalysis && hasSuggestedAction && project.analysis?.suggested_action}
    <SuggestedAction 
      action={project.analysis.suggested_action}
      devCommand={project.analysis.dev_command}
      onWorkOnGoal={handleWorkOnGoal}
      onStartServer={handleStartServer}
      onAddGoal={handleAddGoal}
    />
  {/if}
  
  <!-- Section 4: Last Run Status -->
  {#if !isLoadingStatus && hasLastRun && projectStatus}
    <LastRunStatus status={projectStatus} onResume={handleResume} />
  {/if}
  
  <!-- Section 5: Briefing Panel -->
  {#if briefing.hasBriefing}
    <BriefingPanel />
  {/if}
  
  <!-- Section 6: Goal Input (always visible) -->
  <section class="goal-input-section">
    <div class="input-header">
      <p class="input-label">// What would you like to build?</p>
      <ProviderSelector />
    </div>
    <InputBar placeholder="describe your goal..." onsubmit={handleNewGoal} />
  </section>
  
  <!-- Section 7: Project Files (collapsed) -->
  <CollapsibleSection title="Project Files" count={projectFiles.length}>
    {#if isLoadingFiles}
      <p class="loading-text" role="status">Loading files...</p>
    {:else if projectFiles.length === 0}
      <p class="empty-text">No files yet</p>
    {:else}
      <div class="file-tree-container">
        <FileTree files={projectFiles} onselect={handleFileSelectInternal} />
      </div>
    {/if}
  </CollapsibleSection>
  
  <!-- Section 8: Quick Actions -->
  <div class="quick-actions">
    <button class="action-btn" onclick={handleOpenFiles} aria-label="Open in Finder">
      <span class="action-icon" aria-hidden="true">▤</span><span>Finder</span>
    </button>
    <button class="action-btn" onclick={handleOpenTerminal} aria-label="Open Terminal">
      <span class="action-icon" aria-hidden="true">⊳</span><span>Terminal</span>
    </button>
    <button class="action-btn" onclick={handleOpenEditor} aria-label="Open in Editor">
      <span class="action-icon" aria-hidden="true">⊡</span><span>Editor</span>
    </button>
    {#if project.current?.path}
      <RunButton projectPath={project.current.path} />
    {/if}
  </div>
</div>

<style>
  .idle {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4) 0;
    max-width: 700px;
  }
  
  .analysis-error {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--bg-secondary);
    border-radius: var(--radius-md);
    border: 1px solid var(--warning);
    color: var(--text-secondary);
    font-size: var(--text-sm);
  }
  
  .error-icon {
    font-size: var(--text-base);
  }
  
  .goal-input-section {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-color);
  }
  
  .input-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-4);
  }
  
  .input-label {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    margin: 0;
    font-family: var(--font-mono);
  }
  
  .file-tree-container {
    max-height: 250px;
    overflow-y: auto;
  }
  
  .loading-text, .empty-text {
    font-size: var(--text-sm);
    color: var(--text-tertiary);
    padding: var(--space-4);
    text-align: center;
    margin: 0;
  }
  
  .quick-actions {
    display: flex;
    gap: var(--space-3);
    padding-top: var(--space-4);
    border-top: 1px solid var(--border-color);
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
    cursor: pointer;
    transition: all var(--transition-fast);
    min-width: 70px;
  }
  
  .action-btn:hover, .action-btn:focus {
    background: var(--bg-tertiary);
    border-color: var(--text-tertiary);
    color: var(--text-primary);
  }
  
  .action-btn:focus {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  
  .action-icon {
    font-size: var(--text-lg);
  }
</style>
