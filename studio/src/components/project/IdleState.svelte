<!--
  IdleState — Project landing/idle state UI (Svelte 5)
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { untrack } from 'svelte';
  import type { FileEntry, ProjectStatus } from '$lib/types';
  import Button from '../Button.svelte';
  import InputBar from '../InputBar.svelte';
  import FileTree from '../FileTree.svelte';
  import RunButton from '../RunButton.svelte';
  import BriefingPanel from '../BriefingPanel.svelte';
  import ProviderSelector from '../ProviderSelector.svelte';
  import { project, resumeProject } from '../../stores/project.svelte';
  import { runGoal } from '../../stores/agent.svelte';
  import { briefing, loadBriefing, hasBriefing } from '../../stores/briefing.svelte';
  import { formatRelativeTime } from '$lib/format';
  import { getRunProvider } from '../../stores/settings.svelte';
  
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
  
  let lastGoal = $derived(projectStatus?.last_goal);
  let taskProgress = $derived(
    projectStatus?.tasks_completed !== undefined && projectStatus?.tasks_total !== undefined
      ? `${projectStatus.tasks_completed}/${projectStatus.tasks_total} tasks`
      : null
  );
  
  async function handleOpenFiles() {
    if (!project.current?.path) return;
    try { await invoke('open_in_finder', { path: project.current.path }); } catch (e) { console.error('Failed:', e); }
  }
  
  async function handleOpenTerminal() {
    if (!project.current?.path) return;
    try { await invoke('open_terminal', { path: project.current.path }); } catch (e) { console.error('Failed:', e); }
  }
  
  async function handleOpenEditor() {
    if (!project.current?.path) return;
    try { await invoke('open_in_editor', { path: project.current.path }); } catch (e) { console.error('Failed:', e); }
  }
  
  async function handleNewGoal(goal: string) {
    if (!project.current?.path) return;
    const provider = getRunProvider();
    await runGoal(goal, project.current.path, null, true, provider);
  }
  
  async function handleResume() {
    if (!project.current?.path) return;
    await resumeProject(project.current.path);
  }
  
  function handleFileSelectInternal(detail: { path: string; name: string; isDir: boolean }) {
    onFileSelect?.(detail);
  }
</script>

