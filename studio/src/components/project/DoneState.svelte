<!--
  DoneState — Completed state UI (Svelte 5)
  RFC-064: Shows lens used for completed task
-->
<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import type { FileEntry } from '$lib/types';
  import Button from '../Button.svelte';
  import LearningsPanel from '../LearningsPanel.svelte';
  import FileTree from '../FileTree.svelte';
  import LensBadge from '../LensBadge.svelte';
  import { project } from '../../stores/project.svelte';
  import { goToPreview } from '../../stores/app.svelte';
  import { agent, resetAgent, runGoal } from '../../stores/agent.svelte';
  import { formatDuration } from '$lib/format';
  import { getRunProvider } from '../../stores/settings.svelte';
  
  interface Props {
    projectFiles?: FileEntry[];
    isLoadingFiles?: boolean;
    onFileSelect?: (event: { path: string; name: string; isDir: boolean }) => void;
  }
  
  let { projectFiles = [], isLoadingFiles = false, onFileSelect }: Props = $props();
  
  let doneTaskCount = $derived(agent.tasks.length > 0 ? agent.tasks.length : agent.totalTasks);
  let doneHasMismatch = $derived(agent.tasks.length === 0 && agent.totalTasks > 0);
  
  function handleTryIt() { goToPreview(); }
  
  async function handleOpenFiles() {
    if (!project.current?.path) return;
    try { await invoke('open_in_finder', { path: project.current.path }); } catch (e) { console.error('Failed to open files:', e); }
  }
  
  async function handleOpenTerminal() {
    if (!project.current?.path) return;
    try { await invoke('open_terminal', { path: project.current.path }); } catch (e) { console.error('Failed to open terminal:', e); }
  }
  
  async function handleOpenEditor() {
    if (!project.current?.path) return;
    try { await invoke('open_in_editor', { path: project.current.path }); } catch (e) { console.error('Failed to open editor:', e); }
  }
  
  async function handleRebuild() {
    const goal = agent.goal;
    if (!goal || !project.current?.path) return;
    resetAgent();
    const provider = getRunProvider();
    await runGoal(goal, project.current.path, null, true, provider);
  }
  
  function handleFileSelectInternal(detail: { path: string; name: string; isDir: boolean }) {
    onFileSelect?.(detail);
  }
</script>

<div class="done animate-fadeIn">
  <div class="done-header">
    <span class="done-icon" aria-hidden="true">◆</span>
    <span class="done-text">Done</span>
    <LensBadge size="sm" showAuto={false} />
    <span class="done-stats">
      {doneTaskCount} {doneHasMismatch ? 'artifacts' : 'tasks'} · {formatDuration(agent.duration)}
      {#if doneHasMismatch}
        <span class="warning-badge" title="Task tracking mismatch" aria-label="Warning">▲</span>
      {/if}
    </span>
  </div>
  
  <div class="try-it-section">
    <Button variant="primary" size="lg" icon="»" onclick={handleTryIt}>TRY IT</Button>
  </div>
  
  <nav class="done-nav" aria-label="Project actions">
    <button class="nav-link" onclick={handleOpenFiles}>files</button>
    <span class="nav-sep" aria-hidden="true">·</span>
    <button class="nav-link" onclick={handleOpenTerminal}>terminal</button>
    <span class="nav-sep" aria-hidden="true">·</span>
    <button class="nav-link" onclick={handleOpenEditor}>edit</button>
    <span class="nav-sep" aria-hidden="true">·</span>
    <button class="nav-link" onclick={handleRebuild}>rebuild</button>
  </nav>
  
  <div class="done-files">
    <h3 class="section-title">▤ Created Files</h3>
    {#if isLoadingFiles}
      <p class="loading-text" role="status">Loading files...</p>
    {:else if projectFiles.length === 0}
      <p class="empty-text">No files created</p>
    {:else}
      <div class="file-tree-container">
        <FileTree files={projectFiles} onselect={handleFileSelectInternal} />
      </div>
    {/if}
  </div>
  
  {#if agent.learnings.length > 0}
    <div class="done-learnings">
      <LearningsPanel learnings={agent.learnings} concepts={agent.concepts} collapsed={true} />
    </div>
  {/if}
</div>

<style>
  .done { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: var(--space-8); }
  .done-header { display: flex; align-items: baseline; gap: var(--space-3); }
  .done-icon { color: var(--success); font-size: var(--text-xl); font-weight: 600; }
  .done-text { font-size: var(--text-lg); font-weight: 500; }
  .done-stats { color: var(--text-tertiary); font-size: var(--text-sm); display: flex; align-items: center; gap: var(--space-2); }
  .warning-badge { color: var(--warning); font-size: var(--text-xs); cursor: help; }
  .try-it-section { margin: var(--space-8) 0; }
  .done-nav { display: flex; gap: var(--space-2); color: var(--text-tertiary); font-size: var(--text-sm); }
  .nav-link { color: var(--text-secondary); background: transparent; border: none; cursor: pointer; transition: color var(--transition-fast); }
  .nav-link:hover, .nav-link:focus { color: var(--text-primary); }
  .nav-link:focus { outline: 2px solid var(--accent); outline-offset: 2px; }
  .nav-sep { color: var(--text-tertiary); }
  .done-files { width: 100%; max-width: 500px; display: flex; flex-direction: column; gap: var(--space-2); }
  .section-title { font-size: var(--text-sm); font-weight: 500; color: var(--text-secondary); margin: 0; }
  .file-tree-container { background: var(--bg-secondary); border: 1px solid var(--border-color); border-radius: var(--radius-md); padding: var(--space-2); max-height: 300px; overflow-y: auto; }
  .loading-text, .empty-text { font-size: var(--text-sm); color: var(--text-tertiary); padding: var(--space-4); text-align: center; margin: 0; }
  .done-learnings { width: 100%; max-width: 500px; margin-top: var(--space-6); }
</style>