<div class="idle animate-fadeIn">
  <section class="project-info">
    <h2 class="project-title">{project.current?.name ?? 'Project'}</h2>
    {#if project.current?.id}
      <p class="project-id">ID: <code>{project.current.id}</code></p>
    {/if}
    {#if project.current?.description}
      <p class="project-description">{project.current.description}</p>
    {:else if project.current}
      <p class="project-description empty">No description</p>
    {/if}
    <p class="project-path">{project.current?.path}</p>
  </section>
  
  {#if hasBriefing()}
    <BriefingPanel />
  {/if}
  
  {#if !isLoadingStatus && projectStatus && projectStatus.status !== 'none'}
    <section class="last-run" aria-label="Last run status">
      {#if projectStatus.status === 'interrupted'}
        <div class="status-badge interrupted">
          <span class="badge-icon" aria-hidden="true">◐</span><span>Interrupted</span>
        </div>
        {#if lastGoal}<p class="last-goal">"{lastGoal}"</p>{/if}
        {#if taskProgress}<p class="last-progress">{taskProgress} completed</p>{/if}
        <Button variant="primary" onclick={handleResume}>Resume</Button>
      {:else if projectStatus.status === 'complete'}
        <div class="status-badge complete">
          <span class="badge-icon" aria-hidden="true">◆</span><span>Last run complete</span>
        </div>
        {#if lastGoal}<p class="last-goal">"{lastGoal}"</p>{/if}
      {:else if projectStatus.status === 'failed'}
        <div class="status-badge failed">
          <span class="badge-icon" aria-hidden="true">⊗</span><span>Last run failed</span>
        </div>
      {/if}
      {#if projectStatus.last_activity}
        <p class="last-activity">{formatRelativeTime(new Date(projectStatus.last_activity))}</p>
      {/if}
    </section>
  {/if}
  
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
  
  <section class="file-tree-section">
    <h3 class="section-title">// Project Files</h3>
    {#if isLoadingFiles}
      <p class="loading-text" role="status">Loading files...</p>
    {:else if projectFiles.length === 0}
      <p class="empty-text">No files yet</p>
    {:else}
      <div class="file-tree-container">
        <FileTree files={projectFiles} onselect={handleFileSelectInternal} />
      </div>
    {/if}
  </section>
  
  <section class="goal-input-section">
    <div class="input-header">
      <p class="input-label">What would you like to build?</p>
      <ProviderSelector />
    </div>
    <InputBar placeholder="describe your goal..." onsubmit={handleNewGoal} />
  </section>
</div>

<style>
  .idle { flex: 1; display: flex; flex-direction: column; gap: var(--space-8); padding: var(--space-4) 0; }
  .project-info { display: flex; flex-direction: column; gap: var(--space-2); }
  .project-title { font-size: var(--text-2xl); font-weight: 600; color: var(--text-primary); margin: 0; }
  .project-description { color: var(--text-secondary); font-size: var(--text-base); margin: 0; }
  .project-description.empty { color: var(--text-tertiary); font-style: italic; }
  .project-id { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-tertiary); margin: 0; }
  .project-id code { background: var(--bg-tertiary); padding: 2px 6px; border-radius: var(--radius-sm); color: var(--text-secondary); }
  .project-path { font-family: var(--font-mono); font-size: var(--text-xs); color: var(--text-tertiary); margin: 0; }
  .last-run { display: flex; flex-direction: column; gap: var(--space-3); padding: var(--space-4); background: var(--bg-secondary); border-radius: var(--radius-lg); border: 1px solid var(--border-color); max-width: 600px; }
  .status-badge { display: flex; align-items: center; gap: var(--space-2); font-size: var(--text-sm); font-weight: 500; }
  .status-badge.interrupted { color: var(--warning, #f59e0b); }
  .status-badge.complete { color: var(--success); }
  .status-badge.failed { color: var(--error); }
  .badge-icon { font-size: var(--text-base); }
  .last-goal { font-family: var(--font-mono); color: var(--text-primary); font-size: var(--text-sm); margin: 0; }
  .last-progress { font-size: var(--text-xs); color: var(--text-tertiary); margin: 0; }
  .last-activity { font-size: var(--text-xs); color: var(--text-tertiary); margin: 0; }
  .quick-actions { display: flex; gap: var(--space-3); }
  .action-btn { display: flex; flex-direction: column; align-items: center; gap: var(--space-1); padding: var(--space-3) var(--space-4); background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); color: var(--text-secondary); font-size: var(--text-xs); cursor: pointer; transition: all var(--transition-fast); min-width: 70px; }
  .action-btn:hover, .action-btn:focus { background: var(--bg-tertiary); border-color: var(--text-tertiary); color: var(--text-primary); }
  .action-btn:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
  .action-icon { font-size: var(--text-lg); }
  .file-tree-section { display: flex; flex-direction: column; gap: var(--space-2); }
  .section-title { font-size: var(--text-sm); font-weight: 500; color: var(--text-secondary); margin: 0; }
  .file-tree-container { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--space-2); max-height: 300px; overflow-y: auto; }
  .loading-text, .empty-text { font-size: var(--text-sm); color: var(--text-tertiary); padding: var(--space-4); text-align: center; margin: 0; }
  .goal-input-section { display: flex; flex-direction: column; gap: var(--space-3); margin-top: auto; padding-top: var(--space-8); }
  .input-header { display: flex; align-items: center; justify-content: space-between; gap: var(--space-4); }
  .input-label { font-size: var(--text-sm); color: var(--text-tertiary); margin: 0; }
</style>
